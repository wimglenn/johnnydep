import os

from anytree.exporter import UniqueDotExporter


def nodeattrfunc(node):
    label = node._name_with_extras(attr="project_name")
    return 'label="{}"'.format(label)


def edgeattrfunc(parent, child):
    spec = child.req.specifier
    if spec:
        return 'label="{}"'.format(spec)


def jd2dot(dist):
    """exports johnnydist to graphviz DOT language
    https://graphviz.org/doc/info/lang.html
    nodes will be labeled with the project name [+extras]
    edges will be labeled with any requirement constraints
    """
    dot_exporter = UniqueDotExporter(
        dist,
        nodeattrfunc=nodeattrfunc,
        edgeattrfunc=edgeattrfunc,
    )
    return os.linesep.join(dot_exporter)
