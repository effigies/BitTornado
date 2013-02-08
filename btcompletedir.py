#!/usr/bin/env python

# Written by Bram Cohen
# see LICENSE.txt for license information

import sys
assert sys.version >= '2', "Install Python 2.0 or greater"
import os
from BitTornado.BT1.makemetafile import defaults, completedir, announcelist_details
from BitTornado.parseargs import parseargs, formatDefinitions

def main(argv):
    program, ext = os.path.splitext(os.path.basename(argv[0]))
    usage = "Usage: %s <trackerurl> <dir> [dir...] [params...]" % program
    desc = "Makes a .torrent file for every file or directory present in each dir."

    if len(argv) < 3:
        print "%s\n%s\n%s%s" % (usage, desc,
                            formatDefinitions(defaults, 80),
                            announcelist_details)
        return 2

    try:
        config, args = parseargs(argv[1:], defaults, 2, None)
        for dir in args[1:]:
            completedir(dir, args[0], config)
    except ValueError, e:
        print 'error: ' + str(e)
        print 'run with no args for parameter explanations'
        return 1

    return 0

sys.exit(main(sys.argv))
