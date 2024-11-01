import json
import os
from argparse import ArgumentTypeError
from collections import deque
from pathlib import Path
from subprocess import CalledProcessError
from subprocess import check_output

import structlog
import unearth

from . import env_check


log = structlog.get_logger()


def python_interpreter(path):
    sub_env = os.environ.copy()
    sub_env["PYTHONPATH"] = str(Path(unearth.__file__).parent.parent)
    sub_env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        env_json = check_output(
            [path, env_check.__file__],
            env=sub_env,
        )
    except CalledProcessError:
        raise ArgumentTypeError("Invalid python env call")
    try:
        env = json.loads(env_json.decode())
    except json.JSONDecodeError:
        raise ArgumentTypeError("Invalid python env output")
    for k, v in env.items():
        if isinstance(v, list):
            # make result hashable
            env[k] = tuple(v)
    return tuple(env.items())


class CircularMarker:
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
        self.parents = [parent]
        self.children = []
        self.log = structlog.get_logger()

    def __getattr__(self, name):
        if name.startswith("_"):
            return super(CircularMarker, self).__getattribute__(name)


def _bfs(jdist):
    seen = set()
    q = deque([jdist])
    while q:
        jd = q.popleft()
        pk = id(jd)
        if pk not in seen:
            seen.add(pk)
            yield jd
            q += jd.children


def _un_none(d):
    # toml can't serialize None
    return {k: v for k, v in d.items() if v is not None}
