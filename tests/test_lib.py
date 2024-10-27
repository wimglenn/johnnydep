import json
import os
from textwrap import dedent

import pytest
from packaging.requirements import Requirement

from johnnydep import lib
from johnnydep.lib import flatten_deps
from johnnydep.lib import JohnnyDist
from johnnydep.lib import JohnnyError


def test_version_nonexisting(make_dist):
    # v0.404 does not exist in index
    make_dist()
    with pytest.raises(JohnnyError("Package not found 'jdtest==0.404'")):
        JohnnyDist("jdtest==0.404")


def test_import_names_empty(make_dist):
    make_dist()
    jdist = JohnnyDist("jdtest")
    assert jdist.import_names == []


def test_import_names_nonempty(make_dist):
    make_dist(py_modules=["mod1", "mod2"])
    jdist = JohnnyDist("jdtest")
    assert jdist.import_names == ["mod1", "mod2"]


def test_version_installed(make_dist):
    make_dist(name="wimpy", version="0.3")
    jdist = JohnnyDist("wimpy")
    assert jdist.version_installed == "0.3"


def test_version_not_installed(make_dist):
    make_dist()
    jdist = JohnnyDist("jdtest")
    assert not jdist.version_installed


def test_version_latest(make_dist):
    make_dist(version="1.2.3")
    make_dist(version="1.3.2")
    jdist = JohnnyDist("jdtest")
    assert jdist.version_latest == "1.3.2"


def test_version_latest_in_spec(make_dist):
    make_dist(version="1.2.3")
    make_dist(version="2.3.4")
    make_dist(version="3.4.5")
    jdist = JohnnyDist("jdtest<3")
    assert jdist.version_latest_in_spec == "2.3.4"


def test_version_latest_in_spec_prerelease_not_chosen(make_dist):
    make_dist(version="0.1")
    make_dist(version="0.2a0")
    jdist = JohnnyDist("jdtest")
    assert jdist.version_latest_in_spec == "0.1"


def test_version_latest_in_spec_prerelease_chosen(make_dist):
    make_dist(name="alphaonly", version="0.2a0")
    jdist = JohnnyDist("alphaonly")
    assert jdist.version_latest_in_spec == "0.2a0"


def test_version_pinned_to_latest_in_spec(make_dist):
    make_dist(version="1.2.3")
    make_dist(version="2.3.4")
    make_dist(version="3.4.5")
    jdist = JohnnyDist("jdtest<3")
    assert jdist.pinned == "jdtest==2.3.4"


def test_version_pin_includes_extras(make_dist):
    make_dist(version="1.2.3")
    make_dist(version="2.3.4")
    make_dist(version="3.4.5")
    jdist = JohnnyDist("jdtest[a,b]<3")
    assert jdist.pinned == "jdtest[a,b]==2.3.4"


def test_version_in_spec_not_avail(make_dist):
    make_dist(version="1.2.3")
    make_dist(version="2.3.4")
    make_dist(version="3.4.5")
    with pytest.raises(JohnnyError("Package not found 'jdtest>4'")):
        JohnnyDist("jdtest>4")


def test_project_name_different_from_canonical_name(make_dist):
    make_dist(name="PyYAML")
    jdist = JohnnyDist("pyyaml")
    assert jdist.name == "pyyaml"
    assert jdist.project_name == "PyYAML"


def test_homepage(make_dist):
    make_dist()
    jdist = JohnnyDist("jdtest")
    assert jdist.homepage == "https://www.example.org/default"


def test_homepage_from_project_urls(make_dist):
    make_dist(project_url=["url1, https://blah", "homepage, https://www.example.org/proj_url"])
    jdist = JohnnyDist("jdtest")
    assert jdist.homepage == "https://www.example.org/proj_url"


def test_no_homepage(make_dist):
    make_dist(url=None)
    jdist = JohnnyDist("jdtest")
    assert jdist.homepage is None


def test_dist_no_children(make_dist):
    make_dist()
    jdist = JohnnyDist("jdtest")
    assert jdist.children == []


def test_checksum_sha256(make_dist):
    # the actual checksum value is not repeatable because of timestamps, file modes etc
    # so we just assert that we get a value which looks like a valid checkum
    make_dist()
    jdist = JohnnyDist("jdtest")
    hashtype, sep, hashval = jdist.checksum.partition("=")
    assert hashtype == "sha256"
    assert sep == "="
    assert len(hashval) == 64
    assert set(hashval) <= set("1234567890abcdef")


def test_scratch_dirs_are_being_cleaned_up(make_dist, mocker):
    make_dist()
    mkdtemp = mocker.spy(lib, "mkdtemp")
    rmtree = mocker.spy(lib, "rmtree")
    JohnnyDist("jdtest")
    mkdtemp.assert_called_once_with()
    [scratch] = mkdtemp.spy_return_list
    rmtree.assert_called_once_with(scratch, ignore_errors=True)
    assert not os.path.exists(scratch)


def test_extras_available_none(make_dist):
    make_dist()
    jdist = JohnnyDist("jdtest")
    assert jdist.extras_available == []


def test_extras_available(make_dist):
    make_dist(extras_require={"xy": ["blah"], "abc": ["spam", "eggs"]})
    jdist = JohnnyDist("jdtest")
    assert jdist.extras_available == ["abc", "xy"]


def test_extras_requested_none(make_dist):
    make_dist()
    jdist = JohnnyDist("jdtest")
    assert jdist.extras_requested == []


def test_extras_requested_sorted(make_dist):
    make_dist()
    jdist = JohnnyDist("jdtest[spam,eggs]")
    assert jdist.extras_requested == ["eggs", "spam"]


def test_summary(make_dist):
    make_dist()
    jdist = JohnnyDist("jdtest")
    assert jdist.summary == "default text for metadata summary"


def test_versions_available(make_dist):
    make_dist(version="0.1")
    make_dist(version="1.0.0")
    jdist = JohnnyDist("jdtest")
    assert jdist.versions_available == ["0.1", "1.0.0"]


def test_requires(make_dist):
    make_dist(name="parent", install_requires=["child1", "child3[extra]", "child2<0.5"])
    make_dist(name="child1")
    make_dist(name="child2")
    make_dist(name="child3")
    jdist = JohnnyDist("parent")
    assert jdist.requires == ["child1", "child2<0.5", "child3[extra]"]


def test_conditional_dependency_included_by_environment_marker(make_dist):
    make_dist(name="parent", install_requires=["child1", "child2; python_version>='1.0'"])
    make_dist(name="child1")
    make_dist(name="child2")
    jdist = JohnnyDist("parent")
    assert jdist.requires == ["child1", "child2"]


def test_conditional_dependency_excluded_by_environment_marker(make_dist):
    make_dist(name="parent", install_requires=["child1", "child2; python_version<'1.0'"])
    make_dist(name="child1")
    make_dist(name="child2")
    jdist = JohnnyDist("parent")
    assert jdist.requires == ["child1"]


def test_conditional_dependency_included_by_extra(make_dist):
    make_dist(name="parent", install_requires=["child1"], extras_require={"x": ["child2"]})
    make_dist(name="child1")
    make_dist(name="child2")
    jdist = JohnnyDist("parent[x]")
    assert jdist.requires == ["child1", "child2"]


def test_conditional_dependency_excluded_by_extra(make_dist):
    make_dist(name="parent", install_requires=["child1"], extras_require={"x": ["child2"]})
    make_dist(name="child1")
    make_dist(name="child2")
    jdist = JohnnyDist("parent")
    assert jdist.requires == ["child1"]


def test_conditional_dependency_included_by_extra_but_excluded_by_environment_marker(make_dist):
    make_dist(name="parent", extras_require={"x": ['child; python_version<"1.0"']})
    make_dist(name="child")
    jdist = JohnnyDist("parent[x]")
    assert jdist.requires == []


def test_children(make_dist):
    make_dist(name="parent", install_requires=["child"])
    make_dist(name="child")
    jdist = JohnnyDist("parent")
    [child] = jdist.children
    assert isinstance(child, JohnnyDist)
    assert isinstance(jdist.children, list)
    assert child.name == "child"


def test_serialiser_python(make_dist):
    make_dist()
    jdist = JohnnyDist("jdtest")
    assert jdist.serialise() == [{"name": "jdtest", "summary": "default text for metadata summary"}]


def test_serialiser_json(make_dist):
    make_dist()
    jdist = JohnnyDist("jdtest")
    assert jdist.serialise(format="json") == dedent(
        """\
        [
          {
            "name": "jdtest",
            "summary": "default text for metadata summary"
          }
        ]"""
    )


def test_serialiser_toml(make_dist):
    make_dist()
    jdist = JohnnyDist("jdtest")
    assert jdist.serialise(format="toml") == dedent(
        '''\
        name = "jdtest"
        summary = "default text for metadata summary"
        '''
    )


def test_serialiser_yaml(make_dist):
    make_dist()
    jdist = JohnnyDist("jdtest")
    yaml_out = "- name: jdtest\n  summary: default text for metadata summary\n"
    assert jdist.serialise(format="yaml") == yaml_out


def test_serialiser_pinned(make_dist):
    make_dist()
    jdist = JohnnyDist("jdtest[a]")
    assert jdist.serialise(format="pinned") == "jdtest[a]==0.1.2"


def test_serialiser_unsupported(make_dist):
    make_dist()
    jdist = JohnnyDist("jdtest")
    with pytest.raises(JohnnyError) as cm:
        jdist.serialise(format="bogus")
    assert cm.value.args == ("Unsupported format",)


def test_serialiser_with_children(make_dist):
    make_dist(name="a", install_requires=["b"])
    make_dist(name="b", version="2.0")
    jdist = JohnnyDist("A")
    assert jdist.serialise(format="pinned", recurse=True) == "a==0.1.2\nb==2.0"


def test_serialiser_with_children_no_recurse(make_dist):
    make_dist(name="a", install_requires=["b"])
    make_dist(name="b", version="2.0")
    jdist = JohnnyDist("A")
    assert jdist.serialise(format="pinned", recurse=False) == "a==0.1.2"


def test_serialiser_custom_fields(make_dist):
    make_dist(version="0.1")
    make_dist(version="0.2")
    jdist = JohnnyDist("jdtest")
    expected = [{"versions_available": ["0.1", "0.2"], "version_latest": "0.2"}]
    assert jdist.serialise(fields=("versions_available", "version_latest")) == expected


def test_flatten_dist_with_nodeps(make_dist):
    make_dist()
    jdist = JohnnyDist("jdtest")
    reqs = list(flatten_deps(jdist))
    assert reqs == [jdist]


def test_flatten_dist_with_deps(make_dist):
    make_dist(name="root", install_requires=["dep"])
    make_dist(name="dep")
    jdist = JohnnyDist("root")
    reqs = list(flatten_deps(jdist))
    [dist0, dist1] = reqs
    assert dist0 is jdist
    assert dist1.name == "dep"


def test_diamond_dependency_resolution(make_dist):
    make_dist(name="dist1", install_requires=["dist2a", "dist2b"])
    make_dist(name="dist2a", install_requires=["dist3[y]>0.2"])
    make_dist(name="dist2b", install_requires=["dist3[x,z]<0.4"])
    make_dist(name="dist3", version="0.2")
    make_dist(name="dist3", version="0.3")
    make_dist(name="dist3", version="0.4")
    jdist = JohnnyDist("dist1")
    dist1, dist2a, dist2b, dist3 = flatten_deps(jdist)

    assert dist1 is jdist
    assert dist1.requires == ["dist2a", "dist2b"]
    assert dist1.required_by == []

    assert dist2a.name == "dist2a"
    assert dist2a.requires == ["dist3[y]>0.2"]
    assert dist2a.required_by == ["dist1"]

    assert dist2b.name == "dist2b"
    assert dist2b.requires == ["dist3[x,z]<0.4"]
    assert dist2b.required_by == ["dist1"]

    assert dist3.name == "dist3"
    assert dist3.required_by == ["dist2a", "dist2b"]
    assert dist3.extras_requested == ["x", "y", "z"]  # merged
    assert dist3.versions_available == ["0.2", "0.3", "0.4"]
    assert dist3.version_latest == "0.4"
    assert dist3.version_latest_in_spec == "0.3"
    assert str(dist3.req.specifier) == "<0.4,>0.2"


def test_resolve_unresolvable(make_dist):
    make_dist(
        name="dist1", description="unresolvable", install_requires=["dist2<=0.1", "dist2>0.2"]
    )
    make_dist(name="dist2", version="0.1")
    make_dist(name="dist2", version="0.3")
    dist = JohnnyDist("dist1")
    data = dist.serialise(recurse=False, fields=["project_name", "summary", "requires"])
    assert data == [
        {
            "project_name": "dist1",
            "summary": "unresolvable",
            "requires": ["dist2<=0.1", "dist2>0.2"],
        }
    ]
    gen = flatten_deps(dist)
    assert next(gen) is dist
    with pytest.raises(JohnnyError("Package not found 'dist2<=0.1,>0.2'")):
        next(gen)


def test_pprint(make_dist, mocker):
    mocker.patch("johnnydep.lib.id", return_value=51966, create=True)
    mock_printer = mocker.MagicMock()
    make_dist()
    jdist = JohnnyDist("jdtest")
    jdist._repr_pretty_(mock_printer, cycle=False)
    pretty = "<JohnnyDist jdtest at 0xcafe>"
    mock_printer.text.assert_called_once_with(pretty)
    mock_printer.text.reset_mock()
    jdist = JohnnyDist("jdtest[a]~=0.1.2")
    jdist._repr_pretty_(mock_printer, cycle=False)
    pretty = "<JohnnyDist jdtest[a]~=0.1.2 at 0xcafe>"
    mock_printer.text.assert_called_once_with(pretty)
    mock_printer.text.reset_mock()
    jdist._repr_pretty_(mock_printer, cycle=True)
    mock_printer.text.assert_called_once_with(repr(jdist))


def test_get_caching(make_dist, mocker):
    # this test is trying to make sure that distribution "c", a node which appears
    # twice in the dependency graph, is only downloaded from the index once.
    # i.e. check that the caching on the downloader is working correctly.
    make_dist(name="c", description="leaf node")
    make_dist(name="b1", install_requires=["c"], description="branch one")
    make_dist(name="b2", install_requires=["c"], description="branch two")
    make_dist(name="a", install_requires=["b1", "b2"], description="root node")
    spy = mocker.spy(lib, "download_dist")
    jdist = JohnnyDist("a")
    txt = jdist.serialise(format="human")
    assert txt == dedent(
        """\
         name        summary
        ━━━━━━━━━━━━━━━━━━━━━━━━
         a           root node
         ├── b1      branch one
         │   └── c   leaf node
         └── b2      branch two
             └── c   leaf node"""
    )
    assert spy.call_count == 4
    downloads = [call.kwargs["url"] for call in spy.call_args_list]
    filenames = [download.split("/")[-1] for download in downloads]
    distnames = [filename.split("-")[0] for filename in filenames]
    assert distnames == ["a", "b1", "b2", "c"]


def test_extras_parsing(make_dist):
    make_dist(name="parent", install_requires=['child; extra == "foo" or extra == "bar"'])
    make_dist(name="child")
    assert JohnnyDist("parent").requires == []
    assert JohnnyDist("parent[foo]").requires == ["child"]
    assert JohnnyDist("parent[bar]").requires == ["child"]
    assert JohnnyDist("parent[baz]").requires == []
    assert JohnnyDist("parent[baz,foo]").requires == ["child"]


def test_license_parsing_metadaa(make_dist):
    make_dist(license="The License")
    assert JohnnyDist("jdtest").license == "The License"


def test_license_parsing_classifiers(make_dist):
    make_dist(license="", classifiers=["blah", "License :: OSI Approved :: MIT License"])
    assert JohnnyDist("jdtest").license == "MIT License"


def test_license_parsing_unknown(make_dist):
    make_dist(license="")
    assert JohnnyDist("jdtest").license == ""


def test_ignore_errors(make_dist):
    make_dist(name="distA", install_requires=["distB1>=1.0"], version="0.1")
    dist = JohnnyDist("distA", ignore_errors=True)
    assert len(dist.children) == 1
    assert dist.children[0].name == "distb1"
    assert dist.children[0].error is not None
    assert "Package not found 'distB1>=1.0'" in str(dist.children[0].error)


def test_flatten_failed(make_dist):
    make_dist(name="dist1", install_requires=["dist2>0.2"])
    make_dist(name="dist2", version="0.1")
    dist = JohnnyDist("dist1", ignore_errors=True)
    with pytest.raises(JohnnyError("Could not find satisfactory version for dist2>0.2")):
        list(flatten_deps(dist))


def test_local_whl_pinned(make_dist, mocker):
    # https://github.com/wimglenn/johnnydep/issues/105
    dist_path = make_dist(name="loc", version="1.2.3", callback=None)
    dist = JohnnyDist(dist_path)
    mocker.patch("unearth.finder.PackageFinder.find_all_packages", return_value=[])
    txt = dist.serialise(format="pinned").strip()
    assert txt == "loc==1.2.3"


def test_local_whl_json(make_dist):
    make_dist(name="loc", version="0.1.1")
    dist_path = make_dist(name="loc", version="0.1.2", callback=None)
    make_dist(name="loc", version="0.1.3")
    dist = JohnnyDist(dist_path)
    fields = ["download_link", "checksum", "versions_available"]
    txt = dist.serialise(format="json", fields=fields).strip()
    [result] = json.loads(txt)
    assert result["checksum"].startswith("sha256=")
    link = result["download_link"]
    assert link.startswith("file://")
    assert link.endswith("loc-0.1.2-py2.py3-none-any.whl")
    assert result["versions_available"] == ["0.1.1", "0.1.2", "0.1.3"]


def test_entry_points(make_dist):
    # https://packaging.python.org/en/latest/specifications/entry-points/
    entry_points = {"console_scripts": ["my-script = mypkg.mymod:foo"]}
    make_dist(name="example", entry_points=entry_points)
    dist = JohnnyDist("example")
    [ep] = dist.entry_points
    assert ep.name == "my-script"
    assert ep.group == "console_scripts"
    assert ep.value == "mypkg.mymod:foo"
    assert dist.console_scripts == ["my-script = mypkg.mymod:foo"]


def test_direct_path_version_insort(make_dist, tmp_path):
    make_dist(name="foo", version="0.1.1")
    make_dist(name="foo", version="0.1.3")
    ext_path = tmp_path / "ext"
    ext_path.mkdir()
    path = make_dist(scratch_path=ext_path, name="foo", version="0.1.2", callback=None)
    dist = JohnnyDist(path)
    assert dist.specifier == "==0.1.2"
    assert dist.versions_available == ["0.1.1", "0.1.2", "0.1.3"]


def test_ignore_errors_version_attrs(mocker):
    mocker.patch("johnnydep.lib._get_info", side_effect=Exception)
    mocker.patch("unearth.finder.PackageFinder.find_all_packages", return_value=[])
    dist = JohnnyDist("notexist", ignore_errors=True)
    assert dist.version_latest is None
