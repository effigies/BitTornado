#!/usr/bin/env python3
#
# Replace the suggested filename for the target of a .torrent file
#
# 2013 Chris Johnson
#
# Original written by Henry 'Pi' James
# see LICENSE.txt for license information

import sys
import os
import getopt
from BitTornado.Meta.Info import MetaInfo

VERSION = '20130326'


def rename(fname, newname, verbose=False):
    metainfo = MetaInfo.read(fname)

    if verbose:
        print("{}: {} -> {}".format(fname, metainfo['info']['name'], newname))

    metainfo['info']['name'] = newname

    metainfo.write(fname)


def main(argv):
    prog, _ = os.path.splitext(os.path.basename(argv[0]))
    helpmsg = """Usage: {0} [-v] TORRENT NAME
       {0} [-m] TORRENT [...]

Change the suggested filename in a .torrent file

    --help      display this help and exit
    --match     set suggested filename to match .torrent file name
    --verbose   print old and new file name
    --version   print program version
    """.format(prog)

    try:
        opts, args = getopt.getopt(
            argv[1:], "hmvV", ["help", "match", "verbose", "version"])
    except getopt.error as msg:
        print(msg)
        return 0

    verbose = False
    match = False

    for opt, _ in opts:
        if opt in ('-h', '--help'):
            print(helpmsg)
            return 0
        elif opt in ('-m', '--match'):
            match = True
        elif opt in ('-v', '--verbose'):
            verbose = True
        elif opt in ('-V', '--version'):
            print(' '.join((prog, VERSION)))
            return 0

    if match and not args or not match and len(args) != 2:
        print(helpmsg)
        return 2        # common exit code for syntax error

    if match:
        for fname in args:
            newname, torrent = os.path.splitext(fname)
            if torrent == '.torrent':
                rename(fname, newname, verbose)
            else:
                print("{} does not appear to be a .torrent file".format(fname))
        return 0

    fname, newname = args
    rename(fname, newname, verbose)

    return 0

sys.exit(main(sys.argv))
