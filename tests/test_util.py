import sys
from argparse import ArgumentTypeError
from subprocess import CalledProcessError

import pytest

from johnnydep import JohnnyDist
from johnnydep.cli import FIELDS
from johnnydep.compat import text_type
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
    for value in data.values():
        assert isinstance(value, text_type)
    assert sorted(data) == [
        "implementation_name",
        "implementation_version",
        "os_name",
        "packaging_version",
        "pip_version",
        "platform_machine",
        "platform_python_implementation",
        "platform_release",
        "platform_system",
        "platform_version",
        "python_executable",
        "python_full_version",
        "python_version",
        "setuptools_version",
        "sys_platform",
        "wheel_version",
    ]


def test_placeholder_serializes(make_dist):
    # this just checks that the placeholder can render to text without issue
    make_dist()
    dist = JohnnyDist("jdtest")
    CircularMarker(summary=".", parent=dist)
    txt = dist.serialise(fields=FIELDS, format="human")
    assert txt
