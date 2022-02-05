# coding: utf-8
from __future__ import unicode_literals

import hashlib
import os
import os.path
import subprocess
import sys

import pytest
from setuptools import setup
from wimpy import working_directory

import johnnydep
from johnnydep import lib
from johnnydep import pipper


original_check_output = subprocess.check_output


@pytest.fixture(autouse=True)
def expire_caches():
    pipper.get_versions.cache_clear()
    pipper._get_cache.clear()
    lib._get_info.cache_clear()


@pytest.fixture(autouse=True)
def disable_logconfig(mocker):
    mocker.patch("johnnydep.logs.logging.config.dictConfig")


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


def make_wheel(capsys, mocker, scratch_dir="/tmp/jdtest", python_tag=None, callback=None, **extra):
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
    mocker.patch("sys.dont_write_bytecode", False)
    with working_directory(scratch_dir):
        for fname in kwargs["py_modules"]:
            if os.path.exists(fname):
                raise Exception("already exists: {}".format(fname))
            with open(fname + ".py", "w"):
                pass
        dist = setup(script_args=script_args, **kwargs)
    out, err = capsys.readouterr()
    lines = out.splitlines() + err.splitlines()
    for line in lines:
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
        callback(name=name, path=dist_path, urlfragment="#md5=" + md5)
    return dist, dist_path, md5


@pytest.fixture
def add_to_index():
    index_data = {}

    def add_package(name, path, urlfragment=""):
        index_data[path] = (name, urlfragment)

    add_package.index_data = index_data
    yield add_package


@pytest.fixture
def make_dist(tmp_path, add_to_index, capsys, mocker):
    def f(**kwargs):
        return make_wheel(capsys, mocker, scratch_dir=str(tmp_path), callback=add_to_index, **kwargs)

    return f


@pytest.fixture(autouse=True)
def fake_subprocess(mocker, add_to_index):

    index_data = add_to_index.index_data
    subprocess_check_output = subprocess.check_output

    def wheel_proc(args, stderr, cwd=None):
        exe = args[0]
        req = args[-1]
        links = ["--find-links={}".format(p) for p in index_data]
        args = [
            exe,
            "-m",
            "pip",
            "wheel",
            "-vvv",
            "--no-index",
            "--no-deps",
            "--no-cache-dir",
            "--disable-pip-version-check",
            "--progress-bar=off",
            "--use-deprecated=legacy-resolver",
        ]
        args.extend(links)
        args.append(req)
        output = subprocess_check_output(args, stderr=stderr, cwd=cwd)
        lines = output.decode().splitlines()
        for line in lines:
            line = line.strip()
            if line.startswith("Saved "):
                fname = line.split("/")[-1].split("\\")[-1]
                inject = "{0}  Downloading from URL http://fakeindex/{1}{0}".format(os.linesep, fname)
                output += inject.encode()
                break
        return output

    mocker.patch("johnnydep.pipper.subprocess.check_output", wheel_proc)


@pytest.fixture
def fake_pip(mocker):
    import pip
    mocker.patch("johnnydep.pipper.subprocess.check_output", original_check_output)

    def local_files_args(index_url, env, extra_index_url):
        test_dir = os.path.abspath(os.path.join(__file__, os.pardir))

        args = [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "-vvv",  # --verbose x3
            "--no-deps",
            "--no-cache-dir",
            "--disable-pip-version-check",
            "--find-links",
            "file://{0}".format(os.path.join(test_dir, "test_deps"))
        ]
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
    mocker.patch("johnnydep.pipper._get_wheel_args", local_files_args)
