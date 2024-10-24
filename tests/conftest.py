import os
import shutil
import tempfile
from importlib.metadata import version
from pathlib import Path

import pytest
import whl
from unearth import PackageFinder
from wimpy import working_directory

from johnnydep import cli
from johnnydep import dot
from johnnydep import lib


@pytest.fixture(autouse=True)
def expire_caches():
    lib._get_info.cache_clear()
    lib._get_link.cache_clear()
    lib._get_versions.cache_clear()


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


def make_wheel(scratch_path=None, callback=None, **extra):
    if scratch_path is None:
        scratch_path = Path(tempfile.gettempdir())
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
            for req in reqs:
                if ";" in req:
                    req, marker = req.split(";")
                    marker = f"({marker}) and extra == '{extra}'"
                    req_str = f"{req}; {marker}"
                else:
                    req_str = f"{req}; extra == '{extra}'"
                kwargs["requires_dist"].append(req_str)
    if "url" in kwargs:
        kwargs["home_page"] = kwargs.pop("url")
    if "platforms" in kwargs:
        kwargs["platform"] = kwargs.pop("platforms")
    if "classifiers" in kwargs:
        kwargs["classifier"] = kwargs.pop("classifiers")

    py_modules = kwargs.pop("py_modules", [])
    packages = kwargs.pop("packages", [])

    if py_modules:
        kwargs["src"] = []

    with working_directory(scratch_path):
        for fname in py_modules:
            assert not Path(fname).exists()
            with open(fname + ".py", "w"):
                pass
            kwargs["src"].append(f"{scratch_path / fname}" + ".py")
        dist_path = Path(whl.make_wheel(**kwargs)).resolve()

    fname = f"{name.replace('-', '_')}-{version}-py2.py3-none-any.whl"
    assert dist_path == scratch_path.resolve() / fname
    if callback is not None:
        # contribute to test index
        callback(dist_path)

    return dist_path


@pytest.fixture
def add_to_index(mocker):

    find_links = set()

    def add_package(path):
        find_links.add(path.parent)

    def mock_package_finder(index_urls, target_python, trusted_hosts):
        return PackageFinder(
            index_urls=[],
            target_python=target_python,
            find_links=list(find_links),
        )

    mocker.patch("unearth.PackageFinder", mock_package_finder)
    yield add_package


@pytest.fixture
def make_dist(tmp_path, add_to_index):
    def f(**kwargs):
        kwargs.setdefault("callback", add_to_index)
        kwargs.setdefault("scratch_path", tmp_path)
        return make_wheel(**kwargs)

    return f


def pytest_assertrepr_compare(config, op, left, right):
    # https://docs.pytest.org/en/latest/reference/reference.html#pytest.hookspec.pytest_assertrepr_compare
    if isinstance(left, str) and isinstance(right, str) and op == "==":
        left_lines = left.splitlines()
        right_lines = right.splitlines()
        if len(left_lines) > 1 or len(right_lines) > 1:
            width, _ = shutil.get_terminal_size(fallback=(80, 24))
            width = max(width, 40) - 10
            lines = [
                "When comparing multiline strings:",
                f" LEFT ({len(left)}) ".center(width, "="),
                *left_lines,
                f" RIGHT ({len(right)}) ".center(width, "="),
                *right_lines,
            ]
            return lines
