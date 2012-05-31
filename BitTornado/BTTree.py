#!/usr/bin/env python
# Written by Chris Johnson
#
# This is a generalization of the BitTorrent and BitTornado makemetafile.py
# files, which were respectively written by Bram Cohen and Jon Hoffman

import os
import sha
from BitTornado.bencode import bencode
from BitTornado.BT1.btformats import check_info
from time import time
try:
    from sys import getfilesystemencoding
    ENCODING = getfilesystemencoding()
except:
    from sys import getdefaultencoding
    ENCODING = getdefaultencoding()
    if not ENCODING:
        ENCODING = 'ascii'

# Generic utility functions
def uniconvertl(srclist, encoding):
    """Convert a list of strings to Unicode
    
    Parameters
        str[]   - Strings to be converted
        str     - Current string encoding
    
    Return
    	str[]   - Converted strings
    """
    r = []
    try:
        for src in srclist:
            r.append(uniconvert(src, encoding))
    except UnicodeError:
        raise UnicodeError('bad filename: '+os.path.join(srclist))
    return r

def uniconvert(src, encoding):
    """Convert a string to Unicode
    
    Parameters
        str     - String to be converted
        str     - Current string encoding
    
    Return
    	str     - Converted string
    """
    try:
        return unicode(src, encoding).encode('utf-8')
    except UnicodeError:
        raise UnicodeError('bad filename: ' + src)

class Info:
    """Info - information associated with a .torrent file
    
    Info attributes
        str     name            - name of file/dir being hashed
        long    size            - total size of files to be described
        long    piece_length    - size of pieces
        str[]   pieces          - sha1 digests of file parts
        sha1    sh              - sha1 hash object
        long    done            - portion of piece hashed
        dict[]  fs              - metadata about files described
        long    totalhashed     - portion of total data hashed
    """
    
    def __init__(self, source, size, **params):
        """
        Parameters
            str source  - source file name (last path element)
            int size    - total size of files to be described
        """
        self.encoding = ENCODING
        if 'encoding' in params:
            self.encoding = params['encoding']

        self.name = uniconvert(source,self.encoding)
        self.size = size

        # BitTorrent/BitTornado have traditionally allowed this parameter
        piece_len_exp = params.get('piece_size_pow2')
        if piece_len_exp is not None and piece_len_exp != 0:
            self.piece_length = 2 ** piece_len_exp
        else:
            self.piece_length = self.get_piece_len(size)

        # Universal
        self.pieces = []
        self.sh = sha.sha()
        self.done = 0L
        self.fs = []
        self.totalhashed = 0L
    
    def get_piece_len(self, size): 
        """Parameters
            long    size    - size of files described by torrent
        
        Return
            long            - size of pieces to hash
        """
        if   size > 8L*1024*1024*1024:  # > 8 gig =
            piece_len_exp = 21          #   2 meg pieces
        elif size > 2*1024*1024*1024:	# > 2 gig =
            piece_len_exp = 20          #   1 meg pieces
        elif size > 512*1024*1024:      # > 512M =
            piece_len_exp = 19          #   512K pieces
        elif size > 64*1024*1024:       # > 64M =
            piece_len_exp = 18          #   256K pieces
        elif size > 16*1024*1024:       # > 16M =
            piece_len_exp = 17          #   128K pieces
        elif size > 4*1024*1024:        # > 4M =
            piece_len_exp = 16          #   64K pieces
        else:                           # < 4M =
            piece_len_exp = 15          #   32K pieces
        return 2 ** piece_len_exp
    
    def add_file_info(self, size, path):
        """Add file information to torrent.
        
        Parameters
            long        size    size of file (in bytes)
            str[]       path    file path e.g. ['path','to','file.ext']
        """
        self.fs.append({'length': size,
                        'path': uniconvertl(path, self.encoding)})
    
    def add_data(self, data):
        """Process a segment of data.
        
        Note that the sequence of calls to this function is sensitive to
        order and concatenation. Treat it as a rolling hashing function, as
        it uses one.
        
        The length of data is relatively unimportant, though exact multiples
        of piece_length will slightly improve performance. The largest
        possible piece_length (2**21 bytes == 2MB) would be a reasonable
        default.
        
        Parameters
            str data    - an arbitrarily long segment of the file to
                        be hashed
        """
        toHash = len(data)
        self.totalhashed += toHash

        remainder = self.piece_length - self.done

        while toHash > 0:
            if toHash < remainder:
                # If we cannot complete a piece, update hash and leave
                self.sh.update(data)
                self.done += toHash
                break
            else:
                # Complete a block
                self.sh.update(data[:remainder])
                self.pieces.append(self.sh.digest())

                # Reset hash
                self.done = 0
                self.sh = sha.sha()

                # Discard hashed data
                data = data[remainder:]
                toHash = len(data)

                # Because self.done is always zero, here
                remainder = self.piece_length
    
    def write(self, target, tracker, **params):
        """Write a .torrent file

        Parameters
            str     target             - target file name (full path)
            str     tracker            - URL of tracker
        
        Optional parameters
            str     comment            - comment to include in file
            str     announce_list      - unparsed announce list
            str[][] real_announce_list - hierarchical announce list
            str     httpseeds          - unparsed http seed list
            str[]   real_httpseeds     - list of http seeds
        """
        
        # Whatever hash we have left, we'll add on to the end
        excess = []
        if self.done > 0:
            excess.append(self.sh.digest())
        
        info = {'pieces': ''.join(self.pieces + excess),
                'piece length': self.piece_length,
                'name': self.name}
        
        # If there is only one file and it has the same name path as the
        # torrent name, then encode directly, not as a files dictionary
        if len(self.fs) == 1 and self.name == self.fs[0]['path'][0]:
            info['length'] = self.size
        else:
            info['files'] = self.fs

        check_info(info)
        
        #data = {'info': info, 'announce': tracker, 'creation date': long(time())}
        data = {'info': info, 'announce': tracker, 'creation date': long(0)}

        # Optional data dictionary contents
        if params.has_key('comment') and params['comment']:
            data['comment'] = params['comment']
            
        if params.has_key('real_announce_list'):
            data['announce-list'] = params['real_announce_list']
        elif params.has_key('announce_list') and params['announce_list']:
            l = []
            for tier in params['announce_list'].split('|'):
                l.append(tier.split(','))
            data['announce-list'] = l
            
        if params.has_key('real_httpseeds'):
            data['httpseeds'] = params['real_httpseeds']
        elif params.has_key('httpseeds') and params['httpseeds']:
            data['httpseeds'] = params['httpseeds'].split('|')
        
        # Write file
        h = open(target, 'wb')
        h.write(bencode(data))
        h.close()

class BTTree:
    """BTTree - Recursive data structure that tracks the total size of a
    file or directory, which can then be used to create torrent files.
    
    BTTree attributes
        str      loc    Location of source file/directory
        str[]    path   Path
        BTTree[] subs   List of direct children (empty, if a file)
        int      size   Total size of subfiles (or self, if a file)
    """
    def __init__(self, loc, path):
        """
        Parameters
            str         loc     Location of source file/directory
            str[]       path    File path e.g. ['path','to','file.ext']
        """
        self.loc = os.path.abspath(loc)
        self.path = path
        self.subs = []
        
        # The only important bit of information at this stage is size
        if os.path.isfile(loc):
            self.size = os.path.getsize(loc)
        
        # We'll need to know the size of all subfiles
        elif os.path.isdir(loc):
            for sub in sorted(os.listdir(self.loc)):
                # Ignore .* (glob, not regex)
                if sub[0] == '.':
                    continue
                sloc = os.path.join(loc,sub)
                spath = self.path + [sub]
                try:
                    self.subs.append(BTTree(sloc,spath))
                
                # Notify, but ignore entries that are neither
                # files nor directories
                except problem:
                    print problem
            
            # For bittorrent's purposes, size(dir) = size(subs)
            self.size = sum([sub.size for sub in self.subs])
        else:
            raise Exception("Entry is neither file nor directory: %s"
                            % loc)

    def makeInfo(self, **params):
        """Generate an Info data structure from a BTTree
        
        Parameters
            str         tracker - URL of tracker
            str         target  - target directory
        """
        if self.path == []:
            name = os.path.split(self.loc)[-1]
        else:
            name = self.path[0]
        info = Info(    name,
                        self.size,
                        **params)

        self.updateInfo(info)

        return info

    def updateInfo(self, info):
        """Add a sub-BTTree to an Info structure

        Parameters
            Info	info   - Info structure to update
        """
        if self.subs == []:
            h = open(self.loc,'rb')
            pos = 0L
            info.add_file_info(self.size, self.path)
            
            while pos < self.size:
                a = min(info.piece_length, self.size - pos)
                buf = h.read(a)
                pos += a
                info.add_data(buf)
            
            h.close()
        
        else:
            for sub in self.subs:
                sub.updateInfo(info)
    
    def makeDirInfos(self, **params):
        return [sub.makeInfo(**params) for sub in self.subs]

    def buildMetaTree(self, tracker, target, infos = [], **params):
        """Construct a directory structure such that, for every path in
        the source structure defined by the object, there is a .torrent
        file describing it.
        
        This is an inlining of makeInfo and updateInfo so that, when a
        subtree is complete, its .torrent file is written, preserving
        memory.
        
        Parameters
            str         tracker - URL of tracker
            str         target  - target directory
            Info[]	infos   - List of Info's to add current file to
        """
        info = Info(    self.path[0],
                        self.size,
                        params.get('piece_size_pow2'))
        
        # Since append updates the object, while + creates a new one
        infos += [info]
        
        # Add the file pointed to by this BTTree to all infos
        if self.subs == []:
            h = open(self.loc,'rb')
            pos = 0L
            for i in infos:
                piece_length = max(piece_length, i.piece_length)
                i.add_file_info(self.size, self.path)
            
            while pos < self.size:
                a = min(piece_length, self.size - pos)
                buf = h.read(a)
                pos += a
                [i.add_data(buf) for i in infos]
            
            h.close()
        
        # Recurse in this directory
        else:
            for sub in self.subs:
                sub.buildMetaTree(tracker, target, infos)
        
        # Verify we can make our target .torrent file
        target_dir = os.path.split(info.target)[0]
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        
        info.write(os.path.join(target, *self.path) + '.torrent', tracker)
