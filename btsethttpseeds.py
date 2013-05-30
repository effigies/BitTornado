#!/usr/bin/env python3

# Written by Henry 'Pi' James and Bram Cohen
# multitracker extensions by John Hoffman
# see LICENSE.txt for license information

import sys
import os
import getopt
from BitTornado.Meta.Info import MetaInfo


def main(argv):
    program, _ = os.path.splitext(os.path.basename(argv[0]))
    usage = """Usage: %s <http-seeds> file1.torrent [file2.torrent...]

  Where:
    http-seeds = list of seed URLs, in the format:
        url[|url...] or 0
            if the list is a zero, any http seeds will be stripped.
""" % program

    try:
        opts, args = getopt.getopt(argv[1:], "hv", ("help", "verbose"))
    except getopt.error as msg:
        print(msg)
        return 1

    if len(args) < 2:
        print(usage)
        return 2

    http_seeds = None
    if args[0] != '0':
        http_seeds = args[0].split('|')

    verbose = False

    for opt, _ in opts:
        if opt in ('-h', '--help'):
            print(usage)
            return 0
        elif opt in ('-v', '--verbose'):
            verbose = True

    for fname in args[1:]:
        metainfo = MetaInfo.read(fname)

        if 'httpseeds' in metainfo:
            if verbose:
                print('old http-seed list for {}: {}'.format(
                    fname, '|'.join(metainfo['httpseeds'])))
            if http_seeds is None:
                del metainfo['httpseeds']

        if http_seeds is not None:
            metainfo['httpseeds'] = http_seeds

        metainfo.write(fname)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
