from argparse import ArgumentParser

import tabulate

from johnnydep.lib import gen_table
from johnnydep.lib import JohnnyDist
from johnnydep.logs import configure_logging


def main():
    parser = ArgumentParser()
    parser.add_argument('req')
    parser.add_argument('--upgrade', '-U', action='store_true')
    parser.add_argument('--verbose', '-v', default=0, action='count')
    parser.add_argument('--extra', '-e', nargs='*', default=['summary'], choices=[
        'summary', 'specifier', 'provides', 'homepage', 'options', 'installed', 'latest',
    ])
    args = parser.parse_args()
    configure_logging(verbosity=args.verbose)
    dist = JohnnyDist(args.req)
    table = gen_table(dist, extra_cols=args.extra)
    tabulate.PRESERVE_WHITESPACE = True
    print(tabulate.tabulate(table, headers='keys'))


if __name__ == '__main__':
    main()
