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

from sys import argv, version, exit
from os.path import split
assert version >= '2', "Install Python 2.0 or greater"
from BitTornado.BT1.makemetafile import make_meta_file, defaults, print_announcelist_details
from BitTornado.parseargs import parseargs, formatDefinitions


def prog(amount):
    print '%.1f%% complete\r' % (amount * 100),

if len(argv) < 3:
    a,b = split(argv[0])
    print 'Usage: ' + b + ' <trackerurl> <file> [file...] [params...]'
    print
    print formatDefinitions(defaults, 80)
    print_announcelist_details()
    print ('')
    exit(2)

try:
    config, args = parseargs(argv[1:], defaults, 2, None)
    for file in args[1:]:
        make_meta_file(file, args[0], config, progress = prog)
except ValueError, e:
    print 'error: ' + str(e)
    print 'run with no args for parameter explanations'
