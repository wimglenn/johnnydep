from __future__ import unicode_literals, print_function

from argparse import ArgumentParser
from collections import OrderedDict

import tabulate

from johnnydep.lib import DEFAULT_INDEX
from johnnydep.lib import JohnnyDist
from johnnydep.lib import gen_table
from johnnydep.logs import configure_logging

FIELDS = OrderedDict([
    # (attribute, help)
    ('summary', 'Short description of the distribution'),
    ('specifier', 'Requirement specifier (see PEP 508) e.g. ~=1.7'),
    ('import_names', 'Python imports provided (top-level names only)'),
    ('homepage', 'Project URL'),
    ('extras_available', 'Optional extensions available for the distribution'),
    ('extras_requested', 'Optional extensions parsed from requirement specifier'),
    ('project_name', 'Usually matches the canonical name but may have different case'),
    ('versions_available', 'List of versions available at index'),
    ('version_installed', 'Version currently installed, if any'),
    ('version_latest', 'Latest version available'),
    ('version_latest_in_spec', 'Best version: latest available within requirement specifier'),
    ('download_link', 'Source or binary distribution URL'),
    ('checksum', 'Source or binary distribution hash'),
])


def main():
    parser = ArgumentParser()
    parser.add_argument('req', help='The project name or requirement specifier')
    parser.add_argument('--verbose', '-v', default=0, action='count')
    parser.add_argument('--index-url', '-i', default=DEFAULT_INDEX)
    parser.add_argument('--output-format', '-o', choices=['json', 'yaml', 'text', 'python', 'toml'], default='text')
    parser.add_argument('--flat', help='Flatten and resolve dependencies', action='store_true')
    parser.add_argument('--fields', '-f', nargs='*', default=['summary'], choices=list(FIELDS) + ['ALL'])
    args = parser.parse_args()
    if 'ALL' in args.fields:
        args.fields = list(FIELDS)
    configure_logging(verbosity=args.verbose)
    dist = JohnnyDist(args.req, index_url=args.index_url)
    if args.output_format == 'text':
        table = gen_table(dist, extra_cols=args.fields)
        tabulate.PRESERVE_WHITESPACE = True
        print(tabulate.tabulate(table, headers='keys'))
    else:
        print(dist.serialise(fields=args.fields, format=args.output_format))
