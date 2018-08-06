# coding: utf-8
from __future__ import unicode_literals

import hashlib
import os
import subprocess
from collections import defaultdict
from functools import partial

import pytest
from setuptools import setup
from testfixtures import OutputCapture
from testfixtures import Replace
from wimpy import strip_prefix
from wimpy import working_directory

from johnnydep import pipper


@pytest.fixture(autouse=True)
def expire_caches():
    pipper.get_versions.cache_clear()
    pipper.get.cache_clear()


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
def add_to_index():
    index_data = {}

    def add_package(name, path, urlfragment=''):
        index_data[path] = (name, urlfragment)

    add_package.index_data = index_data
    yield add_package


@pytest.fixture()
def make_dist(tmpdir, add_to_index):
    return partial(make_wheel, scratch_dir=str(tmpdir), callback=add_to_index)


@pytest.fixture(autouse=True)
def fake_subprocess(mocker, add_to_index):

    index_data = add_to_index.index_data
    subprocess_check_output = subprocess.check_output

    def wheel_proc(args, stderr, cwd=None):
        exe = args[0]
        req = args[-1]
        links = ['--find-links={}'.format(p) for p in index_data]
        args = [exe, '-m', 'pip', 'wheel', '-vvv', '--no-index', '--no-deps', '--no-cache-dir', '--disable-pip-version-check', '--progress-bar=off'] + links + [req]
        output = subprocess_check_output(args, stderr=stderr, cwd=cwd)
        lines = output.decode().splitlines()
        for line in lines:
            line = line.strip()
            if line.startswith('Saved ./'):
                fname = strip_prefix(line, 'Saved ./')
                inject = '\n  Downloading from URL http://fakeindex/{}\n'.format(fname)
                output += inject.encode()
                break
        return output

    mocker.patch('johnnydep.pipper.subprocess.check_output', wheel_proc)
