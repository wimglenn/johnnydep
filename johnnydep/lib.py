import json
import os
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

from anytree import NodeMixin
from anytree import RenderTree
from anytree.iterators import LevelOrderIter
from johnnydep.pipper import get
from johnnydep.pipper import get_versions
from pip.req.req_install import Marker
from pkg_resources import get_distribution
from pkg_resources import DistributionNotFound
from pkg_resources import Requirement
from pkg_resources import VersionConflict
from structlog import get_logger
from types import SimpleNamespace
from wheel.metadata import pkginfo_to_dict
from wimpy import cached_property
from wimpy import strip_suffix
from wimpy import working_directory


__all__ = ['JohnnyDist', 'get_wheel_file', 'gen_table']


logger = get_logger(__name__)
DEFAULT_INDEX = 'https://pypi.python.org/simple'
tmp = Path(os.environ.get('TMPDIR') or '/tmp') / 'johnnydep'
tmp.mkdir(exist_ok=True)


class JohnnyDist(NodeMixin):

    def __init__(self, req_string, parent=None, index_url=DEFAULT_INDEX):
        self.req = Requirement.parse(req_string)
        log = self.log = logger.bind(dist=str(req_string))
        log.info('init johnnydist', parent=parent and str(parent.req))
        if parent is not None:
            self.index_url = parent.index_url
        else:
            if index_url is None:
                index_url = DEFAULT_INDEX
            self.index_url = index_url
        try:
            log.debug('checking if installed already')
            dist = get_distribution(req_string)
        except (DistributionNotFound, VersionConflict) as err:
            log.debug('not found, fetching a wheel')
            local_whl = get_wheel_file(req_string, index_url=self.index_url)
            self.zip = ZipFile(file=str(tmp/local_whl.path))
            self.namelist = self.zip.namelist()
            if isinstance(err, VersionConflict):
                self.installed = get_distribution(self.req.name).version
            else:
                self.installed = None
        else:
            log.debug('existing installation found', version=dist.version)
            self.installed = dist.version
            self.namelist = [os.path.join(dist.egg_info, x) for x in os.listdir(dist.egg_info)]
            self.zip = None
        self.parent = parent
        self._recursed = False

    def read(self, name):
        if self.zip is None:
            return Path(name).read_text()
        else:
            return self.zip.read(name).decode('utf-8')

    @cached_property
    def import_names(self):
        self.log.debug('finding import names')
        try:
            [top_level_fname] = [x for x in self.namelist if x.endswith('top_level.txt')]
        except ValueError:
            self.log.debug('top_level absent, trying metadata')
            public_names = self.metadata['python.exports']['modules'] or []
        else:
            all_names = self.read(top_level_fname).splitlines()
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
            with NamedTemporaryFile(mode='w', encoding='utf-8') as f:
                f.write(self.read(metadata_fname))
                f.flush()
                data = pkginfo_to_dict(f.name)
        else:
            data = json.loads(self.read(metadata_fname))
        return data

    @cached_property
    def deps(self):
        """Just the strings (name and spec) for my immediate dependencies. Cheap."""
        # TODO : gets for other env / cross-compat?
        result = []
        for d in self.metadata.get('run_requires', {}):
            if 'extra' in d:
                include = d['extra'] in self.req.extras
                msg = f"{'adding' if include else 'ignored'} reqs for extra"
                self.log.debug(msg, extra=d['extra'], requires=d['requires'])
                if not include:
                    continue
            if 'environment' in d:
                include = Marker(d['environment']).evaluate()
                msg = f"{'adding' if include else 'ignored'} platform specific reqs"
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
            for dep in self.deps:
                # a bit of a kludge but .. transform metadata back into PEP440 style syntax
                dep = dep.replace(' (', '').rstrip(')')
                JohnnyDist(req_string=dep, parent=self)
            self._recursed = True
        return super().children

    def iter_tree(self):
        yield from LevelOrderIter(self)

    @property
    def homepage(self):
        for k in 'python.details', 'python.project':
            try:
                return self.metadata['extensions'][k]['project_urls']['Home']
            except KeyError:
                pass
        self.log.info("unknown url")

    @property
    def specifier(self):
        return self.req.specifier

    @property
    def summary(self):
        return self.metadata.get('summary').lstrip('#').strip()

    @cached_property
    def latest(self):
        all_versions = get_versions(self.req.name)
        return all_versions.split(', ')[-1]

    @property
    def options(self):
        return ', '.join(self.metadata.get('extras', []))

    @property
    def provides(self):
        return ', '.join(self.import_names)


@lru_cache()
def get_wheel_file(dist_name, index_url=DEFAULT_INDEX):
    with working_directory(tmp):
        return SimpleNamespace(**get(dist_name=dist_name, index_url=index_url))


def gen_table(johnnydist, extra_cols=()):
    johnnydist.log.debug('generating table')
    for pre, _fill, node in RenderTree(johnnydist):
        row = OrderedDict()
        name = str(node.req)
        if 'specifier' in extra_cols:
            name = strip_suffix(name, str(node.specifier))
        row['name'] = f'{pre}{name}'
        for col in extra_cols:
            row[col] = getattr(node, col, '')
        yield row


def flatten_deps(johnnydist):
    """yields tuples of (project_name, johnnydist) in breadth-first order, including the root node"""
    seen = {}  # dict of {project_name: (spec, extras, johnnydist)}
    for dep in johnnydist.iter_tree():
        try:
            prev_spec, prev_extras, prev = seen[dep.req.name]
        except KeyError:
            # we have not seen this dep before
            seen[dep.req.name] = dep.req.specifier, dep.req.extras, dep
        else:
            # we already saw this dep earlier...
            new_spec, new_extras = prev_spec & dep.req.specifier, prev_extras | dep.req.extras
            seen[dep.req.name] = new_spec, new_extras, dep
            if prev.metadata['version'] in new_spec and prev.req.extras <= new_extras:
                # the wheel yielded earlier is still in spec of the new requirements, so we can just skip it
                logger.debug(
                    'prev dist still in spec', project_name=dep.req.name,
                    prev_version=prev.metadata['version'], new_spec=new_spec, new_extras=new_extras,
                )
                continue
            else:
                logger.info(
                    'updated dependency', project_name=dep.req.name,
                    old_spec=prev_spec, old_extras=prev_extras,
                    new_spec=new_spec, new_extras=new_extras,
                )
        yield dep.req.name, dep
        # TODO : dependency resolution handling for disjoint extras / specs


# TODO: json and/or yaml output
# TODO: progress bar?
# TODO: TTL cache
