#!/usr/bin/env python

# Written by Henry 'Pi' James and Loring Holden
# modified for multitracker display by John Hoffman
# see LICENSE.txt for license information

import sys
import os
import sha
from BitTornado.bencode import bencode, bdecode

NAME, EXT = os.path.splitext(os.path.basename(sys.argv[0]))
VERSION = '20030621'

print '%s %s - decode BitTorrent metainfo files' % (NAME, VERSION)
print

if len(sys.argv) == 1:
    print '%s file1.torrent file2.torrent file3.torrent ...' % sys.argv[0]
    print
    sys.exit(2) # common exit code for syntax error

for metainfo_name in sys.argv[1:]:
    metainfo_file = open(metainfo_name, 'rb')
    metainfo = bdecode(metainfo_file.read())
#    print metainfo
    info = metainfo['info']
    info_hash = sha.sha(bencode(info))

    print 'metainfo file.: %s' % os.path.basename(metainfo_name)
    print 'info hash.....: %s' % info_hash.hexdigest()
    piece_length = info['piece length']
    if 'length' in info:
        # let's assume we just have a file
        print 'file name.....: %s' % info['name']
        file_length = info['length']
        name ='file size.....:'
    else:
        # let's assume we have a directory structure
        print 'directory name: %s' % info['name']
        print 'files.........: '
        file_length = 0;
        for file in info['files']:
            path = ''
            for item in file['path']:
                if (path != ''):
                   path = path + "/"
                path = path + item
            print '   %s (%d)' % (path, file['length'])
            file_length += file['length']
            name ='archive size..:'
    piece_number, last_piece_length = divmod(file_length, piece_length)
    print '%s %i (%i * %i + %i)' \
          % (name,file_length, piece_number, piece_length, last_piece_length)
    print 'announce url..: %s' % metainfo['announce']
    if 'announce-list' in metainfo:
        announce_list = '|'.join(','.join(tier)
                                for tier in metainfo['announce-list'])
        print 'announce-list.: %s' % announce_list
    if 'httpseeds' in metainfo:
        print 'http seeds....: %s' % '|'.join(metainfo['httpseeds'])
    if 'comment' in metainfo:
        print 'comment.......: %s' % metainfo['comment']
