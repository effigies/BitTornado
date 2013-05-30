#!/usr/bin/env python3

# Written by Bram Cohen
# multitracker extensions by John Hoffman
# see LICENSE.txt for license information

import sys
import os
from BitTornado.Application.makemetafile import make_meta_file, defaults, \
    announcelist_details
from BitTornado.Application.parseargs import parseargs, formatDefinitions


def prog(amount):
    print('%.1f%% complete\r' % (amount * 100))


def main(argv):
    program, _ = os.path.splitext(os.path.basename(argv[0]))
    usage = "Usage: %s <trackerurl> <file> [file...] [params...]" % program

    if len(argv) < 3:
        print("{}\n\n{}{}".format(usage, formatDefinitions(defaults, 80),
                                  announcelist_details))
        return 2

    try:
        config, args = parseargs(argv[1:], defaults, 2, None)
        for file in args[1:]:
            make_meta_file(file, args[0], config.copy(), progress=prog)
    except ValueError as e:
        print('error: ', e)
        print('run with no args for parameter explanations')

    return 0

sys.exit(main(sys.argv))
