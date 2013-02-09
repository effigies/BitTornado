#!/usr/bin/env python
#
# Replace the suggested filename for the target of a .torrent file
#
# 2012 Chris Johnson
# 
# Original written by Henry 'Pi' James
# see LICENSE.txt for license information

import sys
import os
import getopt
from BitTornado.bencode import bencode, bdecode

VERSION = '20120601'

def rename(fname, newname, verbose = False):
    with open(fname, 'rb') as metainfo_file:
        metainfo = bdecode(metainfo_file.read())

    if verbose:
        print "%s: %s -> %s" % (fname, metainfo['info']['name'], newname)

    metainfo['info']['name'] = newname

    with open(fname, 'wb') as metainfo_file:
        metainfo_file.write(bencode(metainfo))

def main(argv):
    prog, ext = os.path.splitext(os.path.basename(argv[0]))
    help = """Usage: %s [-v] TORRENT NAME
       %s [-m] TORRENT [...]

Change the suggested filename in a .torrent file

    --help      display this help and exit
    --match     set suggested filename to match .torrent file name
    --verbose   print old and new file name
    --version   print program version
    """ % (prog,prog)

    try:
        opts, args = getopt.getopt(argv[1:], "hmvV",
                        ["help","match","verbose","version"])
    except getopt.error, msg:
        print msg
        return 0

    verbose     = False
    match       = False

    for opt, arg in opts:
        if opt in ('-h','--help'):
            print help
            return 0
        elif opt in ('-m','--match'):
            match = True
        elif opt in ('-v','--verbose'):
            verbose = True
        elif opt in ('-V','--version'):
            print "%s %s" % (prog,VERSION)
            return 0

    if match:
        if len(args) == 0:
            print help
            return 2
        for fname in args:
            newname, torrent = os.path.splitext(fname)
            if torrent == '.torrent':
                rename(fname, newname, verbose)
            else:
                print "%s does not appear to be a .torrent file" % fname
    else:
        if len(args) != 2:
            print help
            return 2 # common exit code for syntax error

        fname, newname = args

        rename(fname, newname, verbose)

    return 0

sys.exit(main(sys.argv))
