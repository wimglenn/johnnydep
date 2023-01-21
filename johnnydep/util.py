# coding: utf-8
from __future__ import unicode_literals

import json
import structlog
from argparse import ArgumentTypeError
from subprocess import check_output
from subprocess import CalledProcessError

import anytree

from johnnydep import env_check
from johnnydep.compat import JSONDecodeError


def python_interpreter(path):
    try:
        env_json = check_output([path, env_check.__file__])
    except CalledProcessError:
        raise ArgumentTypeError("Invalid python env call")
    try:
        env = json.loads(env_json.decode())
    except JSONDecodeError:
        raise ArgumentTypeError("Invalid python env output")
    frozen = tuple(map(tuple, env))
    return frozen


class CircularMarker(anytree.NodeMixin):
    """
    This is like a "fake" JohnnyDist instance which is used
    to render a node in circular dep trees like:

    a
    └── b
        └── c
            └── ...

    Everything is null except the req/name which is "..." and
    the metadata summary, which can be provided by the caller
    """
    glyph = "..."

    def __init__(self, summary, parent):
        self.req = CircularMarker.glyph
        self.name = CircularMarker.glyph
        self.summary = summary
        self.parent = parent
        self.log = structlog.get_logger()

    def __getattr__(self, name):
        if name.startswith("_"):
            return super(CircularMarker, self).__getattribute__(name)
