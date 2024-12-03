import hashlib
import io
import json
import re
import subprocess
import sys
from collections import defaultdict
from collections import deque
from dataclasses import dataclass
from functools import cached_property
from importlib.metadata import distribution
from importlib.metadata import PackageNotFoundError
from importlib.metadata import PathDistribution
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from textwrap import dedent
from urllib.parse import urlparse
from zipfile import Path as zipfile_path
from zipfile import ZipFile

import rich.box
import rich.markup
import tomli_w
import unearth
import yaml
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.tags import parse_tag
from packaging.utils import canonicalize_name
from packaging.utils import canonicalize_version
from packaging.version import Version
from rich.table import Table
from rich.tree import Tree
from structlog import get_logger

from .dot import jd2dot
from .downloader import download_dist
from .util import _bfs
from .util import _un_none
from .util import CircularMarker
from .util import lru_cache_ttl

__all__ = ["JohnnyDist", "gen_table", "gen_tree", "flatten_deps", "has_error", "JohnnyError"]

logger = get_logger(__name__)


class JohnnyError(Exception):
    pass


def get_or_create(req_string):
    pass


class JohnnyDist:
    def __init__(self, req_string, parent=None, index_urls=(), env=None, ignore_errors=False):
        if isinstance(req_string, Path):
            req_string = str(req_string)
        log = self.log = logger.bind(dist=req_string)
        log.info("init johnnydist", parent=parent and str(parent.req))
        self._children = None
        self.parents = []
        if parent is not None:
            self.parents.append(parent)
        self._ignore_errors = ignore_errors
        self.error = None
        self.checksum = None
        self.import_names = None
        self.metadata = {}
        self.entry_points = None
        self._index_urls = index_urls
        self._env = env

        fname, sep, extras = req_string.partition("[")
        if fname.endswith(".whl") and Path(fname).is_file():
            # crudely parse dist name and version from wheel filename
            # see https://peps.python.org/pep-0427/#file-name-convention
            name, version, *rest = Path(fname).name.split("-")
            self.name = canonicalize_name(name)
            self.specifier = "==" + canonicalize_version(version)
            self.req = Requirement(self.name + sep + extras + self.specifier)
            self.import_names = _discover_import_names(fname)
            self.metadata = _extract_metadata(fname)
            self.entry_points = _discover_entry_points(fname)
            self._local_path = Path(fname).resolve()
            self.checksum = "sha256=" + hashlib.sha256(self._local_path.read_bytes()).hexdigest()
        else:
            self._local_path = None
            self.req = Requirement(req_string)
            self.name = canonicalize_name(self.req.name)
            self.specifier = str(self.req.specifier)
            log.debug("fetching best wheel")
            try:
                info = _get_info(self.req, self._index_urls, self._env)
            except Exception as err:
                if not self._ignore_errors:
                    raise
                self.error = err
            else:
                self.import_names = info.import_names
                self.metadata = info.metadata
                self.entry_points = info.entry_points
                self.checksum = "sha256=" + info.sha256

        self.extras_requested = sorted(self.req.extras)
        if parent is None:
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
        for req_str in all_requires:
            req = Requirement(req_str)
            req_short, _sep, _marker = str(req).partition(";")
            if req.marker is None:
                # unconditional dependency
                result.append(req_short)
                continue
            # conditional dependency - must be evaluated in environment context
            for extra in [None] + self.extras_requested:
                if req.marker.evaluate(dict(self._env or default_environment(), extra=extra)):
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
        if self._children is None:
            self._children = []
            self.log.debug("populating dep graph")
            circular_deps = _detect_circular(self)
            if circular_deps:
                chain = " -> ".join([d._name_with_extras() for d in circular_deps])
                summary = f"... <circular dependency marker for {chain}>"
                self.log.info("pruning circular dependency", chain=chain)
                _dep = CircularMarker(summary=summary, parent=self)
                self._children = [_dep]
            else:
                for dep in self.requires:
                    child = JohnnyDist(
                        req_string=dep,
                        parent=self,
                        index_urls=self._index_urls,
                        env=self._env,
                        ignore_errors=self._ignore_errors,
                    )
                    self._children.append(child)
        return self._children

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
        versions = _get_versions(self.req, self._index_urls, self._env)
        if self._local_path is not None:
            raw_version = self._local_path.name.split("-")[1]
            local_version = canonicalize_version(raw_version)
            version_key = Version(local_version)
            if local_version not in versions:
                # when we're Python 3.10+ only, can use bisect.insort instead here
                i = 0
                for i, v in enumerate(versions):
                    if version_key < Version(v):
                        break
                versions.insert(i, local_version)
        return versions

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
            req = Requirement(req_str)
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

    @property
    def download_link(self):
        if self._local_path is not None:
            return f"file://{self._local_path}"
        link = _get_link(self.req, self._index_urls, self._env)
        if link is not None:
            return link.url

    def serialise(self, fields=("name", "summary"), recurse=True, format=None):
        if format == "pinned":
            # user-specified fields are ignored/invalid in this case
            fields = ("pinned",)
        if format == "dot":
            return jd2dot(self)
        data = [{f: getattr(self, f, None) for f in fields}]
        if format == "human":
            cols = dict.fromkeys(fields)
            cols.pop("name", None)
            with_specifier = "specifier" not in cols
            if recurse:
                tree = gen_tree(self, with_specifier=with_specifier)
            else:
                tree = Tree(_to_str(self, with_specifier))
                tree.dist = self
            table = gen_table(tree, cols=cols)
            buf = io.StringIO()
            rich.print(table, file=buf)
            raw = buf.getvalue()
            stripped = "\n".join([x.rstrip() for x in raw.splitlines() if x.strip()])
            result = dedent(stripped)
            return result
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
            options = {}
            can_indent = Version(tomli_w.__version__) >= Version("1.1.0")
            if can_indent:
                options["indent"] = 2
            result = "\n".join([tomli_w.dumps(_un_none(d), **options) for d in data])
            if not can_indent:
                result = re.sub(r"^    ", "  ", result, flags=re.MULTILINE)
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


def _to_str(dist, with_specifier=True):
    txt = str(dist.req)
    if dist.error:
        txt += " (FAILED)"
    if not with_specifier:
        # can use https://docs.python.org/3/library/stdtypes.html#str.removesuffix
        # after dropping support for Python-3.8
        suffix = str(dist.specifier)
        if txt.endswith(suffix):
            txt = txt[:len(txt) - len(suffix)]
    return rich.markup.escape(txt)


def gen_tree(johnnydist, with_specifier=True):
    johnnydist.log.debug("generating tree")
    seen = set()
    tree = Tree(_to_str(johnnydist, with_specifier))
    tree.dist = johnnydist
    q = deque([tree])
    while q:
        node = q.popleft()
        jd = node.dist
        pk = id(jd)
        if pk in seen:
            continue
        seen.add(pk)
        for child in jd.children:
            tchild = node.add(_to_str(child, with_specifier))
            tchild.dist = child
            q.append(tchild)
    return tree


def gen_table(tree, cols):
    table = Table(box=rich.box.SIMPLE)
    table.add_column("name", overflow="fold")
    for col in cols:
        table.add_column(col, overflow="fold")
    rows = []
    stack = [tree]
    while stack:
        node = stack.pop()
        rows.append(node)
        stack += reversed(node.children)
    buf = io.StringIO()
    rich.print(tree, file=buf)
    tree_lines = buf.getvalue().splitlines()
    for row0, row in zip(tree_lines, rows):
        data = [getattr(row.dist, c) for c in cols]
        for i, d in enumerate(data):
            if d is None:
                data[i] = ""
            elif not isinstance(d, str):
                data[i] = ", ".join(map(str, d))
        escaped = [rich.markup.escape(x) for x in [row0, *data]]
        table.add_row(*escaped)
    return table


def _detect_circular(dist):
    # detects a circular dependency when traversing from here to the root node, and returns
    # a chain of nodes in that case
    # TODO: fix this for full DAG
    dist0 = dist
    chain = [dist]
    while dist.parents:
        [dist] = dist.parents
        chain.append(dist)
        if dist.name == dist0.name and dist.extras_requested == dist0.extras_requested:
            return chain[::-1]


def flatten_deps(johnnydist):
    johnnydist.log.debug("resolving dep graph")
    dist_map = defaultdict(list)
    spec_map = defaultdict(str)
    extra_map = defaultdict(set)
    required_by_map = defaultdict(list)
    for dep in _bfs(johnnydist):
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
                msg = f"Could not find satisfactory version for {dist.name}{dist.specifier}"
                raise JohnnyError(msg)
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
            if extras:
                extra = f"[{','.join(sorted(extras))}]"
            else:
                extra = ""
            dist = JohnnyDist(
                req_string=f"{name}{extra}{spec}",
                index_urls=johnnydist._index_urls,
                env=johnnydist._env,
                ignore_errors=johnnydist._ignore_errors,
            )
            # TODO: set parents
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
                elif len(parts) == 1 and name.endswith((".py", ".so", ".pyd")):
                    # found a top level module
                    public_names.append(name.split(".")[0])
    else:
        all_names = zf.read(top_level_fname).decode("utf-8").strip().splitlines()
        public_names = [n for n in all_names if not n.startswith("_")]
    result = [n.replace("/", ".") for n in public_names]
    return result


def _path_dist(whl_file):
    parts = Path(whl_file).name.split("-", maxsplit=2)
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


def _get_package_finder(index_urls, env):
    trusted_hosts = ()
    for index_url in index_urls:
        host = urlparse(index_url).hostname
        if host != "pypi.org":
            trusted_hosts += (host,)
    target_python = None
    if env is not None:
        envd = dict(env)
        target_python = unearth.TargetPython(
            py_ver=envd["py_ver"],
            impl=envd["impl"],
        )
        valid_tags = []
        for tag in envd["supported_tags"].split(","):
            valid_tags.extend(parse_tag(tag))
        target_python._valid_tags = valid_tags
    package_finder = unearth.PackageFinder(
        index_urls=index_urls,
        target_python=target_python,
        trusted_hosts=trusted_hosts,
    )
    return package_finder


@lru_cache_ttl()
def _get_packages(project_name: str, index_urls: tuple, env: tuple):
    finder = _get_package_finder(index_urls, env)
    seq = finder.find_all_packages(project_name, allow_yanked=True)
    result = list(seq)
    return result


def _get_versions(req: Requirement, index_urls: tuple, env: tuple):
    packages = _get_packages(req.name, index_urls, env)
    versions = {p.version for p in packages}
    versions = sorted(versions, key=Version)
    return versions


def _get_link(req: Requirement, index_urls: tuple, env: tuple):
    packages = _get_packages(req.name, index_urls, env)
    ok = (p for p in packages if req.specifier.contains(p.version, prereleases=True))
    best = next(ok, None)
    if best is not None:
        return best.link


@dataclass
class _Info:
    import_names: list
    metadata: dict
    entry_points: list
    sha256: str


@lru_cache_ttl()
def _get_info(req: Requirement, index_urls: tuple, env: tuple):
    log = logger.bind(req=str(req))
    link = _get_link(req, index_urls, env)
    if link is None:
        raise JohnnyError(f"Package not found {str(req)!r}")
    tmpdir = mkdtemp()
    log.debug("created scratch", tmpdir=tmpdir)
    try:
        dist_path = Path(tmpdir) / link.filename
        with dist_path.open("wb") as f:
            download_dist(url=link.url, f=f, index_urls=index_urls)
        sha256 = hashlib.sha256(dist_path.read_bytes()).hexdigest()
        if link.hashes is not None and link.hashes.get("sha256", sha256) != sha256:
            raise JohnnyError("checksum mismatch")
        if not dist_path.name.endswith("whl"):
            args = [sys.executable, "-m", "uv", "build", "--wheel", str(dist_path)]
            subprocess.run(args, capture_output=True, check=True)
            [dist_path] = dist_path.parent.glob("*.whl")
        # extract any info we may need from downloaded dist right now, so the
        # downloaded file can be cleaned up immediately
        import_names = _discover_import_names(dist_path)
        metadata = _extract_metadata(dist_path)
        entry_points = _discover_entry_points(dist_path)
    finally:
        log.debug("removing scratch", tmpdir=tmpdir)
        rmtree(tmpdir, ignore_errors=True)
    result = _Info(import_names, metadata, entry_points, sha256)
    return result
