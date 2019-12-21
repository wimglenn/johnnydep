# coding: utf-8
from __future__ import unicode_literals

import json
import os

import pytest
from wimpy import working_directory

import johnnydep.pipper


def test_pipper_main(mocker, capsys, make_dist, tmp_path):
    make_dist(name="fakedist", version="1.2.3")
    mocker.patch("sys.argv", "pipper.py fakedist".split())
    with working_directory(tmp_path):
        johnnydep.pipper.main()
    out, err = capsys.readouterr()
    output = json.loads(out)
    path = output.pop("path")
    checksum = output.pop("checksum")
    assert output == {"url": "http://fakeindex/fakedist-1.2.3-py2.py3-none-any.whl"}
    assert os.path.isfile(path)
    assert os.path.basename(path) == "fakedist-1.2.3-py2.py3-none-any.whl"
    assert len(checksum) == 4 + 32
    assert checksum.startswith("md5=")
    assert err == ""


def test_compute_checksum(tmp_path):
    tmpfile = tmp_path.joinpath("fname")
    fname = str(tmpfile)
    tmpfile.write_text("spam and eggs")
    md5 = johnnydep.pipper.compute_checksum(fname, algorithm="md5")
    sha256 = johnnydep.pipper.compute_checksum(fname)
    assert md5 == "b581660cff17e78c84c3a84ad02e6785"
    assert sha256 == "7c788633adc75d113974372eec8c24776a581f095a747136e7ccf41b4a18b74e"


def test_get_wheel_args():
    fake_env = ("python_executable", "snek"), ("pip_version", "8.8.8")
    url = "https://user:pass@example.org:8888/something"
    args = johnnydep.pipper._get_wheel_args(index_url=url, env=fake_env, extra_index_url=None)
    assert args == [
        "snek",
        "-m",
        "pip",
        "wheel",
        "-vvv",
        "--no-deps",
        "--no-cache-dir",
        "--disable-pip-version-check",
        "--index-url",
        "https://user:pass@example.org:8888/something",
        "--trusted-host",
        "example.org",
    ]


@pytest.mark.parametrize(
    "url, index_url, extra_index_url, expected_auth, expected_top_level_url",
    [
        (
            "https://pypi.example.com/packages",
            "https://pypi.example.com/simple",
            None,
            None,
            None,
        ),
        (
            "https://pypi.example.com/packages",
            "https://user:pass@pypi.example.com/simple",
            None,
            ("user", "pass"),
            "pypi.example.com",
        ),
        (
            "https://pypi.extra.com/packages",
            "https://user:pass@pypi.example.com/simple",
            "https://pypi.extra.com/simple",
            None,
            "pypi.example.com",
        ),
        (
            "https://pypi.extra.com/packages",
            "https://user:pass@pypi.example.com/simple",
            "https://user:extrapass@pypi.extra.com/simple",
            ("user", "extrapass"),
            "pypi.extra.com",
        ),
        (
            "https://pypi.extra.com/packages",
            None,
            "https://user:extrapass@pypi.extra.com/simple",
            ("user", "extrapass"),
            "pypi.extra.com",
        ),
    ],
    ids=(
        "index_url without auth",
        "index_url with auth",
        "extra_index_url without auth",
        "extra_index_url with auth",
        "extra_index_url with auth (no index_url)",
    ),
)
def test_download_dist_auth(mocker, url, index_url, extra_index_url, expected_auth, expected_top_level_url, tmp_path):
    mgr = mocker.patch("johnnydep.compat.urllib2.HTTPPasswordMgrWithDefaultRealm")
    add_password_mock = mgr.return_value.add_password

    opener = mocker.patch("johnnydep.compat.urllib2.build_opener").return_value
    mock_response = opener.open.return_value
    mock_response.read.return_value = b"test body"

    scratch_path = tmp_path / "test-0.1.tar.gz"
    target, _headers = johnnydep.pipper._download_dist(
        url=url + "/test-0.1.tar.gz",
        scratch_file=str(scratch_path),
        index_url=index_url,
        extra_index_url=extra_index_url,
    )
    if expected_auth is None:
        add_password_mock.assert_not_called()
    else:
        expected_realm = None
        expected_username, expected_password = expected_auth
        add_password_mock.assert_called_once_with(
            expected_realm,
            expected_top_level_url,
            expected_username,
            expected_password,
        )
    assert target == str(scratch_path)
    assert scratch_path.read_bytes() == b"test body"
