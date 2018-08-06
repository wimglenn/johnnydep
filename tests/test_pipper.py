# coding: utf-8
from __future__ import unicode_literals

import json
import os

from wimpy import working_directory

import johnnydep.pipper


def test_pipper(mocker, capsys, make_dist, tmpdir):
    make_dist(name="fakedist", version="1.2.3")
    mocker.patch("sys.argv", "pipper.py fakedist".split())
    with working_directory(tmpdir):
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


def test_compute_checksum(tmpdir):
    tmpfile = tmpdir.join("fname")
    fname = str(tmpfile)
    tmpfile.write("spam and eggs")
    md5 = johnnydep.pipper.compute_checksum(fname, algorithm="md5")
    sha256 = johnnydep.pipper.compute_checksum(fname)
    assert md5 == "b581660cff17e78c84c3a84ad02e6785"
    assert sha256 == "7c788633adc75d113974372eec8c24776a581f095a747136e7ccf41b4a18b74e"
