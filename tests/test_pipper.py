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
    "url, index_url, extra_index_url, expected",
    [
        (
            "https://pypi.example.com/packages",
            "https://pypi.example.com/simple",
            None,
            None,
        ),
        (
            "https://pypi.example.com/packages",
            "https://user:pass@pypi.example.com/simple",
            None,
            ("user", "pass"),
        ),
        (
            "https://pypi.extra.com/packages",
            "https://user:pass@pypi.example.com/simple",
            "https://pypi.extra.com/simple",
            None,
        ),
        (
            "https://pypi.extra.com/packages",
            "https://user:pass@pypi.example.com/simple",
            "https://user:extrapass@pypi.extra.com/simple",
            ("user", "extrapass"),
        ),
        (
            "https://pypi.extra.com/packages",
            None,
            "https://user:extrapass@pypi.extra.com/simple",
            ("user", "extrapass"),
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
def test_download_dist_auth(mocker, url, index_url, extra_index_url, expected):
    here = os.path.dirname(__file__)
    whl_fname = os.path.join(here, "vanilla-0.1.2-py2.py3-none-any.whl")
    # return auth instead of headers
    mocker.patch(
        "johnnydep.pipper.urlretrieve",
        new=lambda url, target, auth: (target, auth),
    )

    target, auth = johnnydep.pipper._download_dist(
        url=url + "/vanilla/0.1.2/vanilla-0.1.2-py2.py3-none-any.whl",
        scratch_file=whl_fname,
        index_url=index_url,
        extra_index_url=extra_index_url,
    )
    assert target == whl_fname
    assert auth == expected
