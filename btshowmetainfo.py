#!/usr/bin/env python3

# Written by Henry 'Pi' James and Loring Holden
# modified for multitracker display by John Hoffman
# see LICENSE.txt for license information

import sys
import os
import hashlib
from BitTornado.Meta.Info import MetaInfo
from BitTornado.Meta.bencode import bencode

NAME, EXT = os.path.splitext(os.path.basename(sys.argv[0]))
VERSION = '20130326'

print('{} {} - decode BitTorrent metainfo files'.format(NAME, VERSION))
print()

if len(sys.argv) == 1:
    print('{} file1.torrent file2.torrent file3.torrent ...'.format(
          sys.argv[0]))
    print()
    sys.exit(2)     # common exit code for syntax error

for metainfo_name in sys.argv[1:]:
    metainfo = MetaInfo.read(metainfo_name)
    info = metainfo['info']
    info_hash = hashlib.sha1(bencode(info))

    print('metainfo file.:', os.path.basename(metainfo_name))
    print('info hash.....:', info_hash.hexdigest())
    piece_length = info['piece length']
    if 'length' in info:
        # let's assume we just have a file
        print('file name.....:', info['name'])
        file_length = info['length']
        name = 'file size.....:'
    else:
        # let's assume we have a directory structure
        print('directory name:', info['name'])
        print('files.........:')
        file_length = 0
        for file in info['files']:
            path = ''
            for item in file['path']:
                if path != '':
                    path = path + "/"
                path = path + item
            print('   {} ({:d})'.format(path, file['length']))
            file_length += file['length']
            name = 'archive size..:'
    piece_number, last_piece_length = divmod(file_length, piece_length)
    print('{} {:d} ({:d} * {:d} + {:d})'.format(
          name, file_length, piece_number, piece_length, last_piece_length))
    print('announce url..:', metainfo['announce'])
    if 'announce-list' in metainfo:
        announce_list = '|'.join(','.join(tier)
                                 for tier in metainfo['announce-list'])
        print('announce-list.:', announce_list)
    if 'httpseeds' in metainfo:
        print('http seeds....:', '|'.join(metainfo['httpseeds']))
    if 'comment' in metainfo:
        print('comment.......:', metainfo['comment'])
