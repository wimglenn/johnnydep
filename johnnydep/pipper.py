#!/usr/bin/env python
from __future__ import unicode_literals, print_function

import glob
import hashlib
import json
import logging
import os
import sys
from argparse import ArgumentParser

import pip
from pip.exceptions import DistributionNotFound
from pip.index import canonicalize_name
from pip.req.req_install import Requirement
from structlog import get_logger
from testfixtures import LogCapture
from testfixtures import OutputCapture
from testfixtures import Replace

log = get_logger(__name__)


DEFAULT_INDEX = 'https://pypi.python.org/simple/'


def compute_checksum(target, algorithm='sha256', blocksize=2**13):
    hashtype = getattr(hashlib, algorithm)
    hash_ = hashtype()
    log.info('computing checksum', target=target, algorithm=algorithm)
    with open(target, 'rb') as f:
        for chunk in iter(lambda: f.read(blocksize), b''):
            hash_.update(chunk)
    result = hash_.hexdigest()
    log.debug('computed checksum', result=result)
    return result


def get_versions(dist_name, index_url=DEFAULT_INDEX):
    bare_name = Requirement(dist_name).name
    log.debug('checking versions available', dist=bare_name)
    wheel_cmd = pip.commands.wheel.WheelCommand()
    wheel_args = ['--no-deps', '--no-cache-dir', '--index-url', index_url, bare_name + '==showmethemoney']
    options, args = wheel_cmd.parse_args(wheel_args)
    with LogCapture(level=logging.INFO) as log_capture, OutputCapture():
        try:
            wheel_cmd.run(options, args)
        except DistributionNotFound:
            # expected.  we forced this by using a non-existing version number.
            pass
    msg = 'Could not find a version that satisfies the requirement %s (from versions: %s)'
    record = next(r for r in reversed(log_capture.records) if r.msg == msg)
    _install_requirement, versions = record.args
    return versions


def get(dist_name, index_url=DEFAULT_INDEX):
    wheel_cmd = pip.commands.wheel.WheelCommand()
    wheel_args = ['--no-deps', '--no-cache-dir', '--index-url', index_url, dist_name]
    options, args = wheel_cmd.parse_args(wheel_args)
    # Waiting on pip 9.1 here
    #   https://github.com/pypa/pip/pull/4194
    log.debug('wheeling and dealing', cmd=' '.join(wheel_args))
    with LogCapture(level=logging.INFO) as log_capture, OutputCapture() as out:
        with open(os.devnull, 'w') as shhh, Replace('pip.utils.ui.DownloadProgressBar.file', shhh):
            wheel_cmd.run(options, args)
    log.debug('wheel command completed successfully')
    install_req = whl = url = checksum = collected_name = None
    for record in log_capture.records:
        if record.msg == 'Collecting %s':
            [install_req] = record.args
            url, _fragment, checksum = install_req.link.url.partition('#')
        elif record.msg == 'File was already downloaded %s':
            [whl] = record.args
        elif record.msg == 'Saved %s':
            [whl_rel] = record.args
            whl = os.path.realpath(whl_rel)
        elif record.msg == 'Building wheels for collected packages: %s':
            # only sdist was avail :(  this is annoying .. have to dig around to find the .whl
            # it's not easy, because the filename is case sensitive but the req name isn't
            [collected_name] = record.args
        elif record.msg == 'Successfully built %s' and (collected_name,) == record.args:
            whls = glob.glob('*.whl')
            whl = max(whls, key=lambda whl: os.stat(whl).st_mtime)
            required_spec = Requirement(dist_name).specifier
            name, version, the_rest = os.path.basename(whl).split('-', 2)
            name_mismatch = canonicalize_name(name) != canonicalize_name(install_req.req.name)
            if name_mismatch or version not in required_spec:
                # wat - the most recently modified wheel is not up to spec?  I think this can never happen ...
                raise Exception('Something strange happened')
    if None in {whl, url, checksum}:
        log.warning('failed to get a wheel', dist=dist_name)
        for record in log_capture.records:
            log.debug(record.msg, record.args)
        log.debug(out.captured)
        raise Exception("No .whl")
    if '.cache/pip/wheels' in url:
        # wat? using --no-cache-dir should have prevented this possibility
        # consider LogCapture at level DEBUG and capture the cached link (which may have been sdist)
        # start digging in pip.req.req_install.py:InstallRequirement.populate_link
        # If that doesn't work, might have to look at using pip.index.py:PackageFinder directly
        raise Exception('url is cached ... fixme')
    if not checksum:
        # this can happen, for example, if wheel dug a file out of the pip cache instead of downloading it
        # the wheel cache (~/.cache/pip/wheels/) directory structure is no good for us here, that's a sha224
        # of the download link, not a proper content checksum. so let's just compute the checksum clientside.
        md5 = compute_checksum(whl, algorithm='md5')
        checksum = 'md5={}'.format(md5)
    msg = 'built wheel from source' if collected_name is not None else 'found existing wheel'
    log.info(msg, url=url, checksum=checksum)
    result = {
        'path': whl,
        'url': url,
        'checksum': checksum,
    }
    return result


def main():
    parser = ArgumentParser()
    parser.add_argument('dist_name')
    parser.add_argument('--index-url', default=DEFAULT_INDEX)
    parser.add_argument('-v', '--verbose', action='store_true')
    debug = {
        'sys.argv': sys.argv,
        'sys.executable': sys.executable,
        'sys.version': sys.version,
        'sys.path': sys.path,
        'pip.__version__': pip.__version__,
        'pip.__file__': pip.__file__,
    }
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)
    log.debug(str(debug))
    result = get(dist_name=args.dist_name, index_url=args.index_url)
    print(json.dumps(result, indent=2, sort_keys=True, separators=(',', ': ')))


if __name__ == '__main__':
    main()
