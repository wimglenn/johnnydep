import hashlib
import os
import os.path
import subprocess
import sys
from importlib.metadata import version

import pytest
import whl
from wimpy import working_directory

from johnnydep import cli
from johnnydep import dot
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


@pytest.fixture(autouse=True, scope="session")
def freeze_version():
    def fake_version(name):
        assert name == "johnnydep"
        return "1.0"
    cli.version = dot.version = fake_version
    yield
    cli.version = dot.version = version


@pytest.fixture(autouse=True)
def kill_env():
    os.environ.pop("JOHNNYDEP_FIELDS", None)


default_setup_kwargs = dict(
    name="jdtest",
    version="0.1.2",
    author="default author",
    author_email="default@example.org",
    description="default text for metadata summary",
    install_requires=(),
    extras_require=(),
    license="MIT",
    long_description="default long text for PyPI landing page 💩",
    url="https://www.example.org/default",
    platforms=("default platform",),
    py_modules=(),
    packages=(),
)


def make_wheel(scratch_dir="/tmp/jdtest", callback=None, **extra):
    kwargs = default_setup_kwargs.copy()
    kwargs.update(extra)
    name = kwargs["name"]
    version = kwargs["version"]

    # normalise from setuptools-style names to Core metadata spec names
    if "description" in kwargs:
        kwargs["summary"] = kwargs.pop("description")
    if "long_description" in kwargs:
        kwargs["description"] = kwargs.pop("long_description")
    if "install_requires" in kwargs:
        kwargs["requires_dist"] = kwargs.pop("install_requires")
    extras = kwargs.pop("extras_require") or {}
    if extras:
        if not kwargs.get("requires_dist"):
            kwargs["requires_dist"] = []
        for extra, reqs in extras.items():
            if isinstance(reqs, str):
                reqs = [reqs]
            for req in reqs:
                if ";" in req:
                    req, marker = req.split(";")
                    marker = "({}) and extra == '{}'".format(marker, extra)
                    req_str = "{}; {}".format(req, marker)
                else:
                    req_str = "{}; extra == '{}'".format(req, extra)
                kwargs["requires_dist"].append(req_str)
    if "url" in kwargs:
        kwargs["home_page"] = kwargs.pop("url")
    if "platforms" in kwargs:
        platforms = kwargs.pop("platforms")
        if isinstance(platforms, str):
            platforms = [p.strip() for p in platforms.split(",")]
        kwargs["platform"] = platforms
    if "classifiers" in kwargs:
        kwargs["classifier"] = kwargs.pop("classifiers")

    py_modules = kwargs.pop("py_modules", [])
    packages = kwargs.pop("packages", [])

    if py_modules:
        kwargs["src"] = []

    with working_directory(scratch_dir):
        for fname in py_modules:
            if os.path.exists(fname):
                raise Exception("already exists: {}".format(fname))
            with open(fname + ".py", "w"):
                pass
            kwargs["src"].append(os.path.join(scratch_dir, fname + ".py"))
        dist = whl.make_wheel(**kwargs)

    dist_path = os.path.join(scratch_dir, "{}-{}-py2.py3-none-any.whl".format(name, version))
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
def make_dist(tmp_path, add_to_index):
    def f(**kwargs):
        if "callback" not in kwargs:
            kwargs["callback"] = add_to_index
        if "scratch_dir" not in kwargs:
            kwargs["scratch_dir"] = str(tmp_path)
        return make_wheel(**kwargs)

    return f


@pytest.fixture(autouse=True)
def fake_subprocess(mocker, add_to_index):

    index_data = add_to_index.index_data
    subprocess_check_output = subprocess.check_output

    def wheel_proc(args, stderr, cwd=None):
        exe = args[0]
        req = args[-1]
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
        ]
        args.extend(["--find-links={}".format(p) for p in index_data])
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

    mocker.patch("johnnydep.pipper.check_output", wheel_proc)


@pytest.fixture
def fake_pip(mocker):
    mocker.patch("johnnydep.pipper.check_output", original_check_output)

    def local_files_args(index_url, env, extra_index_url):
        test_dir = os.path.abspath(os.path.join(__file__, os.pardir))
        canned = "file://{}".format(os.path.join(test_dir, "test_deps"))
        args = [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "-vvv",
            "--no-index",
            "--no-deps",
            "--no-cache-dir",
            "--disable-pip-version-check",
            "--find-links={}".format(canned),
        ]
        return args
    mocker.patch("johnnydep.pipper._get_wheel_args", local_files_args)
