# coding: utf-8
from __future__ import unicode_literals

import os

from johnnydep.lib import JohnnyDist


def test_generated_metadata_from_dist_name(make_dist):
    make_dist()
    jdist = JohnnyDist("jdtest")
    expected_metadata = {
        "author": "default author",
        "author_email": "default@example.org",
        "description": "default long text for PyPI landing page \U0001f4a9\n\n\n",
        "home_page": "https://www.example.org/default",
        "license": "MIT",
        "metadata_version": "2.1",
        "name": "jdtest",
        "platforms": ["default platform"],
        "summary": "default text for metadata summary",
        "version": "0.1.2",
    }
    assert jdist.metadata == expected_metadata


def test_generated_metadata_from_dist_path(make_dist):
    _dist, dist_path, _checksum = make_dist()
    jdist = JohnnyDist(dist_path)
    expected_metadata = {
        "author": "default author",
        "author_email": "default@example.org",
        "description": "default long text for PyPI landing page \U0001f4a9\n\n\n",
        "home_page": "https://www.example.org/default",
        "license": "MIT",
        "metadata_version": "2.1",
        "name": "jdtest",
        "platforms": ["default platform"],
        "summary": "default text for metadata summary",
        "version": "0.1.2",
    }
    assert jdist.metadata == expected_metadata


def test_generated_filename(tmpdir, make_dist):
    _dist, dist_path, _checksum = make_dist()
    jdist = JohnnyDist(dist_path)
    expected_path = "{}/dist/jdtest-0.1.2-py2.py3-none-any.whl".format(tmpdir)
    assert dist_path == jdist.dist_path == expected_path


def test_build_from_sdist(add_to_index):
    here = os.path.dirname(__file__)
    sdist_fname = os.path.join(here, "copyingmock-0.2.tar.gz")
    add_to_index(name="copyingmock", path=sdist_fname, checksum="9aa6ba13542d25e527fe358d53cdaf3b")
    dist = JohnnyDist("copyingmock")
    assert dist.name == "copyingmock"
    assert dist.summary == "A subclass of MagicMock that copies the arguments"
    assert dist.required_by == []
    assert dist.import_names == ["copyingmock"]
    assert dist.homepage == "https://github.com/wimglenn/copyingmock"
    assert dist.extras_available == []
    assert dist.extras_requested == []
    assert dist.project_name == "copyingmock"
    assert dist.download_link == "https://pypi.org/simple/copyingmock/copyingmock-0.2.tar.gz"
    assert dist.checksum == "md5=9aa6ba13542d25e527fe358d53cdaf3b"


def test_plaintext_whl_metadata(add_to_index):
    # this dist uses an old-skool metadata version 1.2
    here = os.path.dirname(__file__)
    sdist_fname = os.path.join(here, "testpath-0.3.1-py2.py3-none-any.whl")
    add_to_index(name="testpath", path=sdist_fname, checksum="12728181294cf6f815421081d620c494")
    dist = JohnnyDist("testpath==0.3.1")
    assert dist.serialise(fields=["name", "summary", "import_names", "homepage"]) == [
        {
            "name": "testpath",
            "summary": "Test utilities for code working with files and commands",
            "import_names": ["testpath"],
            "homepage": "https://github.com/jupyter/testpath",
        }
    ]
