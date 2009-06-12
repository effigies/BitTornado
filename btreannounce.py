#!/usr/bin/env python

# Written by Henry 'Pi' James and Bram Cohen
# multitracker extensions by John Hoffman
# see LICENSE.txt for license information

from sys import argv,exit
from os.path import split
from BitTornado.bencode import bencode, bdecode

if len(argv) < 3:
    a,b = split(argv[0])
    print ('Usage: ' + b + ' <announce> [--announce_list <arg>] file1.torrent [file2.torrent...]')
    print ('')
    print ('  Where:')
    print ('    announce = tracker URL')
    print ('           Example: http://www.tracker.com:6699/announce')
    print ('')
    print ('    announce_list = optional list of redundant/backup tracker URLs, in the format:')
    print ('           url[,url...][|url[,url...]...]')
    print ('                where URLs separated by commas are all tried first')
    print ('                before the next group of URLs separated by the pipe is checked.')
    print ("                If none is given, it is assumed you don't want one in the metafile.")
    print ('                If announce-list is given, clients which support it')
    print ('                will ignore the <announce> value.')
    print ('           Examples:')
    print ('                http://tracker1.com|http://tracker2.com|http://tracker3.com')
    print ('                     (tries trackers 1-3 in order)')
    print ('                http://tracker1.com,http://tracker2.com,http://tracker3.com')
    print ('                     (tries trackers 1-3 in a randomly selected order)')
    print ('                http://tracker1.com|http://backup1.com,http://backup2.com')
    print ('                     (tries tracker 1 first, then tries between the 2 backups randomly)')
    print ('')
    exit(2) # common exit code for syntax error

announce = argv[1]
announce_list = []
if argv[2] == '--announce_list':
    for tier in argv[3].split('|'):
        sublist = []
        for tracker in tier.split(','):
            sublist += [tracker]
        announce_list += [sublist]
    if len(argv) < 5:
        print ('error: no .torrent files given')
        print ('')
        exit(2)
    argv = argv[2:]
    

for f in argv[2:]:
    h = open(f, 'rb')
    metainfo = bdecode(h.read())
    h.close()
    print 'old announce for %s: %s' % (f, metainfo['announce'])
    metainfo['announce'] = announce
    if metainfo.has_key('announce-list'):
        list = []
        for tier in metainfo['announce-list']:
            for tracker in tier:
                list+=[tracker,',']
            del list[-1]
            list+=['|']
        del list[-1]
        liststring = ''
        for i in list:
            liststring+=i
        print 'old announce-list for %s: %s' % (f, liststring)
    if len(announce_list) > 0:
        metainfo['announce-list'] = announce_list
    elif metainfo.has_key('announce-list'):
        try:
            del metainfo['announce-list']
        except:
            pass
        
    h = open(f, 'wb')
    h.write(bencode(metainfo))
    h.close()
