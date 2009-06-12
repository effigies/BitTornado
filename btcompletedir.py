#!/usr/bin/env python

# Written by Bram Cohen
# see LICENSE.txt for license information

from BitTornado import PSYCO
if PSYCO.psyco:
    try:
        import psyco
        assert psyco.__version__ >= 0x010100f0
        psyco.full()
    except:
        pass

from sys import argv, version, exit
assert version >= '2', "Install Python 2.0 or greater"
from os.path import split
from BitTornado.BT1.makemetafile import defaults, completedir, print_announcelist_details
from BitTornado.parseargs import parseargs, formatDefinitions


if len(argv) < 3:
    a,b = split(argv[0])
    print 'Usage: ' + b + ' <trackerurl> <dir> [dir...] [params...]'
    print 'makes a .torrent file for every file or directory present in each dir.'
    print
    print formatDefinitions(defaults, 80)
    print_announcelist_details()
    print ('')
    exit(2)

try:
    config, args = parseargs(argv[1:], defaults, 2, None)
    for dir in args[1:]:
        completedir(dir, args[0], config)
except ValueError, e:
    print 'error: ' + str(e)
    print 'run with no args for parameter explanations'
