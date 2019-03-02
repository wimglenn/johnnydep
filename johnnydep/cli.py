# coding: utf-8
from __future__ import print_function
from __future__ import unicode_literals

import os
from argparse import ArgumentParser
from collections import OrderedDict

from johnnydep.lib import JohnnyDist
from johnnydep.logs import configure_logging
from johnnydep.util import python_interpreter


FIELDS = OrderedDict(
    [
        # (attribute, help)
        ("name", "Canonical name of the distribution"),
        ("summary", "Short description of the distribution"),
        ("specifier", "Requirement specifier (see PEP 508) e.g. ~=1.7"),
        ("requires", "Immediate dependencies"),
        ("required_by", "Parent(s) in the tree"),
        ("import_names", "Python imports provided (top-level names only)"),
        ("homepage", "Project URL"),
        ("extras_available", "Optional extensions available for the distribution"),
        ("extras_requested", "Optional extensions parsed from requirement specifier"),
        ("project_name", "Usually matches the canonical name but may have different case"),
        ("versions_available", "List of versions available at index"),
        ("version_installed", "Version currently installed, if any"),
        ("version_latest", "Latest version available"),
        ("version_latest_in_spec", "Best version: latest available within requirement specifier"),
        ("download_link", "Source or binary distribution URL"),
        ("checksum", "Source or binary distribution hash"),
    ]
)


def main():
    default_fields = os.environ.get("JOHNNYDEP_FIELDS", "name,summary").split(",")
    parser = ArgumentParser()
    parser.add_argument("req", help="The project name or requirement specifier")
    parser.add_argument("--index-url", "-i")
    parser.add_argument("--extra-index-url")
    parser.add_argument(
        "--output-format",
        "-o",
        choices=["human", "json", "yaml", "python", "toml", "pinned"],
        default="human",
    )
    parser.add_argument(
        "--no-deps", help="Don't recurse the dependency tree", dest="recurse", action="store_false"
    )
    parser.add_argument(
        "--fields", "-f", nargs="*", default=default_fields, choices=list(FIELDS) + ["ALL"]
    )
    parser.add_argument("--for-python", "-p", dest="env", type=python_interpreter)
    parser.add_argument("--verbose", "-v", default=1, type=int, choices=range(3))
    args = parser.parse_args()
    if "ALL" in args.fields:
        args.fields = list(FIELDS)
    configure_logging(verbosity=args.verbose)
    dist = JohnnyDist(args.req, index_url=args.index_url, env=args.env, extra_index_url=args.extra_index_url)
    print(dist.serialise(fields=args.fields, format=args.output_format, recurse=args.recurse))
