import json
import os
import re
import subprocess
from collections import defaultdict
from functools import cached_property
from importlib.metadata import distribution
from importlib.metadata import PackageNotFoundError
from importlib.metadata import PathDistribution
from shutil import rmtree
from tempfile import mkdtemp
from zipfile import Path as zipfile_path
from zipfile import ZipFile

import anytree
import tabulate
import toml
import yaml
from cachetools.func import ttl_cache
from packaging import requirements
from packaging.markers import default_environment
from packaging.utils import canonicalize_name
from packaging.utils import canonicalize_version
from packaging.version import parse as parse_version
from structlog import get_logger

from johnnydep import pipper
from johnnydep.dot import jd2dot
from johnnydep.util import CircularMarker

__all__ = ["JohnnyDist", "gen_table", "flatten_deps", "has_error", "JohnnyError"]


logger = get_logger(__name__)


class JohnnyError(Exception):
    pass


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
            self.req = requirements.Requirement(self.name + sep + extras + self.specifier)
            self.import_names = _discover_import_names(fname)
            self.metadata = _extract_metadata(fname)
            self.entry_points = _discover_entry_points(fname)
            self._from_fname = os.path.abspath(fname)
        else:
            self._from_fname = None
            self.req = requirements.Requirement(req_string)
            self.name = canonicalize_name(self.req.name)
            self.specifier = str(self.req.specifier)
            log.debug("fetching best wheel")
            try:
                self.import_names, self.metadata, self.entry_points = _get_info(
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
                self.entry_points = None
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
            req = requirements.Requirement(req_str)
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
            circular_deps = _detect_circular(self)
            if circular_deps:
                chain = " -> ".join([d._name_with_extras() for d in circular_deps])
                summary = f"... <circular dependency marker for {chain}>"
                self.log.info("pruning circular dependency", chain=chain)
                _dep = CircularMarker(summary=summary, parent=self)
            else:
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
        for project_url in self.metadata.get("project_url", []):
            if project_url.lower().startswith("homepage, "):
                _, url = project_url.split(", ", 1)
                return url
        try:
            return self.metadata["home_page"]
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
        for classifier in self.metadata.get("classifier", []):
            if classifier.startswith("License :: "):
                crap, result = classifier.rsplit(" :: ", 1)
                break
        if not result:
            self.log.info("unknown license")
        return result

    @cached_property
    def versions_available(self):
        result = pipper.get_versions(
            self.project_name,
            index_url=self.index_url,
            env=self.env,
            extra_index_url=self.extra_index_url,
        )
        if self._from_fname is not None:
            raw_version = os.path.basename(self._from_fname).split("-")[1]
            local_version = canonicalize_version(raw_version)
            version_key = parse_version(local_version)
            if local_version not in result:
                # when we're Python 3.10+ only, can use bisect.insort instead here
                i = 0
                for i, v in enumerate(result):
                    if version_key < parse_version(v):
                        break
                result.insert(i, local_version)
        return result

    @cached_property
    def version_installed(self):
        self.log.debug("checking if installed already")
        try:
            dist = distribution(self.name)
        except PackageNotFoundError:
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
        extras = {x for x in self.metadata.get("provides_extra", []) if x}
        for req_str in self.metadata.get("requires_dist", []):
            req = requirements.Requirement(req_str)
            extras |= set(re.findall(r"""extra == ['"](.*?)['"]""", str(req.marker)))
        return sorted(extras)

    @property
    def project_name(self):
        return self.metadata.get("name", self.name)

    @property
    def console_scripts(self):
        eps = [ep for ep in self.entry_points or [] if ep.group == "console_scripts"]
        return [f"{ep.name} = {ep.value}" for ep in eps]

    @property
    def pinned(self):
        if self.extras_requested:
            extras = f"[{','.join(self.extras_requested)}]"
        else:
            extras = ""
        version = self.version_latest_in_spec
        if version is None:
            raise JohnnyError("Can not pin because no version available is in spec")
        result = f"{self.project_name}{extras}=={version}"
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
        if self._from_fname is not None:
            return f"file://{self._from_fname}"
        return self._best.get("url")

    @property
    def checksum(self):
        if self._from_fname is not None:
            md5 = pipper.compute_checksum(self._from_fname, algorithm="md5")
            return f"md5={md5}"
        return self._best.get("checksum")

    def serialise(self, fields=("name", "summary"), recurse=True, format=None):
        if format == "pinned":
            # user-specified fields are ignored/invalid in this case
            fields = ("pinned",)
        if format == "dot":
            return jd2dot(self)
        data = [{f: getattr(self, f, None) for f in fields}]
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
            result = yaml.safe_dump(data, sort_keys=False)
        elif format == "toml":
            result = "\n".join([toml.dumps(d) for d in data])
        elif format == "pinned":
            result = "\n".join([d["pinned"] for d in data])
        else:
            raise JohnnyError("Unsupported format")
        return result

    serialize = serialise

    def _name_with_extras(self, attr="name"):
        result = getattr(self, attr)
        if self.extras_requested:
            result += f"[{','.join(self.extras_requested)}]"
        return result

    def _repr_pretty_(self, p, cycle):
        # hook for IPython's pretty-printer
        if cycle:
            p.text(repr(self))
        else:
            fullname = self._name_with_extras() + self.specifier
            p.text(f"<{type(self).__name__} {fullname} at {hex(id(self))}>")


def gen_table(johnnydist, extra_cols=()):
    extra_cols = {}.fromkeys(extra_cols)  # de-dupe and preserve ordering
    extra_cols.pop("name", None)  # this is always included anyway, no need to ask for it
    johnnydist.log.debug("generating table")
    for prefix, _fill, dist in anytree.RenderTree(johnnydist):
        row = {}
        txt = str(dist.req)
        if dist.error:
            txt += " (FAILED)"
        if "specifier" in extra_cols:
            # can use https://docs.python.org/3/library/stdtypes.html#str.removesuffix
            # after dropping support for Python-3.8
            suffix = str(dist.specifier)
            if txt.endswith(suffix):
                txt = txt[:len(txt) - len(suffix)]
        row["name"] = prefix + txt
        for col in extra_cols:
            val = getattr(dist, col, "")
            if isinstance(val, list):
                val = ", ".join(val)
            row[col] = val
        yield row


def _detect_circular(dist):
    # detects a circular dependency when traversing from here to the root node, and returns
    # a chain of nodes in that case
    chain = [dist]
    for ancestor in reversed(dist.ancestors):
        chain.append(ancestor)
        if ancestor.name == dist.name:
            if ancestor.extras_requested == dist.extras_requested:
                return chain[::-1]


def flatten_deps(johnnydist):
    johnnydist.log.debug("resolving dep tree")
    dist_map = defaultdict(list)
    spec_map = defaultdict(str)
    extra_map = defaultdict(set)
    required_by_map = defaultdict(list)
    for dep in anytree.iterators.LevelOrderIter(johnnydist):
        if dep.name == CircularMarker.glyph:
            continue
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
            v = dist.version_latest_in_spec
            if v is None:
                msg = "Could not find satisfactory version for {}{}"
                raise JohnnyError(msg.format(dist.name, dist.specifier))
            if v in spec and set(dist.extras_requested) >= extras:
                dist.required_by = required_by
                johnnydist.log.info(
                    "resolved",
                    name=dist.name,
                    required_by=required_by,
                    v=v,
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
    log.debug("finding import names")
    zf = ZipFile(file=whl_file)
    namelist = zf.namelist()
    try:
        [top_level_fname] = [x for x in namelist if x.endswith("top_level.txt")]
    except ValueError:
        log.debug("top_level.txt absent, iterating contents")
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
        all_names = zf.read(top_level_fname).decode("utf-8").strip().splitlines()
        public_names = [n for n in all_names if not n.startswith("_")]
    result = [n.replace("/", ".") for n in public_names]
    return result


def _path_dist(whl_file):
    parts = os.path.basename(whl_file).split("-")
    metadata_path = "-".join(parts[:2]) + ".dist-info/"
    zf_path = zipfile_path(whl_file, metadata_path)
    return PathDistribution(zf_path)


def _discover_entry_points(whl_file):
    log = logger.bind(whl_file=whl_file)
    log.debug("finding entry points")
    path_dist = _path_dist(whl_file)
    return path_dist.entry_points


def _extract_metadata(whl_file):
    log = logger.bind(whl_file=whl_file)
    log.debug("finding metadata", whl_file=whl_file)
    path_dist = _path_dist(whl_file)
    message = path_dist.metadata
    try:
        result = message.json
    except AttributeError:
        # older python
        multiple_use_keys = {
            "Classifier",
            "Platform",
            "Requires-External",
            "Obsoletes-Dist",
            "Supported-Platform",
            "Provides-Dist",
            "Requires-Dist",
            "Project-URL",
            "Provides-Extra",
            "Dynamic",
        }
        result = {}
        # https://peps.python.org/pep-0566/#json-compatible-metadata
        for orig_key in message.keys():
            k = orig_key.lower().replace("-", "_")
            if k in result:
                continue
            if orig_key in multiple_use_keys:
                result[k] = message.get_all(orig_key)
            else:
                result[k] = message[orig_key]
        if "description" not in result:
            payload = message.get_payload()
            if payload:
                result["description"] = payload
    return result


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
        entry_points = _discover_entry_points(dist_path)
    finally:
        log.debug("removing scratch", tmpdir=tmpdir)
        rmtree(tmpdir, ignore_errors=True)
    return import_names, metadata, entry_points


# TODO: multi-line progress bar?
# TODO: upload test dists to test PyPI index, document pip existing failure modes
