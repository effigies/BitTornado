#!/usr/bin/env python

# Written by Henry 'Pi' James and Bram Cohen
# multitracker extensions by John Hoffman
# see LICENSE.txt for license information

import sys
import os
import getopt
from BitTornado.bencode import bencode, bdecode
from BitTornado.BT1.makemetafile import announcelist_details

announce_details = """
  Where:
    announce = tracker URL
        Example: http://www.tracker.com:6699/announce
"""

def reannounce(fname, announce, announce_list = None, verbose = False):
    metainfo_file = open(fname, 'rb')
    metainfo = bdecode(metainfo_file.read())
    metainfo_file.close()

    if verbose:
        print 'old announce for %s: %s' % (fname, metainfo['announce'])
    
    metainfo['announce'] = announce
    
    if metainfo.has_key('announce-list'):
        if verbose:
            print 'old announce-list for %s: %s' % (fname,
                '|'.join(','.join(tier) for tier in metainfo['announce-list']))
        if announce_list is not None:
            metainfo['announce-list'] = announce_list
        else:
            try:
                del metainfo['announce-list']
            except:
                pass
            
    metainfo_file = open(fname, 'wb')
    metainfo_file.write(bencode(metainfo))
    metainfo_file.close()

def main(argv):
    program, ext = os.path.splitext(os.path.basename(argv[0]))
    usage = "Usage: %s <announce> [--announce_list <arg>] " \
            "file1.torrent [file2.torrent...]" % program
    help =  "%s\n%s\n%s" % (usage, announce_details, '\n'.join(' ' * 4 + l
            for l in announcelist_details.split('\n')[:-2]))

    try:
        opts, args = getopt.getopt(argv[1:], "hav",
                        ("help","announce_list","verbose"))
    except getopt.error, msg:
        print msg
        return 1

    if len(args) < 2:
        print help
        return 2
    
    announce        = args[0]
    announce_list   = None
    verbose         = False

    for opt, arg in opts:
        if opt in ('-h','--help'):
            print help
            return 0
        elif opt in ('-a','--announce_list'):
            announce_list = [tier.split(',') for tier in arg.split('|')]
        elif opt in ('-v','--verbose'):
            verbose = True

    for fname in args[1:]:
        reannounce(fname, announce, announce_list, verbose)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
