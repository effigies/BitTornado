#!/usr/bin/env python

# btreannounce.py written by Henry 'Pi' James and Bram Cohen
# multitracker extensions by John Hoffman
# see LICENSE.txt for license information

import sys
import os
import getopt
from BitTornado.bencode import bdecode
from BitTornado.reannounce import reannounce

def main(argv):
    program, ext = os.path.splitext(os.path.basename(argv[0]))
    usage = "Usage: %s <source.torrent> <file1.torrent> " \
            "[file2.torrent...]" % program
    desc = 'copies announce information from source to all specified torrents'

    try:
        opts, args = getopt.getopt(argv[1:], "hv",
                        ("help", "verbose"))
    except getopt.error, msg:
        print msg
        return 1

    if len(args) < 2:
        print "%s\n%s\n" % usage, desc
        return 2

    with open(args[0],'rb') as metainfo_file:
        source_metainfo = bdecode(metainfo_file.read())
    
    verbose = False

    for opt, arg in opts:
        if opt in ('-h','--help'):
            print "%s\n%s\n" % usage, desc
            return 0
        elif opt in ('-v','--verbose'):
            verbose = True

    announce = source_metainfo['announce']
    announce_list = source_metainfo.get('announce-list')

    if verbose:
        print 'new announce: ' + announce
        if announce_list:
            print 'new announce-list: ' +
                '|'.join(','.join(tier) for tier in announce_list)


    for fname in args[1:]:
        reannounce(fname, announce, announce_list, verbose)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
