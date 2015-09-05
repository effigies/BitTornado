"""Encode/decode data structures for use in BitTorrent applications
"""
#pylint: disable=R0903

import warnings
import mmap

BENCACHED_MARKER = []


class Bencached(object):
    """Store the ciphertext of repeatedly encoded data structures"""
    def __init__(self, ctext):
        self.marker = BENCACHED_MARKER
        self.bencoded = ctext

    @classmethod
    def cache(cls, data):
        """Construct Bencached value from a plain data structure"""
        return cls(bencode(data))


class BTEncoder(object):
    """Encode a data structure into a string for use in BitTorrent applications
    """

    def __call__(self, data):
        """Encode a data structure into a string.

        Creates a list in which to collect string segments and returns the
        joined result.

        See encode_* for details.
        """
        ctext = []
        self.encode(data, ctext)
        return b''.join(ctext)

    def encode(self, data, ctext):
        """Determine type of data and encode into appropriate string"""
        if isinstance(data, (list, tuple)):
            # A list takes the form lXe where X is the concatenation of the
            # encodings of all elements in the list.
            ctext.append(b'l')
            for element in data:
                self.encode(element, ctext)
            ctext.append(b'e')
        elif isinstance(data, dict):
            # A dictionary is encoded as dXe where X is the concatenation of
            # the encodings of all key,value pairs in the dictionary, sorted by
            # key. Key, value pairs are themselves concatenations of the
            # encodings of keys and values, where keys are assumed to be
            # strings.
            ctext.append(b'd')
            ilist = data.items()
            for key, data in sorted(ilist):
                if not isinstance(key, (str, bytes)):
                    raise TypeError("Dictionary keys must be (byte)strings")
                self.encode(key, ctext)
                self.encode(data, ctext)
            ctext.append(b'e')
        elif isinstance(data, (str, bytes)):
            # A string is encoded as nbytes:contents
            if isinstance(data, str):
                data = data.encode('utf-8')
            ctext.extend((str(len(data)).encode('utf-8'), b':', data))
        elif isinstance(data, int):
            ctext.append('i{:d}e'.format(data).encode('utf-8'))
        elif isinstance(data, Bencached):
            assert data.marker == BENCACHED_MARKER
            ctext.append(data.bencoded)
        else:
            raise TypeError('Unknown type for bencode: ' + str(type(data)))


#pylint: disable=R0201
class BTDecoder(object):
    """Stateless object that decodes bencoded strings into data structures"""
    def __call__(self, ctext, sloppy=False, stacklevel=1):
        """Decode a string encoded with bencode, such as the contents of a
        .torrent file"""
        try:
            data, length = self.decode_func[ctext[0]](self, ctext, 0)
        except (IndexError, KeyError, ValueError):
            raise ValueError("bad bencoded data")
        if not sloppy and length != len(ctext):
            warnings.warn("bad bencoded data", stacklevel=stacklevel + 1)
        return data

    def decode_int(self, ctext, pos):
        """Decode integer in ciphertext at a given position

        An integer with ASCII representation X will be encoded as "iXe". A
        ValueError will be thrown if X begins with 0 but is not simply '0',
        or if X begins with '-0'.

        Returns (parsed integer, next token start position)
        """
        pos += 1
        newpos = ctext.find(b'e', pos)

        # '-0' is invalid and strings beginning with '0' must be == '0'
        if any((newpos < 0, ctext[pos:pos + 2] == b'-0',
                ctext[pos] == ord('0') and newpos != pos + 1)):
            raise ValueError

        return (int(ctext[pos:newpos]), newpos + 1)

    def decode_string(self, ctext, pos):
        """Decode string in ciphertext at a given position

        A string is encoded as an integer length, followed by a colon and a
        string of the length given. A ValueError is thrown if length begins
        with '0' but is not '0'.

        Returns (parsed string, next token start position)
        """
        colon = ctext.find(b':', pos)
        length = int(ctext[pos:colon])

        # '0:' is the only valid string beginning with '0'
        if any((colon == -1, ctext[pos] == ord('0') and colon != pos + 1,
                len(ctext) <= colon + length)):
            raise ValueError

        colon += 1
        data, pos = (ctext[colon:colon + length], colon + length)
        try:
            return (data.decode('utf-8'), pos)
        except UnicodeDecodeError:
            return (data, pos)

    def decode_list(self, ctext, pos):
        """Decode list in ciphertext at a given position

        A list takes the form lXe where X is the concatenation of the
        encodings of all elements in the list.

        Returns (parsed list, next token start position)
        """
        data, pos = [], pos + 1
        while ctext[pos] != ord('e'):
            element, pos = self.decode_func[ctext[pos]](self, ctext, pos)
            data.append(element)
        return (data, pos + 1)

    def decode_dict(self, ctext, pos):
        """Decode dictionary in ciphertext at a given position

        A dictionary is encoded as dXe where X is the concatenation of the
        encodings of all key,value pairs in the dictionary, sorted by key.
        Key, value paris are themselves concatenations of the encodings of
        keys and values, where keys are assumed to be strings.

        Returns (parsed dictionary, next token start position)
        """
        data, pos = {}, pos + 1
        lastkey = b''
        while ctext[pos] != ord('e'):
            key, pos = self.decode_string(ctext, pos)
            rawkey = key if isinstance(key, bytes) else key.encode()
            if lastkey >= rawkey:
                raise ValueError
            lastkey = rawkey
            data[key], pos = self.decode_func[ctext[pos]](self, ctext, pos)
        return (data, pos + 1)

    decode_func = {
        ord('l'):   decode_list,
        ord('d'):   decode_dict,
        ord('i'):   decode_int,
        ord('0'):   decode_string,
        ord('1'):   decode_string,
        ord('2'):   decode_string,
        ord('3'):   decode_string,
        ord('4'):   decode_string,
        ord('5'):   decode_string,
        ord('6'):   decode_string,
        ord('7'):   decode_string,
        ord('8'):   decode_string,
        ord('9'):   decode_string,
    }


class BencodedFile(object):
    """Enable reading of bencoded files into bencodable objects, and writing
    bencodable objects into bencoded files.

    A bencodable object is one in which all values are lists, dictionaries,
    (byte)strings or integers, or subclasses of these, and all dictionary keys
    are (byte)strings or subclasses."""
    def write(self, fname):
        with open(fname, 'wb') as handle:
            handle.write(bencode(self))

    @classmethod
    def read(klass, fname, *args, **kwargs):
        sloppy = kwargs.pop('sloppy', False)
        with open(fname, 'rb') as handle:
            # Using memory maps allows Python to handle some standard errors
            mm = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
            return klass(bdecode(mm, sloppy=sloppy, stacklevel=2), *args,
                         **kwargs)

#pylint: disable=C0103
bencode = BTEncoder().__call__
bdecode = BTDecoder().__call__
