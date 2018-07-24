# coding: utf-8
from __future__ import unicode_literals

import hashlib
import os
import sys
from collections import defaultdict
from functools import partial

import pytest
import requests_mock as _requests_mock
from packaging.utils import canonicalize_name
from setuptools import setup
from testfixtures import OutputCapture
from testfixtures import Replace
from wimpy import working_directory

from johnnydep.lib import get_wheel
from johnnydep.pipper import get_link
from johnnydep.pipper import get_versions


@pytest.fixture(autouse=True)
def expire_caches():
    get_wheel.cache_clear()
    get_link.cache_clear()
    get_versions.cache_clear()


@pytest.fixture(autouse=True)
def requests_mock(mocker):
    adapter = _requests_mock.Adapter()
    mocker.patch("pip._vendor.requests.sessions.Session.get_adapter", return_value=adapter)
    if sys.version_info.major == 2:
        target = "socket.gethostbyname"
    else:
        target = "urllib.request.socket.gethostbyname"
    mocker.patch(target, {"pypi.org": "151.101.44.223"}.__getitem__)
    return adapter


@pytest.fixture(autouse=True)
def kill_env():
    os.environ.pop("JOHNNYDEP_FIELDS", None)


default_setup_kwargs = dict(
    name="jdtest",
    version="0.1.2",
    author="default author",
    author_email="default@example.org",
    description="default text for metadata summary",
    install_requires=[],
    extras_require={},
    license="MIT",
    long_description="default long text for PyPI landing page 💩",
    url="https://www.example.org/default",
    platforms=["default platform"],
    py_modules=[],
    packages=[],
)


def make_wheel(scratch_dir="/tmp/jdtest", python_tag=None, callback=None, **extra):
    kwargs = default_setup_kwargs.copy()
    kwargs.update(extra)
    name = kwargs["name"]
    version = kwargs["version"]
    fname_prefix = "-".join([name, version])
    script_args = ["--no-user-cfg", "bdist_wheel"]
    if python_tag is None:
        script_args.append("--universal")
        python_tag = "py2.py3"
    else:
        script_args.extend(["--python-tag", python_tag])
    with working_directory(scratch_dir), OutputCapture() as cap, Replace('sys.dont_write_bytecode', False):
        for fname in kwargs["py_modules"]:
            if os.path.exists(fname):
                raise Exception("already exists: {}".format(fname))
            with open(fname + ".py", "w"):
                pass
        dist = setup(script_args=script_args, **kwargs)
    for line in cap.captured.splitlines():
        if "warning" in line.lower():
            raise Exception("setup warning: {}".format(line))
    dist_dir = os.path.join(scratch_dir, "dist")
    dist_files = [f for f in os.listdir(dist_dir) if fname_prefix in f]
    [dist_fname] = [f for f in dist_files if "-" + python_tag + "-" in f]
    dist_path = os.path.join(dist_dir, dist_fname)
    with open(dist_path, mode="rb") as f:
        md5 = hashlib.md5(f.read()).hexdigest()
    if callback is not None:
        # contribute to test index
        callback(name=name, path=dist_path, urlfragment='#md5='+md5)
    return dist, dist_path, md5


@pytest.fixture()
def add_to_index(requests_mock):

    index_data = defaultdict(list)  # fake PyPI

    def add_package(name, path, urlfragment=''):
        canonical_name = canonicalize_name(name)
        index_data[canonical_name].append((path, urlfragment))
        with open(path, mode="rb") as f:
            content = f.read()
        fname = os.path.basename(path)
        requests_mock.register_uri(
            method="GET",
            url="https://pypi.org/simple/{}/{}".format(name, fname),
            headers={"Content-Type": "binary/octet-stream"},
            content=content,
        )
        href = '<a href="./{fname}{urlfragment}">{fname}</a><br/>'
        links = {
            os.path.basename(path): md5 for path, md5 in index_data[canonical_name]
        }  # last one wins!
        links = [href.format(fname=k, urlfragment=v) for k, v in links.items()]
        requests_mock.register_uri(
            method="GET",
            url="https://pypi.org/simple/{}/".format(name),
            headers={"Content-Type": "text/html"},
            text="""
            <!DOCTYPE html><html><head><title>Links for {name}</title></head>
            <body><h1>Links for {name}</h1>
            {links}
            </body></html>""".format(
                name=name, links="\n".join(links)
            ),
        )

    yield add_package


@pytest.fixture()
def make_dist(tmpdir, add_to_index):
    return partial(make_wheel, scratch_dir=str(tmpdir), callback=add_to_index)
