"""Generate metafile data for use in BitTorrent applications

These data structures are generalizations of the original BitTorrent and
BitTornado makemetafile.py behaviors.
"""

import sys
import os
import re
import time
import hashlib
from .bencode import bencode, bdecode


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


class Info(dict):   # pylint: disable=R0904
    """Info - information associated with a .torrent file

    Info attributes
        str         name        - name of file/dir being hashed
        long        size        - total size of files to be described
        dict[]      fs          - metadata about files described
        long        totalhashed - portion of total data hashed
        PieceHasher hasher      - object to manage hashed files
    """
    validKeys = set(('name', 'piece length', 'pieces', 'files', 'length'))

    def __init__(self, name, size=None,
                 progress=lambda x: None, progress_percent=False, **params):
        """
        Parameters
            str  source           - source file name (last path element)
            int  size             - total size of files to be described
            f()  progress         - callback function to report progress
            bool progress_percent - flag for reporting percentage or change
        """
        super(Info, self).__init__()

        encoding = params.get('encoding', sys.getfilesystemencoding())
        if encoding == 'UTF-8':
            self.encode = lambda x: x.encode('utf-8')
            self.decode = lambda x: x.decode('utf-8')
        else:
            self.encode = lambda x: unicode(x, encoding).encode('utf-8')
            self.decode = lambda x: x.decode(encoding)

        # Use encoding to set name
        self.name = name

        if 'files' in params:
            self._files = params['files']
            self.size = sum(entry['length'] for entry in self._files)
        elif 'length' in params:
            self.size = params['length']
            self._files = [{'path': self.name, 'length': self.size}]
        else:
            self._files = []
            self.size = size

        if 'pieces' in params:
            pieces = params['pieces']
            # 'piece length' can't be made a variable
            self.hasher = PieceHasher(params['piece length'])
            self.hasher.pieces = [pieces[i:i + 20]
                                  for i in xrange(0, len(pieces), 20)]
            self.totalhashed = self.size
        elif size:
            # BitTorrent/BitTornado have traditionally allowed this parameter
            piece_len_exp = params.get('piece_size_pow2')
            if piece_len_exp is not None and piece_len_exp != 0:
                piece_length = 2 ** piece_len_exp
            else:
                piece_length = get_piece_len(size)

            self.totalhashed = 0L
            self.hasher = PieceHasher(piece_length)

        # Progress for this function updates the total amount hashed
        # Call the given progress function according to whether it accpts
        # percent or update
        if progress_percent:
            assert self.size

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

    def __contains__(self, key):
        """Test whether a key is in the Info dict"""
        if key == 'files':
            return len(self._files) != 1
        elif key == 'length':
            return len(self._files) == 1
        else:
            return key in self.validKeys

    def __getitem__(self, key):
        """Retrieve value associated with key in Info dict"""
        if key not in self.validKeys:
            raise KeyError('Invalid Info key')
        if key == 'piece length':
            return self.hasher.pieceLength
        elif key == 'pieces':
            return str(self.hasher)
        elif key == 'files':
            if 'files' in self:
                return self._files
            raise KeyError('files')
        elif key == 'length':
            if 'length' in self:
                return self.size
            raise KeyError('length')
        else:
            return super(Info, self).__getitem__(key)

    def iterkeys(self):
        """Return iterator over keys in Info dict"""
        keys = self.validKeys.copy()
        if 'files' in self:
            keys.remove('length')
        else:
            keys.remove('files')
        return iter(keys)

    def itervalues(self):
        """Return iterator over values in Info dict"""
        return (self[key] for key in self.keys())

    def iteritems(self):
        """Return iterator over items in Info dict"""
        return ((key, self[key]) for key in self.keys())

    def keys(self):
        """Return list of keys in Info dict"""
        return list(self.iterkeys())

    def values(self):
        """Return list of values in Info dict"""
        return list(self.itervalues())

    def items(self):
        """Return list of (key, value) pairs in Info dict"""
        return list(self.iteritems())

    def get(self, key, default=None):
        """Return value associated with key in Info dict, or default, if
        unavailable"""
        try:
            return self[key]
        except KeyError:
            return default

    @property
    def name(self):         # pylint: disable=E0202
        """Manage encoded Info name string"""
        return self.decode(self['name'])

    @name.setter            # pylint: disable=E1101
    def name(self, name):   # pylint: disable=E0102,E0202
        """Manage encoded Info name string"""
        try:
            self['name'] = self.encode(name)
        except UnicodeError:
            raise UnicodeError('bad filename: ' + name)

    def add_file_info(self, size, path):
        """Add file information to torrent.

        Parameters
            long        size    size of file (in bytes)
            str[]       path    file path e.g. ['path','to','file.ext']
        """
        self._files.append({'length': size,
                            'path': self._uniconvert(path)})

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

    def resume(self, location):
        """Rehash last piece to prepare PieceHasher to accept more data

        Parameters
            str location    - base path for hashed files"""
        excessLength = self.size % self.hasher.pieceLength
        if self.hasher.done != 0 or excessLength == 0:
            return

        # Construct list of files needed to provide the leftover data
        rehash = []
        for entry in self._files[::-1]:
            rehash.insert(0, entry)
            excessLength -= entry['length']
            if excessLength < 0:
                seek = -excessLength
                break

        # Final piece digest to compare new hash digest against
        validator = self.hasher.pieces.pop()

        for entry in rehash:
            path = os.path.join(location, *entry['path'])
            with open(path, 'rb') as tohash:
                tohash.seek(seek)
                self.hasher.update(tohash.read())
                seek = 0

        if self.hasher.digest != validator:
            self.hasher.resetHash()
            self.hasher.pieces.append(validator)
            raise ValueError("Location does not produce same hash")

    def _uniconvert(self, srclist):
        """Convert a list of strings to utf-8

        Parameters
            str[]   - Strings to be converted

        Return
            str[]   - Converted strings
        """
        try:
            return [self.encode(src) for src in srclist]
        except UnicodeError:
            raise UnicodeError('bad filename: ' + os.path.join(*srclist))


class MetaInfo(dict):
    """A constrained metainfo dictionary"""
    validKeys = set(('info', 'announce', 'creation date', 'comment',
                     'announce-list', 'httpseeds'))

    def __init__(self, **params):
        self.skip_check = params.pop('skip_check', False)

        real_announce_list = params.pop('real_announce_list', None)
        announce_list = params.pop('announce_list', None)
        real_httpseeds = params.pop('real_httpseeds', None)
        httpseeds = params.pop('httpseeds', None)

        # Since httpseeds may be passed as a parameter or a list, check this
        # possibility
        if isinstance(httpseeds, list):
            real_httpseeds = httpseeds

        if real_announce_list:
            self['announce-list'] = real_announce_list
        elif announce_list:
            self['announce-list'] = [tier.split(',')
                                     for tier in announce_list.split('|')]
        if real_httpseeds:
            self['httpseeds'] = real_httpseeds
        elif httpseeds:
            self['httpseeds'] = httpseeds.split('|')

        self.info = params.pop('info', None)

        if 'creation date' not in params:
            self['creation date'] = long(time.time())
        super(MetaInfo, self).__init__((k, v) for k, v in params.iteritems()
                                       if k in self.validKeys and v != '')

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
    def read(cls, torrent, skip_check=False):
        """Read MetaInfo from a torrent file"""
        with open(torrent, 'rb') as torrentfile:
            return cls(skip_check=skip_check, **bdecode(torrentfile.read()))

    @property
    def info(self):             # pylint: disable=E0202
        """Access and set Info struct through attribute"""
        return self['info']

    @info.setter                # pylint: disable=E1101
    def info(self, newinfo):    # pylint: disable=E0102,E0202
        """Access and set Info struct through attribute"""
        # Allow no Info
        if newinfo is None:
            self.pop('info', None)
            return

        if not self.skip_check:
            check_info(newinfo)
        if not isinstance(newinfo, Info):
            newinfo = Info(**newinfo)
        self['info'] = newinfo
