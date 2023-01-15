from textwrap import dedent

from johnnydep.lib import JohnnyDist


def test_dot_export(make_dist):
    deps = ["child>0.1"]
    extras = {"x": ["extra"]}
    make_dist(name="parent", install_requires=deps, extras_require=extras)
    make_dist(name="child")
    make_dist(name="Extra")
    dist = JohnnyDist("parent[x]")
    child, extra = dist.children
    expected = dedent(
        """
        digraph tree {
            "%(parent)s" [label="parent[x]"];
            "%(child)s" [label="child"];
            "%(extra)s" [label="Extra"];
            "%(parent)s" -> "%(child)s" [label=">0.1"];
            "%(parent)s" -> "%(extra)s";
        }
        """
    ).strip()
    expected %= {
        "parent": hex(id(dist)),
        "child": hex(id(child)),
        "extra": hex(id(extra)),
    }
    assert dist.serialise(format="dot") == expected
