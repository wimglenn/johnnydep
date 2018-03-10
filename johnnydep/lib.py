from __future__ import unicode_literals

import errno
import io
import json
import os
import sys
from collections import defaultdict
from collections import OrderedDict
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

import anytree
import oyaml
import pkg_resources
import pytoml
import wimpy
from cachetools.func import ttl_cache
from pip.index import canonicalize_name
from pip.req.req_install import Marker
from structlog import get_logger
from wheel.metadata import pkginfo_to_dict
from wheel.util import OrderedDefaultDict
from wimpy import cached_property

from johnnydep import pipper

__all__ = ['JohnnyDist', 'gen_table', 'flatten_deps']


logger = get_logger(__name__)
DEFAULT_INDEX = 'https://pypi.python.org/simple'


if sys.version_info < (3,):
    oyaml.add_representer(unicode, lambda d, s: oyaml.ScalarNode(tag=u'tag:yaml.org,2002:str', value=s))


class JohnnyDist(anytree.NodeMixin):

    def __init__(self, req_string, parent=None, index_url=DEFAULT_INDEX):
        self.req = pkg_resources.Requirement.parse(req_string)

        self.name = canonicalize_name(str(self.req.name))
        self.specifier = str(self.req.specifier)
        self.extras_requested = sorted(self.req.extras)

        log = self.log = logger.bind(dist=str(self.req))
        log.info('init johnnydist', parent=parent and str(parent.req))
        if parent is not None:
            self.index_url = parent.index_url
            self.required_by = [str(parent.req)]
        else:
            self.index_url = index_url
            self.required_by = []
        try:
            log.debug('checking if installed already')
            dist = pkg_resources.get_distribution(req_string)
            log.debug('existing installation found', version=dist.version)
            self.version_installed = dist.version
            dist = pkg_resources.get_distribution(self.pinned)
        except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict) as err:
            log.debug('fetching best wheel')
            with wimpy.working_directory(self.tmp()):
                local_whl_data = get_wheel(req_string, index_url=self.index_url)
            self.zip = ZipFile(file=local_whl_data['path'])
            self.namelist = self.zip.namelist()
            if isinstance(err, pkg_resources.VersionConflict):
                self.version_installed = pkg_resources.get_distribution(self.name).version
            else:
                self.version_installed = None
        else:
            log.debug('existing installation is best!', version=dist.version)
            self.namelist = [os.path.join(dist.egg_info, x) for x in os.listdir(dist.egg_info)]
            self.zip = None
        self.parent = parent
        self._recursed = False

    def read(self, name):
        if self.zip is None:
            with io.open(name) as f:
                return f.read()
        else:
            return self.zip.read(name).decode('utf-8')

    @cached_property
    def import_names(self):
        self.log.debug('finding import names')
        try:
            [top_level_fname] = [x for x in self.namelist if x.endswith('top_level.txt')]
        except ValueError:
            self.log.debug('top_level absent, trying metadata')
            try:
                public_names = self.metadata['python.exports']['modules'] or []
            except KeyError:
                # this dist was packaged by a dinosaur, exports is not in metadata.
                # we gotta do it the hard way ...
                public_names = []
                for name in self.namelist:
                    if '.dist-info/' in name or '.egg-info/' in name:
                        continue
                    parts = name.split(os.sep)
                    if len(parts) == 2 and parts[1] == '__init__.py':
                        # found a top-level package
                        public_names.append(parts[0])
                    elif len(parts) == 1:
                        name, ext = os.path.splitext(parts[0])
                        if ext == '.py' or ext == '.so':
                            # found a top level module
                            public_names.append(name)
        else:
            all_names = self.read(top_level_fname).strip().splitlines()
            public_names = [n for n in all_names if not n.startswith('_')]
        return public_names

    @cached_property
    def metadata(self):
        self.log.debug('searching metadata')
        try:
            [metadata_fname] = [x for x in self.namelist if x.endswith('metadata.json') or x.endswith('pydist.json')]
        except ValueError:
            self.log.debug('json meta absent, try pkginfo')
            [metadata_fname] = [x for x in self.namelist if x.endswith('METADATA') or x.endswith('PKG-INFO')]
            with NamedTemporaryFile(mode='w') as f:
                f.write(self.read(metadata_fname))
                f.flush()
                data = pkginfo_to_dict(f.name)
            data.default_factory = None  # disables defaultdict, restoring KeyErrors
        else:
            data = json.loads(self.read(metadata_fname))
        return data

    @cached_property
    def requires(self):
        """Just the strings (name and spec) for my immediate dependencies. Cheap."""
        # TODO : gets for other env / cross-compat?
        result = []
        for d in self.metadata.get('run_requires', {}):
            if 'extra' in d:
                include = d['extra'] in self.extras_requested
                msg = ('adding' if include else 'ignored') + ' reqs for extra'
                self.log.debug(msg, extra=d['extra'], requires=d['requires'])
                if not include:
                    continue
            if 'environment' in d:
                include = Marker(d['environment']).evaluate()
                msg = ('adding' if include else 'ignored') + ' platform specific reqs'
                self.log.debug(msg, env=d['environment'], requires=d['requires'])
                if not include:
                    continue
            result.extend(d['requires'])
        result = sorted(set(result))  # this makes the dep tree deterministic/repeatable
        return result

    @property
    def children(self):
        """my immediate deps, as a tuple of johnnydists"""
        if not self._recursed:
            self.log.debug('populating dep tree')
            for dep in self.requires:
                JohnnyDist(req_string=dep, parent=self)
            self._recursed = True
        return super(JohnnyDist, self).children

    @property
    def homepage(self):
        for k in 'python.details', 'python.project':
            try:
                return self.metadata['extensions'][k]['project_urls']['Home']
            except KeyError:
                pass
        self.log.info("unknown homepage")

    @property
    def summary(self):
        return self.metadata.get('summary').lstrip('#').strip()

    @cached_property
    def versions_available(self):
        all_versions = pipper.get_versions(self.name, index_url=self.index_url)
        return all_versions.split(', ')

    @property
    def version_latest(self):
        if self.versions_available:
            return self.versions_available[-1]

    @property
    def version_latest_in_spec(self):
        for v in reversed(self.versions_available):
            if v in self.req.specifier:
                return v

    @property
    def extras_available(self):
        return sorted([x for x in self.metadata.get('extras', []) if x])

    @property
    def project_name(self):
        return self.metadata.get('name', self.name)

    @classmethod
    def tmp(cls):
        if getattr(cls, '_tmpdir', None) is None:
            tmpdir = os.path.join((os.environ.get('TMPDIR') or '/tmp'), 'johnnydep')
            logger.debug('get or create scratch', tmpdir=tmpdir)
            try:
                os.mkdir(tmpdir)
            except OSError as err:
                if err.errno != errno.EEXIST:
                    raise
            cls._tmpdir = tmpdir
        return cls._tmpdir

    @property
    def pinned(self):
        if self.extras_requested:
            extras = '[{}]'.format(','.join(self.extras_requested))
        else:
            extras = ''
        result = '{}{}=={}'.format(self.name, extras, self.version_latest_in_spec)
        return result

    @cached_property
    def _best(self):
        return pipper.get_link(self.pinned, index_url=self.index_url)

    @property
    def download_link(self):
        return self._best['url']

    @property
    def checksum(self):
        return self._best['checksum']

    def serialise(self, fields=('name', 'summary'), recurse=True, format=None):
        if format == 'pinned':
            # user-specified fields are ignored/invalid in this case
            fields = 'pinned',
        data = [OrderedDict([(f, getattr(self, f, None)) for f in fields])]
        if recurse and self.requires:
            deps = flatten_deps(self)
            next(deps)  # skip over root
            data += [d for dep in deps for d in dep.serialise(fields=fields, recurse=False)]
        if format is None or format == 'python':
            result = data
        elif format == 'json':
            result = json.dumps(data, indent=2, default=str, separators=(',', ': '))
        elif format == 'yaml':
            result = oyaml.dump(data)
        elif format == 'toml':
            result = '\n'.join([pytoml.dumps(d) for d in data])
        elif format == 'pinned':
            result = '\n'.join([d['pinned'] for d in data])
        else:
            raise Exception('Unsupported format')
        return result


@ttl_cache(maxsize=512, ttl=60*5)  # memo with 5 minutes time-to-live
def get_wheel(dist_name, index_url=DEFAULT_INDEX):
    return pipper.get(dist_name=dist_name, index_url=index_url)


def gen_table(johnnydist, extra_cols=()):
    extra_cols = OrderedDict.fromkeys(extra_cols)  # de-dupe and preserve ordering
    extra_cols.pop('name', None)  # this is always included anyway, no need to ask for it
    johnnydist.log.debug('generating table')
    for pre, _fill, node in anytree.RenderTree(johnnydist):
        row = OrderedDict()
        name = str(node.req)
        if 'specifier' in extra_cols:
            name = wimpy.strip_suffix(name, str(node.specifier))
        row['name'] = pre + name
        for col in extra_cols:
            val = getattr(node, col, '')
            if isinstance(val, list):
                val = ', '.join(val)
            row[col] = val
        yield row


def flatten_deps(johnnydist):
    johnnydist.log.debug('resolving dep tree')
    dist_map = OrderedDefaultDict(list)
    spec_map = defaultdict(str)
    extra_map = defaultdict(set)
    required_by_map = defaultdict(list)
    for dep in anytree.iterators.LevelOrderIter(johnnydist):
        dist_map[dep.name].append(dep)
        spec_map[dep.name] = dep.req.specifier & spec_map[dep.name]
        extra_map[dep.name] |= set(dep.extras_requested)
        required_by_map[dep.name] += dep.required_by
    for name, dists in dist_map.items():
        spec = spec_map[name]
        extras = extra_map[name]
        required_by = list(OrderedDict.fromkeys(required_by_map[name]))  # order preserving de-dupe
        for dist in dists:
            if dist.version_latest_in_spec in spec and set(dist.extras_requested) >= extras:
                dist.required_by = required_by
                johnnydist.log.debug('resolved', name=dist.name, required_by=required_by)
                yield dist
                break
        else:
            nameset = {dist.name for dist in dists}
            assert len(nameset) == 1  # name attributes were canonicalized by JohnnyDist.__init__
            [name] = nameset
            johnnydist.log.debug('merged specs', name=name, spec=spec, extras=extras)
            req_string = '{name}{extras}{spec}'.format(
                name=name,
                extras='[{}]'.format(','.join(sorted(extras))) if extras else '',
                spec=spec,
            )
            dist = JohnnyDist(req_string, index_url=dists[0].index_url)
            dist.required_by = required_by
            yield dist
            # TODO: check if this new version has any new reqs!!


# TODO: progress bar?
# TODO: handle recursive dep tree
# TODO: test dists to test pypi index, document pip failure modes
