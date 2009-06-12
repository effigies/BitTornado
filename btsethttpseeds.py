#!/usr/bin/env python

# Written by Henry 'Pi' James and Bram Cohen
# multitracker extensions by John Hoffman
# see LICENSE.txt for license information

from sys import argv,exit
from os.path import split
from BitTornado.bencode import bencode, bdecode

if len(argv) < 3:
    a,b = split(argv[0])
    print ('Usage: ' + b + ' <http-seeds> file1.torrent [file2.torrent...]')
    print ('')
    print ('  Where:')
    print ('    http-seeds = list of seed URLs, in the format:')
    print ('           url[|url...] or 0')
    print ('                if the list is a zero, any http seeds will be stripped.')
    print ('')
    exit(2) # common exit code for syntax error

seeds = argv[1]
if seeds == '0':
    seedlist = None
else:
    seedlist = seeds.split('|')

for f in argv[2:]:
    h = open(f, 'rb')
    metainfo = bdecode(h.read())
    h.close()
    if metainfo.has_key('httpseeds'):
        list = []
        for url in metainfo['httpseeds']:
            list += [url,'|']
        del list[-1]
        liststring = ''
        for i in list:
            liststring += i
        print 'old http-seed list for %s: %s' % (f, liststring)
        if not seedlist:
            del metainfo['httpseeds']
    if seedlist:
        metainfo['httpseeds'] = seedlist

    h = open(f, 'wb')
    h.write(bencode(metainfo))
    h.close()
