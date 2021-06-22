#!/usr/bin/env python
# coding: utf-8
from __future__ import print_function
from __future__ import unicode_literals

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from argparse import ArgumentParser
from collections import OrderedDict
from glob import glob

import pip
import pkg_resources
from cachetools import cached
from cachetools.func import ttl_cache
from cachetools.keys import hashkey
from cachetools.ttl import TTLCache
from structlog import get_logger

from johnnydep.compat import urlparse, urlretrieve
from johnnydep.logs import configure_logging
from johnnydep.util import python_interpreter

log = get_logger(__name__)


DEFAULT_INDEX = "https://pypi.org/simple/"


def compute_checksum(target, algorithm="sha256", blocksize=2 ** 13):
    hashtype = getattr(hashlib, algorithm)
    hash_ = hashtype()
    log.debug("computing checksum", target=target, algorithm=algorithm)
    with open(target, "rb") as f:
        for chunk in iter(lambda: f.read(blocksize), b""):
            hash_.update(chunk)
    result = hash_.hexdigest()
    log.debug("computed checksum", result=result)
    return result


def _get_wheel_args(index_url, env, extra_index_url):
    args = [
        sys.executable,
        "-m",
        "pip",
        "wheel",
        "-vvv",  # --verbose x3
        "--no-deps",
        "--no-cache-dir",
        "--disable-pip-version-check",
    ]
    if index_url is not None:
        args += ["--index-url", index_url]
        if index_url != DEFAULT_INDEX:
            args += ["--trusted-host", urlparse(index_url).hostname]
    if extra_index_url is not None:
        args += ["--extra-index-url", extra_index_url, "--trusted-host", urlparse(extra_index_url).hostname]
    if env is None:
        pip_version = pip.__version__
    else:
        pip_version = dict(env)["pip_version"]
        args[0] = dict(env)["python_executable"]
    pip_major, pip_minor = pip_version.split(".")[0:2]
    pip_major = int(pip_major)
    pip_minor = int(pip_minor)
    if pip_major >= 10:
        args.append("--progress-bar=off")
    if (pip_major, pip_minor) >= (20, 3):
        # See https://github.com/pypa/pip/issues/9139#issuecomment-735443177
        args.append("--use-deprecated=legacy-resolver")
    return args


def _download_dist(url, scratch_file, index_url, extra_index_url):
    auth = None
    if index_url:
        parsed = urlparse(index_url)
        if parsed.username and parsed.password and parsed.hostname == urlparse(url).hostname:
            # handling private PyPI credentials in index_url
            auth = (parsed.username, parsed.password)
    if extra_index_url:
        parsed = urlparse(extra_index_url)
        if parsed.username and parsed.password and parsed.hostname == urlparse(url).hostname:
            # handling private PyPI credentials in extra_index_url
            auth = (parsed.username, parsed.password)
    target, _headers = urlretrieve(url, scratch_file, auth=auth)
    return target, _headers


@ttl_cache(maxsize=512, ttl=60 * 5)
def get_versions(dist_name, index_url=None, env=None, extra_index_url=None):
    bare_name = pkg_resources.Requirement.parse(dist_name).name
    log.debug("checking versions available", dist=bare_name)
    args = _get_wheel_args(index_url, env, extra_index_url) + [dist_name + "==showmethemoney"]
    try:
        out = subprocess.check_output(args, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as err:
        # expected. we forced this by using a non-existing version number.
        out = getattr(err, "output", b"")
    else:
        log.warning(out)
        raise Exception("Unexpected success:" + " ".join(args))
    out = out.decode("utf-8")
    lines = []
    msg = "Could not find a version that satisfies the requirement"
    for line in out.splitlines():
        if msg in line:
            lines.append(line)
    try:
        [line] = lines
    except ValueError:
        log.warning("failed to get versions", stdout=out)
        raise
    prefix = "(from versions: "
    start = line.index(prefix) + len(prefix)
    stop = line.rfind(")")
    versions = line[start:stop].split(",")
    versions = [v.strip() for v in versions if v.strip()]
    log.debug("found versions", dist=bare_name, versions=versions)
    return versions


def _cache_key(dist_name, index_url=None, env=None, extra_index_url=None, tmpdir=None):
    return hashkey(dist_name, index_url, env, extra_index_url)


# this decoration is a bit more complicated in order to avoid keying of tmpdir
# see https://github.com/tkem/cachetools/issues/146
_get_cache = TTLCache(maxsize=512, ttl=60 * 5)


@cached(_get_cache, key=_cache_key)
def get(dist_name, index_url=None, env=None, extra_index_url=None, tmpdir=None):
    args = _get_wheel_args(index_url, env, extra_index_url) + [dist_name]
    scratch_dir = tempfile.mkdtemp(dir=tmpdir)
    log.debug("wheeling and dealing", scratch_dir=os.path.abspath(scratch_dir), args=" ".join(args))
    try:
        out = subprocess.check_output(args, stderr=subprocess.STDOUT, cwd=scratch_dir)
    except subprocess.CalledProcessError as err:
        output = getattr(err, "output", b"").decode("utf-8")
        log.warning(output)
        raise
    log.debug("wheel command completed ok", dist_name=dist_name)
    out = out.decode("utf-8")
    links = []
    lines = out.splitlines()
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith("Downloading from URL "):
            parts = line.split()
            link = parts[3]
            links.append(link)
        elif line.startswith("Downloading "):
            parts = line.split()
            last = parts[-1]
            if len(parts) == 3 and last.startswith("(") and last.endswith(")"):
                link = parts[-2]
            elif len(parts) == 4 and parts[-2].startswith("(") and last.endswith(")"):
                link = parts[-3]
                if not urlparse(link).scheme:
                    # newest pip versions have changed to not log the full url
                    # in the download event. it is becoming more and more annoying
                    # to preserve compatibility across a wide range of pip versions
                    next_line = lines[i + 1].strip()
                    if next_line.startswith("Added ") and " to build tracker" in next_line:
                        link = next_line.split(" to build tracker")[0].split()[-1]
            else:
                link = last
            links.append(link)
        elif line.startswith("Source in ") and "which satisfies requirement" in line:
            link = line.split()[-1]
            links.append(link)
    links = list(OrderedDict.fromkeys(links))  # order-preserving dedupe
    if not links:
        log.warning("could not find download link", out=out)
        raise Exception("failed to collect dist")
    if len(links) == 2:
        # sometimes we collect the same link, once with a url fragment/checksum and once without
        first, second = links
        if first.startswith(second):
            del links[1]
        elif second.startswith(first):
            del links[0]
    if len(links) > 1:
        log.debug("more than 1 link collected", out=out, links=links)
        # Since PEP 517, maybe an sdist will also need to collect other distributions
        # for the build system, even with --no-deps specified. pendulum==1.4.4 is one
        # example, which uses poetry and doesn't publish any python37 wheel to PyPI.
        # However, the dist itself should still be the first one downloaded.
    link = links[0]
    whls = glob(os.path.join(os.path.abspath(scratch_dir), "*.whl"))
    [whl] = whls
    url, _sep, checksum = link.partition("#")
    url = url.replace("/%2Bf/", "/+f/")  # some versions of pip did not unquote this fragment in the log
    if not checksum.startswith("md5=") and not checksum.startswith("sha256="):
        # PyPI gives you the checksum in url fragment, as a convenience. But not all indices are so kind.
        algorithm = "md5"
        if os.path.basename(whl) == url.rsplit("/")[-1]:
            target = whl
        else:
            scratch_file = os.path.join(scratch_dir, os.path.basename(url))
            target, _headers = _download_dist(url, scratch_file, index_url, extra_index_url)
        checksum = compute_checksum(target=target, algorithm=algorithm)
        checksum = "=".join([algorithm, checksum])
    result = {"path": whl, "url": url, "checksum": checksum}
    return result


def main():
    parser = ArgumentParser()
    parser.add_argument("dist_name")
    parser.add_argument("--index-url", "-i")
    parser.add_argument("--extra-index-url")
    parser.add_argument("--for-python", "-p", dest="env", type=python_interpreter)
    parser.add_argument("--verbose", "-v", default=1, type=int, choices=range(3))
    debug = {
        "sys.argv": sys.argv,
        "sys.executable": sys.executable,
        "sys.version": sys.version,
        "sys.path": sys.path,
        "pip.__version__": pip.__version__,
        "pip.__file__": pip.__file__,
    }
    args = parser.parse_args()
    configure_logging(verbosity=args.verbose)
    log.debug("runtime info", **debug)
    result = get(dist_name=args.dist_name, index_url=args.index_url, env=args.env, extra_index_url=args.extra_index_url)
    text = json.dumps(result, indent=2, sort_keys=True, separators=(",", ": "))
    print(text)


if __name__ == "__main__":
    main()
