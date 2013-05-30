#!/usr/bin/env python3
'Copy announce URLs from one torrent to others'

# btreannounce.py written by Henry 'Pi' James and Bram Cohen
# multitracker extensions by John Hoffman
# see LICENSE.txt for license information

import sys
import os
import getopt
from BitTornado.Meta.Info import MetaInfo
from BitTornado.Application.reannounce import reannounce


def main(argv):
    """Copy announce information from source to all specified torrents"""
    program, _ = os.path.splitext(os.path.basename(argv[0]))
    usage = "Usage: %s <source.torrent> <file1.torrent> " \
            "[file2.torrent...]" % program
    try:
        opts, args = getopt.getopt(argv[1:], "hv",
                                   ("help", "verbose"))
    except getopt.error as msg:
        print(msg)
        return 1

    if len(args) < 2:
        print("{}\n{}\n".format(usage, main.__doc__))
        return 2

    source_metainfo = MetaInfo.read(args[0])

    verbose = False

    for opt, _ in opts:
        if opt in ('-h', '--help'):
            print("{}\n{}\n".format(usage, main.__doc__))
            return 0
        elif opt in ('-v', '--verbose'):
            verbose = True

    announce = source_metainfo['announce']
    announce_list = source_metainfo.get('announce-list')

    if verbose:
        print('new announce: ', announce)
        if announce_list:
            print('new announce-list: ',
                  '|'.join(','.join(tier) for tier in announce_list))

    for fname in args[1:]:
        reannounce(fname, announce, announce_list, verbose)

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
