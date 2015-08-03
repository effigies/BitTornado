"""Generate metafile data for use in BitTorrent applications

These data structures are generalizations of the original BitTorrent and
BitTornado makemetafile.py behaviors.
"""

import os
import re
import time
import hashlib
from .TypedCollections import TypedDict, TypedList, SplitList
from .bencode import BencodedFile


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

VALID_NAME = re.compile(r'^[^/\\.~][^/\\]*$')


def check_info(info):
    """Validate torrent metainfo dictionary"""

    valid_name = re.compile(r'^[^/\\.~][^/\\]*$')
    berr = 'bad metainfo - '
    check_type(info, dict, berr + 'not a dictionary')

    check_type(info.get('pieces'), bytes, berr + 'bad pieces key',
               lambda x: len(x) % 20 != 0)

    check_type(info.get('piece length'), int, berr + 'illegal piece length',
               lambda x: x <= 0)

    name = info.get('name')
    check_type(name, str, berr + 'bad name')
    if not valid_name.match(name):
        raise ValueError('name %s disallowed for security reasons' % name)

    if ('files' in info) == ('length' in info):
        raise ValueError('single/multiple file mix')

    if 'length' in info:
        check_type(info['length'], int, berr + 'bad length',
                   lambda x: x < 0)
    else:
        files = info.get('files')
        check_type(files, list)

        paths = {}
        for finfo in files:
            check_type(finfo, dict, berr + 'bad file value')

            check_type(finfo.get('length'), int, berr + 'bad length',
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
        self.done = 0
        self.pieces = []

    def resetHash(self):
        """Set hash to initial state"""
        self._hash = self._hashtype()
        self.done = 0

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
                      for i in range(0, toHash, self.pieceLength)]
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

    def __bytes__(self):
        """Print concatenated digests of pieces and current digest, if
        nonzero"""
        excess = []
        if self.done > 0:
            excess.append(self._hash.digest())
        return b''.join(self.pieces + excess)

    @property
    def digest(self):
        """Current hash digest as a byte string"""
        return self._hash.digest()

    @property
    def hashtype(self):
        """Name of the hash function being used"""
        return self._hash.name


class Info(TypedDict):   # pylint: disable=R0904
    """Info - information associated with a .torrent file

    Info attributes
        str         name        - name of file/dir being hashed
        long        size        - total size of files to be described
        dict[]      fs          - metadata about files described
        long        totalhashed - portion of total data hashed
        PieceHasher hasher      - object to manage hashed files
    """
    class Files(TypedList):
        class File(TypedDict):
            class Path(TypedList):
                valtype = str
                valconst = lambda s, x: VALID_NAME.match(x)
            typemap = {'length': int, 'path': Path}
        valtype = File
    typemap = {'name': str, 'piece length': int, 'pieces': bytes,
               'files': Files, 'length': int}

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

        if not params and not isinstance(name, (str, bytes)):
            params = name
            # Accept iterables
            if not isinstance(params, dict):
                params = dict(params)
            name = params.pop('name', None)
            size = params.pop('size', None)
            progress = params.pop('progress', lambda x: None)
            progress_percent = params.pop('progress_percent', False)

        if isinstance(name, bytes):
            name = name.decode()

        self['name'] = name

        if 'files' in params:
            self['files'] = params['files']
            self['length'] = sum(entry['length']
                                 for entry in self._get('files'))
        elif 'length' in params:
            self['length'] = params['length']
            self['files'] = [{'path': [self['name']],
                              'length': self._get('length')}]
        else:
            self['files'] = []
            self['length'] = size

        if 'pieces' in params:
            pieces = params['pieces']
            # 'piece length' can't be made a variable
            self.hasher = PieceHasher(params['piece length'])
            self.hasher.pieces = [pieces[i:i + 20]
                                  for i in range(0, len(pieces), 20)]
            self.totalhashed = self._get('length')
        elif size:
            # BitTorrent/BitTornado have traditionally allowed this parameter
            piece_len_exp = params.get('piece_size_pow2')
            if piece_len_exp is not None and piece_len_exp != 0:
                piece_length = 2 ** piece_len_exp
            else:
                piece_length = get_piece_len(size)

            self.totalhashed = 0
            self.hasher = PieceHasher(piece_length)

        # Progress for this function updates the total amount hashed
        # Call the given progress function according to whether it accpts
        # percent or update
        if progress_percent:
            assert self._get('length')

            def totalprogress(update, self=self, base=progress):
                """Update totalhashed and use percentage progress callback"""
                self.totalhashed += update
                base(self.totalhashed / self._get('length'))
            self.progress = totalprogress
        else:
            def updateprogress(update, self=self, base=progress):
                """Update totalhashed and use update progress callback"""
                self.totalhashed += update
                base(update)
            self.progress = updateprogress

    def __contains__(self, key):
        """Test whether a key is in the Info dict"""
        files = self._get('files')
        if key == 'files':
            return len(files) != 1
        elif key == 'length':
            return len(files) == 1
        else:
            return key in self.valid_keys

    def __getitem__(self, key):
        """Retrieve value associated with key in Info dict"""
        if key not in self.valid_keys:
            raise KeyError('Invalid Info key')
        if key == 'piece length':
            return self.hasher.pieceLength
        elif key == 'pieces':
            return bytes(self.hasher)
        elif key == 'files':
            if 'files' not in self:
                raise KeyError('files')
        elif key == 'length':
            if 'length' not in self:
                raise KeyError('length')
        return super(Info, self).__getitem__(key)

    def keys(self):
        """Return iterator over keys in Info dict"""
        keys = self.valid_keys.copy()
        if 'files' in self:
            keys.remove('length')
        else:
            keys.remove('files')
        return iter(keys)

    def values(self):
        """Return iterator over values in Info dict"""
        return (self[key] for key in self.keys())

    def items(self):
        """Return iterator over items in Info dict"""
        return ((key, self[key]) for key in self.keys())

    def get(self, key, default=None):
        """Return value associated with key in Info dict, or default, if
        unavailable"""
        try:
            return self[key]
        except KeyError:
            return default

    def _get(self, *args, **kwargs):
        return super(Info, self).get(*args, **kwargs)

    def add_file_info(self, size, path):
        """Add file information to torrent.

        Parameters
            long        size    size of file (in bytes)
            str[]       path    file path e.g. ['path','to','file.ext']
        """
        self._get('files').append({'length': size, 'path': path})

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
        excessLength = self._get('length') % self.hasher.pieceLength
        if self.hasher.done != 0 or excessLength == 0:
            return

        seek = 0

        # Construct list of files needed to provide the leftover data
        rehash = []
        for entry in self._get('files')[::-1]:
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


class MetaInfo(TypedDict, BencodedFile):
    """A constrained metainfo dictionary"""
    class AnnounceList(SplitList):
        class AnnounceTier(SplitList):
            splitchar = ','
            valtype = str
        splitchar = '|'
        valtype = AnnounceTier

    class HTTPList(SplitList):
        splitchar = '|'
        valtype = str

    typemap = {'info': Info, 'announce': str, 'creation date': int,
               'comment': str, 'announce-list': AnnounceList,
               'httpseeds': HTTPList}

    def __init__(self, *args, **kwargs):
        super(MetaInfo, self).__init__(*args, **kwargs)

        if 'creation date' not in self:
            self['creation date'] = int(time.time())
