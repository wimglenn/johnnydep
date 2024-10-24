"""Display dependency tree of Python distribution"""
from types import SimpleNamespace


config = SimpleNamespace(
    env=None,
    index_url=None,
    extra_index_url=None,
)

from .lib import *
