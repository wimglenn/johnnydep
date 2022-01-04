# coding: utf-8
from __future__ import unicode_literals

from textwrap import dedent

from johnnydep.cli import main


def test_printed_table_on_stdout(mocker, capsys, make_dist):
    make_dist()
    mocker.patch("sys.argv", "johnnydep jdtest==0.1.2".split())
    main()
    out, err = capsys.readouterr()
    assert err == ""
    assert out == dedent(
        """\
        name           summary
        -------------  ---------------------------------
        jdtest==0.1.2  default text for metadata summary
    """
    )


def test_printed_table_on_stdout_with_specifier(make_dist, mocker, capsys):
    make_dist()
    mocker.patch("sys.argv", "johnnydep jdtest>=0.1 --fields specifier".split())
    main()
    out, err = capsys.readouterr()
    assert err == ""
    assert out == dedent(
        """\
        name    specifier
        ------  -----------
        jdtest  >=0.1
    """
    )


def test_printed_tree_on_stdout(mocker, capsys, make_dist):
    make_dist(name="thing", extras_require={"xyz": "spam>0.30.0", "abc": "eggs"})
    make_dist(name="spam", version="0.31")
    make_dist(name="eggs")
    mocker.patch(
        "sys.argv", "johnnydep thing[xyz] --fields extras_available extras_requested".split()
    )
    main()
    out, err = capsys.readouterr()
    assert err == ""
    assert out == dedent(
        """\
        name             extras_available    extras_requested
        ---------------  ------------------  ------------------
        thing[xyz]       abc, xyz            xyz
        └── spam>0.30.0
    """
    )


def test_diamond_deptree(mocker, capsys, make_dist):
    make_dist(name="distA", install_requires=["distB1", "distB2"], version="0.1")
    make_dist(name="distB1", install_requires=["distC[x,z]<0.3"], version="0.1")
    make_dist(name="distB2", install_requires=["distC[y]!=0.2"], version="0.1")
    make_dist(name="distC", version="0.1")
    make_dist(name="distC", version="0.2")
    make_dist(name="distC", version="0.3")
    fields = [
        "name",
        "specifier",
        "requires",
        "required_by",
        "versions_available",
        "version_latest_in_spec",
    ]
    mocker.patch("sys.argv", "johnnydep distA --fields".split() + fields)
    main()
    out, err = capsys.readouterr()
    assert err == ""
    assert out == dedent(
        """\
    name                specifier    requires        required_by    versions_available      version_latest_in_spec
    ------------------  -----------  --------------  -------------  --------------------  ------------------------
    distA                            distB1, distB2                 0.1                                        0.1
    ├── distB1                       distC[x,z]<0.3  distA          0.1                                        0.1
    │   └── distC[x,z]  <0.3                         distB1         0.1, 0.2, 0.3                              0.2
    └── distB2                       distC[y]!=0.2   distA          0.1                                        0.1
        └── distC[y]    !=0.2                        distB2         0.1, 0.2, 0.3                              0.3
    """
    )


def test_unresolvable_deptree(mocker, capsys, make_dist):
    # It is still possible to print the dep tree even though there is no acceptable version available for distC
    make_dist(name="distX", install_requires=["distC<=0.1", "distC>0.2"], version="0.1")
    make_dist(name="distC", version="0.1")
    make_dist(name="distC", version="0.2")
    make_dist(name="distC", version="0.3")
    fields = "name requires required_by versions_available version_latest_in_spec".split()
    mocker.patch("sys.argv", "johnnydep distX --fields".split() + fields)
    main()
    out, err = capsys.readouterr()
    assert err == ""
    assert out == dedent(
        """\
        name            requires               required_by    versions_available      version_latest_in_spec
        --------------  ---------------------  -------------  --------------------  ------------------------
        distX           distC<=0.1, distC>0.2                 0.1                                        0.1
        ├── distC<=0.1                         distX          0.1, 0.2, 0.3                              0.1
        └── distC>0.2                          distX          0.1, 0.2, 0.3                              0.3
    """
    )


def test_requirements_txt_output(mocker, capsys, make_dist):
    make_dist(name="distA", install_requires=["distB1", "distB2"], version="0.1")
    make_dist(name="distB1", install_requires=["distC[x,z]<0.3"], version="0.1")
    make_dist(name="distB2", install_requires=["distC[y]!=0.2"], version="0.1")
    make_dist(name="distC", version="0.1")
    make_dist(name="distC", version="0.2")
    make_dist(name="distC", version="0.3")
    mocker.patch("sys.argv", "johnnydep distA -o pinned".split())
    main()
    out, err = capsys.readouterr()
    assert err == ""
    assert out == dedent(
        """\
        distA==0.1
        distB1==0.1
        distB2==0.1
        distC[x,y,z]==0.1
    """
    )


def test_all_fields_toml_out(mocker, capsys, make_dist):
    _dist, _dist_path, checksum = make_dist(name="wimpy", version="0.3", py_modules=["that"])
    mocker.patch("sys.argv", "johnnydep wimpy<0.4 --fields=ALL --output-format=toml".split())
    main()
    out, err = capsys.readouterr()
    assert err == ""
    assert out == dedent(
        """\
        name = "wimpy"
        summary = "default text for metadata summary"
        specifier = "<0.4"
        requires = []
        required_by = []
        import_names = [ "that",]
        homepage = "https://www.example.org/default"
        extras_available = []
        extras_requested = []
        project_name = "wimpy"
        license = "MIT"
        versions_available = [ "0.3",]
        version_installed = "0.3"
        version_latest = "0.3"
        version_latest_in_spec = "0.3"
        download_link = "http://fakeindex/wimpy-0.3-py2.py3-none-any.whl"
        checksum = "md5={checksum}"

    """.format(
            checksum=checksum
        )
    )


def test_ignore_errors_on_stdout(mocker, capsys, make_dist):
    make_dist(name="distA", install_requires=["distB1>=1.0", "distB2"], version="0.1")
    make_dist(name="distB2", install_requires=["distC[y]!=0.2"], version="0.1")
    make_dist(name="distC", version="0.3")

    mocker.patch(
        "sys.argv", "johnnydep distA --ignore-errors".split()
    )
    main()
    out, err = capsys.readouterr()
    assert err == ""
    assert "DistributionNotFound: No matching distribution found for distB1>=1.0" in out
