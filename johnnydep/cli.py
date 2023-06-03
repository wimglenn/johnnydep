# coding: utf-8
from __future__ import print_function
from __future__ import unicode_literals

import os
import sys
from argparse import ArgumentParser

import johnnydep
from johnnydep.compat import dict
from johnnydep.lib import JohnnyDist, has_error
from johnnydep.logs import configure_logging
from johnnydep.util import python_interpreter


FIELDS = dict(
    [
        # (attribute, help)
        ("name", "Canonical name of the distribution"),
        ("summary", "Short description of the distribution"),
        ("specifier", "Requirement specifier (see PEP 508) e.g. ~=1.7"),
        ("requires", "Immediate dependencies"),
        ("required_by", "Parent(s) in the tree"),
        ("import_names", "Python imports provided (top-level names only)"),
        ("console_scripts", "Entry points in the console_scripts group"),
        ("homepage", "Project URL"),
        ("extras_available", "Optional extensions available for the distribution"),
        ("extras_requested", "Optional extensions parsed from requirement specifier"),
        ("project_name", "Usually matches the canonical name but may have different case"),
        ("license", "License covering the distribution"),
        ("versions_available", "List of versions available at index"),
        ("version_installed", "Version currently installed, if any"),
        ("version_latest", "Latest version available"),
        ("version_latest_in_spec", "Best version: latest available within requirement specifier"),
        ("download_link", "Source or binary distribution URL"),
        ("checksum", "Source or binary distribution hash"),
    ]
)


def main(argv=None, stdout=None):
    default_fields = os.environ.get("JOHNNYDEP_FIELDS", "name,summary").split(",")
    parser = ArgumentParser(prog="johnnydep", description=johnnydep.__doc__)
    parser.add_argument(
        "req",
        help=(
            "The project name or requirement specifier. "
            "Looks like what might you normally put after a 'pip install' "
            "command (use PEP 440 syntax)."
        ),
    )
    parser.add_argument(
        "--index-url",
        "-i",
        metavar="<url>",
        help=(
            "Base URL of the Python Package Index (default https://pypi.org/simple). "
            "This should point to a repository compliant with PEP 503 (the simple "
            "repository API) or a local directory laid out in the same format."
        ),
    )
    parser.add_argument(
        "--extra-index-url",
        metavar="<url>",
        help=(
            "Extra URLs of package indexes to use in addition to --index-url. "
            "Should follow the same rules as --index-url."
        ),
    )
    parser.add_argument(
        "--ignore-errors",
        action="store_true",
        help="Continue rendering the tree even if errors occur.",
    )
    parser.add_argument(
        "--output-format",
        "-o",
        choices=["human", "json", "yaml", "python", "toml", "pinned", "dot"],
        default="human",
        help="Format to render the output (default: %(default)s).",
    )
    parser.add_argument(
        "--no-deps",
        help="Show top level details only, don't recurse the dependency tree.",
        dest="recurse",
        action="store_false",
    )
    parser.add_argument(
        "--fields",
        "-f",
        nargs="*",
        default=default_fields,
        choices=list(FIELDS) + ["ALL"],
        help=(
            "Space separated list of fields to print "
            "(default: {}).".format(" ".join(default_fields))
        ),
    )
    parser.add_argument(
        "--for-python",
        "-p",
        dest="env",
        type=python_interpreter,
        metavar="<path>",
        help=(
            "Path to another Python executable. "
            "If unspecified, the current runtime environment will be used "
            "(i.e. {}).".format(sys.executable)
        ),
    )
    parser.add_argument(
        "--verbose",
        "-v",
        default=1,
        type=int,
        choices=range(3),
        help="0 for less logging, 2 for more logging",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s v{}".format(johnnydep.__version__),
    )
    args = parser.parse_args(argv)
    if "ALL" in args.fields:
        args.fields = list(FIELDS)
    configure_logging(verbosity=args.verbose)
    dist = JohnnyDist(
        args.req,
        index_url=args.index_url,
        env=args.env,
        extra_index_url=args.extra_index_url,
        ignore_errors=args.ignore_errors,
    )
    rendered = dist.serialise(
        fields=args.fields,
        format=args.output_format,
        recurse=args.recurse,
    )
    print(rendered, file=stdout)
    if (args.recurse and has_error(dist)) or (not args.recurse and dist.error is not None):
        sys.exit(1)
