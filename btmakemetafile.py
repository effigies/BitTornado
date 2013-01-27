#!/usr/bin/env python

# Written by Bram Cohen
# multitracker extensions by John Hoffman
# see LICENSE.txt for license information

from BitTornado import PSYCO
if PSYCO.psyco:
    try:
        import psyco
        assert psyco.__version__ >= 0x010100f0
        psyco.full()
    except:
        pass

import sys
import os
assert sys.version >= '2', "Install Python 2.0 or greater"
from BitTornado.BT1.makemetafile import make_meta_file, defaults, announcelist_details
from BitTornado.parseargs import parseargs, formatDefinitions


def prog(amount):
    print '%.1f%% complete\r' % (amount * 100),

def main(argv):
    program, ext = os.path.splitext(os.path.basename(argv[0]))
    usage = "Usage: %s <trackerurl> <file> [file...] [params...]" % program

    if len(argv) < 3:
        print "%s\n\n%s%s" % (usage,
                            formatDefinitions(defaults, 80),
                            announcelist_details)
        return 2

    try:
        config, args = parseargs(argv[1:], defaults, 2, None)
        for file in args[1:]:
            make_meta_file(file, args[0], config.copy(), progress = prog)
    except ValueError, e:
        print 'error: ' + str(e)
        print 'run with no args for parameter explanations'

    return 0

sys.exit(main(sys.argv))
