#!/usr/bin/env python3
"Make a .torrent file for every file or directory in each given directory."

# Written by Bram Cohen
# see LICENSE.txt for license information

import sys
import os
from BitTornado.Application.makemetafile import defaults, completedir, \
    announcelist_details
from BitTornado.Application.parseargs import parseargs, formatDefinitions


def main(cmd, *argv):
    "Make a .torrent file for every file or directory in each given directory."
    program, _ = os.path.splitext(os.path.basename(cmd))
    usage = "Usage: %s <trackerurl> <dir> [dir...] [params...]" % program
    desc = __doc__

    if len(argv) < 2:
        print("{}\n{}\n{}{}".format(usage, desc,
                                    formatDefinitions(defaults, 80),
                                    announcelist_details))
        return 2

    try:
        config, args = parseargs(argv, defaults, 2, None)
        for directory in args[1:]:
            completedir(directory, args[0], config)
    except ValueError as error:
        print('error: ', error)
        print('run with no args for parameter explanations')
        return 1

    return 0

sys.exit(main(*sys.argv))
