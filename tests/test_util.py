import sys
from argparse import ArgumentTypeError
from subprocess import CalledProcessError

import pytest

from johnnydep import JohnnyDist
from johnnydep.cli import FIELDS
from johnnydep.util import CircularMarker
from johnnydep.util import python_interpreter


def test_bad_python_interpreter_triggers_argparse_error(mocker):
    mocker.patch("johnnydep.util.check_output", side_effect=CalledProcessError(1, "boom"))
    with pytest.raises(ArgumentTypeError) as cm:
        python_interpreter("whatever")
    assert str(cm.value) == "Invalid python env call"


def test_bad_python_interpreter_output_triggers_argparse_error(mocker):
    mocker.patch("johnnydep.util.check_output", return_value=b"wtf")
    with pytest.raises(ArgumentTypeError) as cm:
        python_interpreter("whatever")
    assert str(cm.value) == "Invalid python env output"


def test_good_python_env():
    data = python_interpreter(sys.executable)
    assert isinstance(data, tuple)
    data = dict(data)
    keys = sorted(data)
    assert keys == [
        "abis",
        "impl",
        "implementation_name",
        "implementation_version",
        "os_name",
        "platform_machine",
        "platform_python_implementation",
        "platform_release",
        "platform_system",
        "platform_version",
        "platforms",
        "py_ver",
        "python_executable",
        "python_full_version",
        "python_version",
        "supported_tags",
        "sys_platform",
    ]
    assert data.pop("abis") is None
    assert data.pop("platforms") is None
    assert data.pop("py_ver") >= (3, 8)
    for name, value in data.items():
        assert isinstance(value, str), name


def test_placeholder_serializes(make_dist):
    # this just checks that the placeholder can render to text without issue
    make_dist()
    dist = JohnnyDist("jdtest")
    CircularMarker(summary=".", parent=dist)
    txt = dist.serialise(fields=FIELDS, format="human")
    assert txt


def test_placeholder_attr():
    cm = CircularMarker(summary=".", parent=None)
    assert cm.blah is None
    assert cm.__doc__ is not None
    with pytest.raises(AttributeError):
        cm._blah
