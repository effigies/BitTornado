"""Generate metafile data for use in BitTorrent applications

These data structures are generalizations of the original BitTorrent and
BitTornado makemetafile.py behaviors.
"""

import sys
import os
import re
import time
import hashlib
from bencode import bencode, bdecode


def get_piece_len(size):
    """Parameters
        long    size    - size of files described by torrent

    Return
        long            - size of pieces to hash
    """
    if size > 8 * (2 ** 30):        # >  8G file
        piece_len_exp = 21          # =  2M pieces
    elif size > 2 * (2 ** 30):      # >  2G file
        piece_len_exp = 20          # =  1M pieces
    elif size > 512 * (2 ** 20):    # >512M file
        piece_len_exp = 19          # =512K pieces
    elif size > 64 * (2 ** 20):     # > 64M file
        piece_len_exp = 18          # =256K pieces
    elif size > 16 * (2 ** 20):     # > 16M file
        piece_len_exp = 17          # =128K pieces
    elif size > 4 * (2 ** 20):      # >  4M file
        piece_len_exp = 16          # = 64K pieces
    else:                           # <  4M file
        piece_len_exp = 15          # = 32K pieces
    return 2 ** piece_len_exp


def check_type(obj, types, errmsg='', pred=lambda x: False):
    """Raise value error if obj does not match type or triggers predicate"""
    if not isinstance(obj, types) or pred(obj):
        raise ValueError(errmsg)


def check_info(info):
    """Validate torrent metainfo dictionary"""

    valid_name = re.compile(r'^[^/\\.~][^/\\]*$')
    berr = 'bad metainfo - '
    check_type(info, dict, berr + 'not a dictionary')

    check_type(info.get('pieces'), str, berr + 'bad pieces key',
               lambda x: len(x) % 20 != 0)

    check_type(info.get('piece length'), (int, long),
               berr + 'illegal piece length', lambda x: x <= 0)

    name = info.get('name')
    check_type(name, str, berr + 'bad name')
    if not valid_name.match(name):
        raise ValueError('name %s disallowed for security reasons' % name)

    if ('files' in info) == ('length' in info):
        raise ValueError('single/multiple file mix')

    if 'length' in info:
        check_type(info['length'], (int, long), berr + 'bad length',
                   lambda x: x < 0)
    else:
        files = info.get('files')
        check_type(files, list)

        paths = {}
        for finfo in files:
            check_type(finfo, dict, berr + 'bad file value')

            check_type(finfo.get('length'), (int, long), berr + 'bad length',
                       lambda x: x < 0)

            path = finfo.get('path')
            check_type(path, list, berr + 'bad path', lambda x: x == [])

            for directory in path:
                check_type(directory, str, berr + 'bad path dir')
                if not valid_name.match(directory):
                    raise ValueError('path {} disallowed for security reasons'
                                     ''.format(directory))

            tpath = tuple(path)
            if tpath in paths:
                raise ValueError('bad metainfo - duplicate path')
            paths[tpath] = True


class PieceHasher(object):
    """Wrapper for SHA1 hash with a maximum length"""
    def __init__(self, pieceLength, hashtype=hashlib.sha1):
        self.pieceLength = pieceLength
        self._hashtype = hashtype
        self._hash = hashtype()
        self.done = 0L
        self.pieces = []

    def resetHash(self):
        """Set hash to initial state"""
        self._hash = self._hashtype()
        self.done = 0L

    def update(self, data, progress=lambda x: None):
        """Add data to PieceHasher, splitting pieces if necessary.

        Progress function that accepts a number of (new) bytes hashed
        is optional
        """
        tofinish = self.pieceLength - self.done    # bytes to finish a piece

        # Split data based on the number of bytes to finish the current piece
        # If data is less than needed, remainder will be empty
        init, remainder = data[:tofinish], data[tofinish:]

        # Hash initial segment
        self._hash.update(init)
        progress(len(init))
        self.done += len(init)

        # Hash remainder, if present
        if remainder:
            toHash = len(remainder)

            # Create a new hash for each piece of data present
            hashes = [self._hashtype(remainder[i:i + self.pieceLength])
                      for i in xrange(0, toHash, self.pieceLength)]
            progress(toHash)

            self.done = toHash % self.pieceLength

            self.pieces.append(self._hash.digest())
            self._hash = hashes[-1]
            self.pieces.extend(piece.digest() for piece in hashes[:-1])

        # If the piece is finished, reinitialize
        if self.done == self.pieceLength:
            self.pieces.append(self._hash.digest())
            self.resetHash()

    def __nonzero__(self):
        """Evaluate to true if any data has been hashed"""
        return bool(self.pieces) or self.done != 0

    def __repr__(self):
        return "<PieceHasher[{:d}] ({})>".format(
            len(self.pieces), self._hash.hexdigest())

    def __str__(self):
        """Print concatenated digests of pieces and current digest, if
        nonzero"""
        excess = []
        if self.done > 0:
            excess.append(self._hash.digest())
        return ''.join(self.pieces + excess)

    @property
    def digest(self):
        """Current hash digest as a byte string"""
        return self._hash.digest()

    @property
    def hashtype(self):
        """Name of the hash function being used"""
        return self._hash.name


class Info(object):
    """Info - information associated with a .torrent file

    Info attributes
        str         name        - name of file/dir being hashed
        long        size        - total size of files to be described
        dict[]      fs          - metadata about files described
        long        totalhashed - portion of total data hashed
        PieceHasher hasher      - object to manage hashed files
    """

    def __init__(self, source, size, progress=lambda x: None,
                 progress_percent=True, **params):
        """
        Parameters
            str  source           - source file name (last path element)
            int  size             - total size of files to be described
            f()  progress         - callback function to report progress
            bool progress_percent - flag for reporting percentage or change
        """
        self.encoding = params.get('encoding', sys.getfilesystemencoding())

        self.name = self.uniconvert((source,))[0]
        self.size = size

        # BitTorrent/BitTornado have traditionally allowed this parameter
        piece_len_exp = params.get('piece_size_pow2')
        if piece_len_exp is not None and piece_len_exp != 0:
            pieceLength = 2 ** piece_len_exp
        else:
            pieceLength = get_piece_len(size)

        # Universal
        self.files = []
        self.totalhashed = 0L
        self.hasher = PieceHasher(pieceLength)

        # Progress for this function updates the total amount hashed
        # Call the given progress function according to whether it accpts
        # percent or update
        if progress_percent:
            def totalprogress(update, self=self, base=progress):
                """Update totalhashed and use percentage progress callback"""
                self.totalhashed += update
                base(self.totalhashed / self.size)
            self.progress = totalprogress
        else:
            def updateprogress(update, self=self, base=progress):
                """Update totalhashed and use update progress callback"""
                self.totalhashed += update
                base(update)
            self.progress = updateprogress

    def add_file_info(self, size, path):
        """Add file information to torrent.

        Parameters
            long        size    size of file (in bytes)
            str[]       path    file path e.g. ['path','to','file.ext']
        """
        self.files.append({'length': size,
                           'path': self.uniconvert(path)})

    def add_data(self, data):
        """Process a segment of data.

        Note that the sequence of calls to this function is sensitive to
        order and concatenation. Treat it as a rolling hashing function, as
        it uses one.

        The length of data is relatively unimportant, though exact
        multiples of the hasher's pieceLength will slightly improve
        performance. The largest possible pieceLength (2**21 bytes == 2MB)
        would be a reasonable default.

        Parameters
            str data    - an arbitrarily long segment of the file to
                        be hashed
        """
        self.hasher.update(data, self.progress)

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

        info = {'pieces': str(self.hasher),
                'piece length': self.hasher.pieceLength,
                'name': self.name}

        # If there is only one file and it has the same name path as the
        # torrent name, then encode directly, not as a files dictionary
        if len(self.files) == 1 and self.files[0]['path'] == []:
            info['length'] = self.size
        else:
            info['files'] = self.files

        check_info(info)

        data = {'info': info, 'announce': tracker,
                'creation date': long(time.time())}

        # Optional data dictionary contents
        if 'comment' in params and params['comment']:
            data['comment'] = params['comment']

        if 'real_announce_list' in params:
            data['announce-list'] = params['real_announce_list']
        elif 'announce_list' in params and params['announce_list']:
            data['announce-list'] = [
                tier.split(',') for tier in params['announce_list'].split('|')]

        if 'real_httpseeds' in params:
            data['httpseeds'] = params['real_httpseeds']
        elif 'httpseeds' in params and params['httpseeds']:
            data['httpseeds'] = params['httpseeds'].split('|')

        # Write file
        with open(target, 'wb') as fhandle:
            fhandle.write(bencode(data))

    def uniconvert(self, srclist):
        """Convert a list of strings to utf-8

        Parameters
            str[]   - Strings to be converted

        Return
            str[]   - Converted strings
        """
        try:
            return [unicode(src, self.encoding).encode('utf-8')
                    for src in srclist]
        except UnicodeError:
            raise UnicodeError('bad filename: ' + os.path.join(*srclist))


class MetaInfo(dict):
    """A constrained metainfo dictionary"""
    validKeys = set(('info', 'announce', 'creation date', 'comment',
                     'announce-list', 'httpseeds'))

    def __init__(self, **params):
        real_announce_list = params.pop('real_announce_list', None)
        announce_list = params.pop('announce_list', None)
        real_httpseeds = params.pop('real_httpseeds', None)
        httpseeds = params.pop('httpseeds', None)

        if real_announce_list:
            self['announce-list'] = real_announce_list
        elif announce_list:
            self['announce-list'] = [tier.split(',')
                                     for tier in announce_list.split('|')]
        if real_httpseeds:
            self['httpseeds'] = real_httpseeds
        elif httpseeds:
            self['httpseeds'] = httpseeds.split('|')

        super(MetaInfo, self).__init__((k, params[k]) for k in params
                                       if k in self.validKeys)

    def __setitem__(self, key, value):
        """Set value associated with key if key is in MetaInfo.validKeys"""
        if key not in self.validKeys:
            raise KeyError('Invalid MetaInfo key')
        super(MetaInfo, self).__setitem__(key, value)

    def update(self, itr=None, **params):
        """Update MetaInfo from an iterable/dict and/or from named parameters

        Named parameters take precedence, but all arguments are filtered
        against MetaInfo.validKeys
        """
        if itr is not None:
            if hasattr(itr, 'keys'):
                src = ((key, itr[key]) for key in itr if key in self.validKeys)
            else:
                src = ((key, val) for key, val in itr if key in self.validKeys)
            super(MetaInfo, self).update(src)

        super(MetaInfo, self).update((key, params[key]) for key in params
                                     if key in self.validKeys)

    def setdefault(self, key, default=None):
        """Return value associated with key. If not present, try to set to
        default, or None, if not given."""
        if key not in self:
            self[key] = default
        return self[key]

    def write(self, torrent):
        """Write MetaInfo to a torrent file"""
        with open(torrent, 'wb') as torrentfile:
            torrentfile.write(bencode(self))

    @classmethod
    def read(cls, torrent):
        """Read MetaInfo from a torrent file"""
        with open(torrent, 'rb') as torrentfile:
            return cls(**bdecode(torrentfile.read()))
