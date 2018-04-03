#!/usr/bin/env python
# coding: utf-8
from __future__ import print_function
from __future__ import unicode_literals

import glob
import hashlib
import json
import logging
import os
import sys
from argparse import ArgumentParser

import pip
import testfixtures
from cachetools.func import ttl_cache
from packaging.utils import canonicalize_name
from pip._internal.commands.wheel import WheelCommand
from pip._internal.download import PipSession
from pip._internal.exceptions import DistributionNotFound
from pip._internal.index import PackageFinder
from pip._internal.req.req_install import InstallRequirement
from pip._internal.req.req_install import Requirement
from structlog import get_logger

log = get_logger(__name__)


DEFAULT_INDEX = "https://pypi.org/simple/"


def compute_checksum(target, algorithm="sha256", blocksize=2 ** 13):
    hashtype = getattr(hashlib, algorithm)
    hash_ = hashtype()
    log.info("computing checksum", target=target, algorithm=algorithm)
    with open(target, "rb") as f:
        for chunk in iter(lambda: f.read(blocksize), b""):
            hash_.update(chunk)
    result = hash_.hexdigest()
    log.debug("computed checksum", result=result)
    return result


@ttl_cache(maxsize=512, ttl=60 * 5)
def get_versions(dist_name, index_url=DEFAULT_INDEX):
    bare_name = Requirement(dist_name).name
    log.debug("checking versions available", dist=bare_name)
    wheel_cmd = WheelCommand()
    wheel_args = [
        "--no-deps",
        "--no-cache-dir",
        "--index-url",
        index_url,
        bare_name + "==showmethemoney",
    ]
    options, args = wheel_cmd.parse_args(wheel_args)
    with testfixtures.LogCapture(level=logging.INFO) as log_capture, testfixtures.OutputCapture():
        try:
            wheel_cmd.run(options, args)
        except DistributionNotFound:
            # expected.  we forced this by using a non-existing version number.
            pass
    msg = "Could not find a version that satisfies the requirement %s (from versions: %s)"
    record = next(r for r in reversed(log_capture.records) if r.msg == msg)
    _install_requirement, versions = record.args
    return versions


@ttl_cache(maxsize=512, ttl=60 * 5)
def get_link(dist_name, index_url=DEFAULT_INDEX):
    install_req = InstallRequirement.from_req(req=dist_name, comes_from=None)
    with PipSession(retries=5) as session:
        finder = PackageFinder(find_links=(), index_urls=[index_url], session=session)
        result = finder.find_requirement(install_req, upgrade=True)
    url, sep, checksum = result.url.partition("#")
    assert url == result.url_without_fragment
    data = {"url": url, "checksum": checksum or None}  # hashtype=srchash
    return data


def get(dist_name, index_url=DEFAULT_INDEX):
    wheel_cmd = WheelCommand()
    wheel_args = [
        "--no-deps",
        "--no-cache-dir",
        "--index-url",
        index_url,
        "--progress-bar=off",
        dist_name,
    ]
    options, args = wheel_cmd.parse_args(wheel_args)
    log.debug("wheeling and dealing", cmd=" ".join(wheel_args))
    log_capture = testfixtures.LogCapture(level=logging.INFO)
    output_capture = testfixtures.OutputCapture()
    try:
        with log_capture, output_capture:
            wheel_cmd.run(options, args)
    except Exception:
        for record in log_capture.records:
            log.debug(record.msg % record.args)
        if output_capture.captured.strip():
            log.debug(output_capture.captured)
        raise
    log.debug("wheel command completed ok")
    install_req = whl = url = checksum = collected_name = None
    for record in log_capture.records:
        if record.msg == "Collecting %s":
            [install_req] = record.args
            url, _fragment, checksum = install_req.link.url.partition("#")
        elif record.msg == "File was already downloaded %s":
            [whl] = record.args
        elif record.msg == "Saved %s":
            [whl_rel] = record.args
            whl = os.path.realpath(whl_rel)
        elif record.msg == "Building wheels for collected packages: %s":
            # only sdist was avail :(  this is annoying .. have to dig around to find the .whl
            # it's not easy, because the filename is case sensitive but the req name isn't
            [collected_name] = record.args
        elif record.msg == "Successfully built %s" and (collected_name,) == record.args:
            whls = glob.glob("*.whl")
            whl = max(whls, key=lambda whl: os.stat(whl).st_mtime)
            required_spec = Requirement(dist_name).specifier
            name, version, the_rest = os.path.basename(whl).split("-", 2)
            name_match = canonicalize_name(name) == canonicalize_name(install_req.req.name)
            if not name_match or version not in required_spec:
                # wat - the most recently modified wheel is not up to spec?  I think this can never happen ...
                raise Exception("Something strange happened")
    if None in {whl, url, checksum}:
        log.warning("failed to get a wheel", dist=dist_name)
        for record in log_capture.records:
            log.debug("captured logs", msg=record.msg, args=record.args)
        if output_capture.captured.strip():
            log.debug("captured output", out=output_capture.captured)
        raise Exception("No .whl")
    if ".cache/pip/wheels" in url:
        # wat? using --no-cache-dir should have prevented this possibility
        raise Exception("url is cached ... fixme")
    if not checksum:
        # this can happen, for example, if wheel dug a file out of the pip cache instead of downloading it
        # the wheel cache (~/.cache/pip/wheels/) directory structure is no good for us here, that's a sha224
        # of the download link, not a proper content checksum. so let's just compute the checksum clientside.
        md5 = compute_checksum(whl, algorithm="md5")
        checksum = "md5={}".format(md5)
    msg = "built wheel from source" if collected_name is not None else "found existing wheel"
    log.info(msg, url=url, checksum=checksum)
    whl = os.path.abspath(whl)
    result = {"path": whl, "url": url, "checksum": checksum}
    return result


def main():
    parser = ArgumentParser()
    parser.add_argument("dist_name")
    parser.add_argument("--index-url", default=DEFAULT_INDEX)
    parser.add_argument("-v", "--verbose", action="store_true")
    debug = {
        "sys.argv": sys.argv,
        "sys.executable": sys.executable,
        "sys.version": sys.version,
        "sys.path": sys.path,
        "pip.__version__": pip.__version__,
        "pip.__file__": pip.__file__,
    }
    args = parser.parse_args()
    # logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)
    # log.debug(str(debug))
    result = get(dist_name=args.dist_name, index_url=args.index_url)
    print(json.dumps(result, indent=2, sort_keys=True, separators=(",", ": ")))


if __name__ == "__main__":
    main()


"""
TODO: do this smarter

from pip.download import PipSession
from pip.req.req_install import InstallRequirement
import johnnydep.lib

with PipSession() as s:
    p = pip.index.PackageFinder(find_links=[], index_urls=[johnnydep.lib.DEFAULT_INDEX], session=s)
    r = InstallRequirement.from_line('oyaml')
    r.populate_link(finder=p, upgrade=False, require_hashes=True)
"""
