"""Generate metafile data for use in BitTorrent applications

These data structures are generalizations of the original BitTorrent and
BitTornado makemetafile.py behaviors.
"""

import os
import sha
import threading
from bencode import bencode
import re

try:
    from sys import getfilesystemencoding
    ENCODING = getfilesystemencoding()
except:
    from sys import getdefaultencoding
    ENCODING = getdefaultencoding()
    if not ENCODING:
        ENCODING = 'ascii'

REG = re.compile(r'^[^/\\.~][^/\\]*$')


# Generic utility functions
def uniconvertl(srclist, encoding):
    """Convert a list of strings to Unicode

    Parameters
        str[]   - Strings to be converted
        str     - Current string encoding

    Return
        str[]   - Converted strings
    """
    try:
        return [uniconvert(src, encoding) for src in srclist]
    except UnicodeError:
        raise UnicodeError('bad filename: ' + os.path.join(*srclist))


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


def check_type(obj, types, errmsg='', pred=lambda x: False):
    """Raise value error if obj does not match type or triggers predicate"""
    if not isinstance(obj, types) or pred(obj):
        raise ValueError(errmsg)


def check_info(info):
    """Validate torrent metainfo dictionary"""
    berr = 'bad metainfo - '
    check_type(info, dict, berr + 'not a dictionary')

    check_type(info.get('pieces'), str, berr + 'bad pieces key',
               lambda x: len(x) % 20 != 0)

    check_type(info.get('piece length'), (int, long),
               berr + 'illegal piece length', lambda x: x <= 0)

    name = info.get('name')
    check_type(name, str, berr + 'bad name')
    if not REG.match(name):
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
                if not REG.match(directory):
                    raise ValueError('path {} disallowed for security reasons'
                                     ''.format(directory))

            tpath = tuple(path)
            if tpath in paths:
                raise ValueError('bad metainfo - duplicate path')
            paths[tpath] = True


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

    def __init__(self, source, size, flag=threading.Event(),
                 progress=lambda x: None, progress_percent=True, **params):
        """
        Parameters
            str  source           - source file name (last path element)
            int  size             - total size of files to be described
            f()  progress         - callback function to report progress
            bool progress_percent - flag for reporting percentage or change
        """
        self.encoding = params.get('encoding', ENCODING)

        self.name = uniconvert(source, self.encoding)
        self.size = size

        self.flag = flag
        self.progress = progress
        self.progress_percent = progress_percent

        # BitTorrent/BitTornado have traditionally allowed this parameter
        piece_len_exp = params.get('piece_size_pow2')
        if piece_len_exp is not None and piece_len_exp != 0:
            self.piece_length = 2 ** piece_len_exp
        else:
            self.piece_length = self.get_piece_len(size)

        # Universal
        self.pieces = []
        self.sha = sha.sha()
        self.done = 0L
        self.files = []
        self.totalhashed = 0L

    def get_piece_len(self, size):
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

    def add_file_info(self, size, path):
        """Add file information to torrent.

        Parameters
            long        size    size of file (in bytes)
            str[]       path    file path e.g. ['path','to','file.ext']
        """
        self.files.append({'length': size,
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
        remainder = self.piece_length - self.done

        while toHash > 0:
            if toHash < remainder:
                # If we cannot complete a piece, update hash and leave
                self.sha.update(data)
                self.done += toHash
                self.totalhashed += toHash

                # Update progress
                if self.progress_percent:
                    self.progress(self.totalhashed / self.size)
                else:
                    self.progress(toHash)

                break
            else:
                # Complete a block
                self.sha.update(data[:remainder])
                self.pieces.append(self.sha.digest())

                if self.flag is not None and self.flag.isSet():
                    break

                # Update progress
                self.totalhashed += remainder
                if self.progress_percent:
                    self.progress(self.totalhashed / self.size)
                else:
                    self.progress(remainder)

                # Reset hash
                self.done = 0
                self.sha = sha.sha()

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
            excess.append(self.sha.digest())

        info = {'pieces': ''.join(self.pieces + excess),
                'piece length': self.piece_length,
                'name': self.name}

        # If there is only one file and it has the same name path as the
        # torrent name, then encode directly, not as a files dictionary
        if len(self.files) == 1 and self.files[0]['path'] == []:
            info['length'] = self.size
        else:
            info['files'] = self.files

        check_info(info)

        data = {'info': info, 'announce': tracker, 'creation date': long(0)}

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
        with open(target, 'wb') as h:
            h.write(bencode(data))
