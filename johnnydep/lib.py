# coding: utf-8
from __future__ import unicode_literals

import json
import os
import re
import subprocess
from collections import defaultdict
from shutil import rmtree
from tempfile import mkdtemp
from zipfile import ZipFile

import anytree
import pkg_resources
import pkginfo
import toml
import tabulate
import wimpy
from cachetools.func import ttl_cache
from packaging.markers import default_environment
from packaging.utils import canonicalize_name
from packaging.utils import canonicalize_version
from structlog import get_logger
from wimpy import cached_property

from johnnydep import pipper
from johnnydep.compat import dict
from johnnydep.compat import oyaml

__all__ = ["JohnnyDist", "gen_table", "flatten_deps", "has_error"]


logger = get_logger(__name__)


class OrderedDefaultListDict(dict):
    def __missing__(self, key):
        self[key] = value = []
        return value


class JohnnyDist(anytree.NodeMixin):
    def __init__(self, req_string, parent=None, index_url=None, env=None, extra_index_url=None, ignore_errors=False):
        log = self.log = logger.bind(dist=req_string)
        log.info("init johnnydist", parent=parent and str(parent.req))
        self.parent = parent
        self.index_url = index_url
        self.env = env
        self.extra_index_url = extra_index_url
        self.ignore_errors = ignore_errors
        self.error = None
        self._recursed = False

        fname, sep, extras = req_string.partition("[")
        if fname.endswith(".whl") and os.path.isfile(fname):
            # crudely parse dist name and version from wheel filename
            # see https://peps.python.org/pep-0427/#file-name-convention
            parts = os.path.basename(fname).split("-")
            self.name = canonicalize_name(parts[0])
            self.specifier = "==" + canonicalize_version(parts[1])
            self.req = pkg_resources.Requirement.parse(self.name + sep + extras + self.specifier)
            self.import_names = _discover_import_names(fname)
            self.metadata = _extract_metadata(fname)
        else:
            self.req = pkg_resources.Requirement.parse(req_string)
            self.name = canonicalize_name(self.req.name)
            self.specifier = str(self.req.specifier)
            log.debug("fetching best wheel")
            try:
                self.import_names, self.metadata = _get_info(
                    dist_name=req_string,
                    index_url=index_url,
                    env=env,
                    extra_index_url=extra_index_url
                )
            except subprocess.CalledProcessError as err:
                if not self.ignore_errors:
                    raise
                self.import_names = None
                self.metadata = {}
                self.error = err

        self.extras_requested = sorted(self.req.extras)
        if parent is None:
            if env:
                log.debug("root node target env", **dict(env))
            self.required_by = []
        else:
            self.required_by = [str(parent.req)]

    @property
    def requires(self):
        """Just the strings (name and spec) for my immediate dependencies. Cheap."""
        all_requires = self.metadata.get("requires_dist", [])
        if not all_requires:
            return []
        result = []
        if self.env is None:
            env_data = default_environment()
        else:
            env_data = dict(self.env)
        for req_str in all_requires:
            req = pkg_resources.Requirement.parse(req_str)
            req_short, _sep, _marker = str(req).partition(";")
            if req.marker is None:
                # unconditional dependency
                result.append(req_short)
                continue
            # conditional dependency - must be evaluated in environment context
            for extra in [None] + self.extras_requested:
                if req.marker.evaluate(dict(env_data, extra=extra)):
                    self.log.debug("included conditional dep", req=req_str)
                    result.append(req_short)
                    break
            else:
                self.log.debug("dropped conditional dep", req=req_str)
        result = sorted(set(result))  # this makes the dep tree deterministic/repeatable
        return result

    @property
    def children(self):
        """my immediate deps, as a tuple of johnnydists"""
        if not self._recursed:
            self.log.debug("populating dep tree")
            for dep in self.requires:
                JohnnyDist(
                    req_string=dep,
                    parent=self,
                    index_url=self.index_url,
                    env=self.env,
                    extra_index_url=self.extra_index_url,
                    ignore_errors=self.ignore_errors,
                )
            self._recursed = True
        return super(JohnnyDist, self).children

    @property
    def homepage(self):
        try:
            return self.metadata["home_page"]
        except KeyError:
            for k in "python.details", "python.project":
                try:
                    return self.metadata["extensions"][k]["project_urls"]["Home"]
                except KeyError:
                    pass
        self.log.info("unknown homepage")

    @property
    def summary(self):
        text = self.metadata.get("summary") or ""
        result = text.lstrip("#").strip()
        return result

    @property
    def license(self):
        result = self.metadata.get("license") or ""
        # sometimes people just put the license in a trove classifier instead
        # for a list of valid classifiers:
        #   requests.get('https://pypi.python.org/pypi', params={':action': 'list_classifiers'}).text.splitlines()
        self.log.debug("metadata license is not set, checking trove classifiers")
        for classifier in self.metadata.get("classifiers", []):
            if classifier.startswith("License :: "):
                crap, result = classifier.rsplit(" :: ", 1)
                break
        if not result:
            self.log.info("unknown license")
        return result

    @cached_property
    def versions_available(self):
        return pipper.get_versions(
            self.project_name,
            index_url=self.index_url,
            env=self.env,
            extra_index_url=self.extra_index_url,
        )

    @cached_property
    def version_installed(self):
        self.log.debug("checking if installed already")
        try:
            dist = pkg_resources.get_distribution(self.name)
        except pkg_resources.DistributionNotFound:
            self.log.debug("not installed")
            return
        self.log.debug("existing installation found", version=dist.version)
        return dist.version

    @property
    def version_latest(self):
        if self.versions_available:
            return self.versions_available[-1]

    @property
    def version_latest_in_spec(self):
        avail = list(reversed(self.versions_available))
        for v in avail:
            if v in self.req.specifier:
                return v
        # allow to get a pre-release if that's all the index has for us
        for v in avail:
            if self.req.specifier.contains(v, prereleases=True):
                return v

    @property
    def extras_available(self):
        extras = {x for x in self.metadata.get("provides_extras", []) if x}
        for req_str in self.metadata.get("requires_dist", []):
            req = pkg_resources.Requirement.parse(req_str)
            extras |= set(re.findall(r'extra == "(.*?)"', str(req.marker)))
        return sorted(extras)

    @property
    def project_name(self):
        return self.metadata.get("name", self.name)

    @property
    def pinned(self):
        if self.extras_requested:
            extras = "[{}]".format(",".join(self.extras_requested))
        else:
            extras = ""
        version = self.version_latest_in_spec
        if version is None:
            raise Exception("Can not pin because no version available is in spec")
        result = "{}{}=={}".format(self.project_name, extras, version)
        return result

    @cached_property
    def _best(self):
        return pipper.get(
            self.pinned,
            index_url=self.index_url,
            env=self.env,
            extra_index_url=self.extra_index_url,
            ignore_errors=True,
        )

    @property
    def download_link(self):
        return self._best.get("url")

    @property
    def checksum(self):
        return self._best.get("checksum")

    def serialise(self, fields=("name", "summary"), recurse=True, format=None):
        if format == "pinned":
            # user-specified fields are ignored/invalid in this case
            fields = ("pinned",)
        data = [dict([(f, getattr(self, f, None)) for f in fields])]
        if format == "human":
            table = gen_table(self, extra_cols=fields)
            if not recurse:
                table = [next(table)]
            tabulate.PRESERVE_WHITESPACE = True
            return tabulate.tabulate(table, headers="keys")
        if recurse and self.requires:
            deps = flatten_deps(self)
            next(deps)  # skip over root
            data += [d for dep in deps for d in dep.serialise(fields=fields, recurse=False)]
        if format is None or format == "python":
            result = data
        elif format == "json":
            result = json.dumps(data, indent=2, default=str, separators=(",", ": "))
        elif format == "yaml":
            result = oyaml.dump(data)
        elif format == "toml":
            result = "\n".join([toml.dumps(d) for d in data])
        elif format == "pinned":
            result = "\n".join([d["pinned"] for d in data])
        else:
            raise Exception("Unsupported format")
        return result

    serialize = serialise

    def _repr_pretty_(self, p, cycle):
        # hook for IPython's pretty-printer
        if cycle:
            p.text(repr(self))
        else:
            fullname = self.name + self.specifier
            if self.extras_requested:
                fullname += "[{}]".format(",".join(self.extras_requested))
            p.text("<{} {} at {}>".format(type(self).__name__, fullname, hex(id(self))))


def gen_table(johnnydist, extra_cols=()):
    extra_cols = dict.fromkeys(extra_cols)  # de-dupe and preserve ordering
    extra_cols.pop("name", None)  # this is always included anyway, no need to ask for it
    johnnydist.log.debug("generating table")
    for pre, _fill, node in anytree.RenderTree(johnnydist):
        row = dict()
        name = str(node.req)
        if node.error:
            name += " (FAILED)"
        if "specifier" in extra_cols:
            name = wimpy.strip_suffix(name, str(node.specifier))
        row["name"] = pre + name
        for col in extra_cols:
            val = getattr(node, col, "")
            if isinstance(val, list):
                val = ", ".join(val)
            row[col] = val
        yield row


def flatten_deps(johnnydist):
    # TODO: add the check for infinite recursion in here (traverse parents)
    johnnydist.log.debug("resolving dep tree")
    dist_map = OrderedDefaultListDict()
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
        spec.prereleases = True
        extras = extra_map[name]
        required_by = list(dict.fromkeys(required_by_map[name]))  # order preserving de-dupe
        for dist in dists:
            if dist.version_latest_in_spec in spec and set(dist.extras_requested) >= extras:
                dist.required_by = required_by
                johnnydist.log.info(
                    "resolved",
                    name=dist.name,
                    required_by=required_by,
                    v=dist.version_latest_in_spec,
                    spec=str(spec) or "ANY",
                )
                yield dist
                break
        else:
            nameset = {dist.name for dist in dists}
            assert len(nameset) == 1  # name attributes were canonicalized by JohnnyDist.__init__
            [name] = nameset
            johnnydist.log.info("merged specs", name=name, spec=spec, extras=extras)
            req_string = "{name}{extras}{spec}".format(
                name=name,
                extras="[{}]".format(",".join(sorted(extras))) if extras else "",
                spec=spec,
            )
            dist = JohnnyDist(
                req_string=req_string,
                index_url=johnnydist.index_url,
                env=johnnydist.env,
                extra_index_url=johnnydist.extra_index_url,
            )
            dist.required_by = required_by
            yield dist
            # TODO: check if this new version causes any new reqs!!


def _discover_import_names(whl_file):
    log = logger.bind(whl_file=whl_file)
    logger.debug("finding import names")
    zipfile = ZipFile(file=whl_file)
    namelist = zipfile.namelist()
    try:
        [top_level_fname] = [x for x in namelist if x.endswith("top_level.txt")]
    except ValueError:
        log.debug("top_level absent, trying metadata")
        metadata = _extract_metadata(whl_file)
        try:
            public_names = metadata["python.exports"]["modules"] or []
        except KeyError:
            # this dist was packaged by a dinosaur, exports is not in metadata.
            # we gotta do it the hard way ...
            public_names = []
            for name in namelist:
                if ".dist-info/" not in name and ".egg-info/" not in name:
                    parts = name.split("/")
                    if len(parts) == 2 and parts[1] == "__init__.py":
                        # found a top-level package
                        public_names.append(parts[0])
                    elif len(parts) == 1:
                        # TODO: find or make an exhaustive list of file extensions importable
                        name, ext = os.path.splitext(parts[0])
                        if ext == ".py" or ext == ".so":
                            # found a top level module
                            public_names.append(name)
    else:
        all_names = zipfile.read(top_level_fname).decode("utf-8").strip().splitlines()
        public_names = [n for n in all_names if not n.startswith("_")]
    return public_names


def _extract_metadata(whl_file):
    logger.debug("searching metadata", whl_file=whl_file)
    info = pkginfo.get_metadata(whl_file)
    if info is None:
        raise Exception("failed to get metadata")
    data = {k.lower(): v for k,v in vars(info).items()}
    data.pop("filename", None)
    return data


def has_error(dist):
    if dist.error is not None:
        return True
    return any(has_error(n) for n in dist.children)


@ttl_cache(maxsize=512, ttl=60 * 5)
def _get_info(dist_name, index_url=None, env=None, extra_index_url=None):
    log = logger.bind(dist_name=dist_name)
    tmpdir = mkdtemp()
    log.debug("created scratch", tmpdir=tmpdir)
    try:
        data = pipper.get(
            dist_name,
            index_url=index_url,
            env=env,
            extra_index_url=extra_index_url,
            tmpdir=tmpdir,
        )
        dist_path = data["path"]
        # extract any info we may need from downloaded dist right now, so the
        # downloaded file can be cleaned up immediately
        import_names = _discover_import_names(dist_path)
        metadata = _extract_metadata(dist_path)
    finally:
        log.debug("removing scratch", tmpdir=tmpdir)
        rmtree(tmpdir, ignore_errors=True)
    return import_names, metadata


# TODO: multi-line progress bar?
# TODO: upload test dists to test PyPI index, document pip existing failure modes
# TODO: don't infinitely recurse on circular dep tree
