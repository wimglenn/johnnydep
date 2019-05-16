# coding: utf-8
from __future__ import unicode_literals

import errno
import json
import os
import re
import tempfile
from collections import OrderedDict
from collections import defaultdict
from zipfile import ZipFile

import anytree
import pkg_resources
import pkginfo
import pytoml
import tabulate
import wimpy
from packaging.markers import default_environment
from packaging.utils import canonicalize_name
from packaging.utils import canonicalize_version
from structlog import get_logger
from wheel.wheelfile import WheelFile
from wimpy import cached_property

from johnnydep import pipper
from johnnydep.compat import oyaml

__all__ = ["JohnnyDist", "gen_table", "flatten_deps"]


logger = get_logger(__name__)


class OrderedDefaultListDict(OrderedDict):
    def __missing__(self, key):
        self[key] = value = []
        return value


class JohnnyDist(anytree.NodeMixin):
    def __init__(self, req_string, parent=None, index_url=None, env=None, extra_index_url=None):
        self.dist_path = None
        if req_string.endswith(".whl") and os.path.isfile(req_string):
            self.dist_path = req_string
            whl = WheelFile(req_string)
            whl_name_info = whl.parsed_filename.groupdict()
            self.name = canonicalize_name(whl_name_info["name"])
            self.specifier = "==" + canonicalize_version(whl_name_info["ver"])
            self.req = pkg_resources.Requirement.parse(self.name + self.specifier)
        else:
            self.req = pkg_resources.Requirement.parse(req_string)
            self.name = canonicalize_name(self.req.name)
            self.specifier = str(self.req.specifier)

        self.extras_requested = sorted(self.req.extras)
        log = self.log = logger.bind(dist=str(self.req))
        log.info("init johnnydist", parent=parent and str(parent.req))
        if parent is not None:
            self.index_url = parent.index_url
            self.extra_index_url = parent.extra_index_url
            self.required_by = [str(parent.req)]
            self.env = parent.env
            self.env_data = parent.env_data
        else:
            self.index_url = index_url
            self.extra_index_url = extra_index_url
            self.required_by = []
            self.env = env
            if self.env is None:
                self.env_data = default_environment()
            else:
                self.env_data = dict(self.env)
            log.debug("target env", **self.env_data)
        if self.dist_path is None:
            log.debug("fetching best wheel")
            with wimpy.working_directory(self.tmp()):
                data = pipper.get(
                    req_string,
                    index_url=self.index_url,
                    env=self.env,
                    extra_index_url=self.extra_index_url,
                )
                self.dist_path = data["path"]
        self.parent = parent
        self._recursed = False

    @cached_property
    def import_names(self):
        self.log.debug("finding import names")
        zip = ZipFile(file=self.dist_path)
        namelist = zip.namelist()
        try:
            [top_level_fname] = [x for x in namelist if x.endswith("top_level.txt")]
        except ValueError:
            self.log.debug("top_level absent, trying metadata")
            try:
                public_names = self.metadata["python.exports"]["modules"] or []
            except KeyError:
                # this dist was packaged by a dinosaur, exports is not in metadata.
                # we gotta do it the hard way ...
                public_names = []
                for name in namelist:
                    if ".dist-info/" not in name and ".egg-info/" not in name:
                        parts = name.split(os.sep)
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
            all_names = zip.read(top_level_fname).decode("utf-8").strip().splitlines()
            public_names = [n for n in all_names if not n.startswith("_")]
        return public_names

    @cached_property
    def metadata(self):
        self.log.debug("searching metadata")
        info = pkginfo.get_metadata(self.dist_path)
        if info is None:
            raise Exception("failed to get metadata")
        data = vars(info)
        data.pop("filename", None)
        return data

    @property
    def requires(self):
        """Just the strings (name and spec) for my immediate dependencies. Cheap."""
        all_requires = self.metadata.get("requires_dist", [])
        if not all_requires:
            return []
        result = []
        env = self.env_data
        for req_str in all_requires:
            req = pkg_resources.Requirement.parse(req_str)
            # TODO: find a better way to parse this
            extras = re.findall(r'extra == "(.*?)"', str(req.marker))
            if len(extras) > 1:
                raise Exception("ouch")
            elif len(extras) == 1:
                [extra] = extras
                if extra not in self.extras_requested:
                    self.log.debug("dropped unrequested extra", req=req_str)
                    continue
            req_short, _sep, _markers = str(req).partition(";")
            if not extras:
                if not req.marker:
                    result.append(req_short)
                    continue
                if req.marker.evaluate(env):
                    self.log.debug("included conditional dep", req=req_str)
                    result.append(req_short)
                else:
                    self.log.debug("dropped conditional dep", req=req_str)
                continue
            assert extras
            assert set(extras) <= set(self.extras_requested)
            assert "extra" not in env
            if not req.marker or any(req.marker.evaluate(dict(extra=e, **env)) for e in extras):
                self.log.debug("included requested extra", req=req_str)
                result.append(req_short)
            else:
                self.log.debug("dropped conditional extra", req=req_str)
        result = sorted(set(result))  # this makes the dep tree deterministic/repeatable
        return result

    @property
    def children(self):
        """my immediate deps, as a tuple of johnnydists"""
        if not self._recursed:
            self.log.debug("populating dep tree")
            for dep in self.requires:
                JohnnyDist(req_string=dep, parent=self)
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
        text = self.metadata.get("summary") or self.metadata.get("Summary") or ""
        result = text.lstrip("#").strip()
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

    @classmethod
    def tmp(cls):
        if getattr(cls, "_tmpdir", None) is None:
            tmpdir = os.environ.get("TMPDIR") or tempfile.gettempdir()
            tmpdir = os.path.join(tmpdir, "johnnydep")
            logger.debug("get or create scratch", tmpdir=tmpdir)
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
        )

    @property
    def download_link(self):
        return self._best["url"]

    @property
    def checksum(self):
        return self._best["checksum"]

    def serialise(self, fields=("name", "summary"), recurse=True, format=None):
        if format == "pinned":
            # user-specified fields are ignored/invalid in this case
            fields = ("pinned",)
        data = [OrderedDict([(f, getattr(self, f, None)) for f in fields])]
        if format == "human":
            table = gen_table(self, extra_cols=fields)
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
            result = "\n".join([pytoml.dumps(d) for d in data])
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
    extra_cols = OrderedDict.fromkeys(extra_cols)  # de-dupe and preserve ordering
    extra_cols.pop("name", None)  # this is always included anyway, no need to ask for it
    johnnydist.log.debug("generating table")
    for pre, _fill, node in anytree.RenderTree(johnnydist):
        row = OrderedDict()
        name = str(node.req)
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
        extras = extra_map[name]
        required_by = list(OrderedDict.fromkeys(required_by_map[name]))  # order preserving de-dupe
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
                index_url=dists[0].index_url,
                extra_index_url=dists[0].extra_index_url,
            )
            dist.required_by = required_by
            yield dist
            # TODO: check if this new version causes any new reqs!!


# TODO: multi-line progress bar?
# TODO: upload test dists to test PyPI index, document pip existing failure modes
# TODO: don't infinitely recurse on circular dep tree
