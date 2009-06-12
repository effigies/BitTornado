#!/usr/bin/env python

# btreannounce.py written by Henry 'Pi' James and Bram Cohen
# multitracker extensions by John Hoffman
# see LICENSE.txt for license information

from sys import argv,exit
from os.path import split
from BitTornado.bencode import bencode, bdecode


def give_announce_list(l):
    list = []
    for tier in l:
        for tracker in tier:
            list+=[tracker,',']
        del list[-1]
        list+=['|']
    del list[-1]
    liststring = ''
    for i in list:
        liststring+=i
    return liststring


if len(argv) < 3:
    a,b = split(argv[0])
    print 'Usage: ' + b + ' <source.torrent> <file1.torrent> [file2.torrent...]'
    print 'copies announce information from source to all specified torrents'
    exit(2) # common exit code for syntax error

h = open(argv[1], 'rb')
source_metainfo = bdecode(h.read())
h.close()

print 'new announce: ' + source_metainfo['announce']
if source_metainfo.has_key('announce-list'):
    print 'new announce-list: ' + give_announce_list(source_metainfo['announce-list'])


for f in argv[2:]:
    h = open(f, 'rb')
    metainfo = bdecode(h.read())
    h.close()
    print 'old announce for %s: %s' % (f, metainfo['announce'])
    metainfo['announce'] = source_metainfo['announce']
    if metainfo.has_key('announce-list'):
        print 'old announce-list for %s: %s' % (f, give_announce_list(metainfo['announce-list']))
    if source_metainfo.has_key('announce-list'):
        metainfo['announce-list'] = source_metainfo['announce-list']
    elif metainfo.has_key('announce-list'):
        try:
            del metainfo['announce-list']
        except:
            pass
        
    h = open(f, 'wb')
    h.write(bencode(metainfo))
    h.close()
