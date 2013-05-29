"""Encode/decode data structures for use in BitTorrent applications
"""
#pylint: disable=R0903

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
    def __call__(self, ctext, sloppy=0):
        """Decode a string encoded with bencode, such as the contents of a
        .torrent file"""
        try:
            data, length = self.decode_func[ctext[0]](self, ctext, 0)
        except (IndexError, KeyError, ValueError) as e:
            raise ValueError("bad bencoded data")
        if not sloppy and length != len(ctext):
            raise ValueError("bad bencoded data")
        return data

    def decode_int(self, ctext, pos):
        """Decode integer in ciphertext at a given position

        An integer with ASCII representation X will be encoded as "iXe". A
        ValueError will be thrown if X begins with 0 but is not simply '0',
        or if X begins with '-0'.

        Returns (parsed integer, next token start position)
        """
        pos += 1
        newpos = ctext.index(ord('e'), pos)
        data = int(ctext[pos:newpos])

        # '-0' is invalid and strings beginning with '0' must be == '0'
        if ctext[pos:pos + 2] == b'-0' or \
                ctext[pos] == ord('0') and newpos != pos + 1:
            raise ValueError

        return (data, newpos + 1)

    def decode_string(self, ctext, pos):
        """Decode string in ciphertext at a given position

        A string is encoded as an integer length, followed by a colon and a
        string of the length given. A ValueError is thrown if length begins
        with '0' but is not '0'.

        Returns (parsed string, next token start position)
        """
        colon = ctext.index(ord(':'), pos)
        length = int(ctext[pos:colon])

        # '0:' is the only valid string beginning with '0'
        if ctext[pos] == ord('0') and colon != pos + 1:
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

#pylint: disable=C0103
bencode = BTEncoder().__call__
bdecode = BTDecoder().__call__


def _test_exception(exc, func, *data):
    """Validate that func(data) raises exc"""
    try:
        func(*data)
    except exc:
        return True
    except Exception:
        pass
    return False


def test_bencode():
    """Test encoding of encodable and unencodable data structures"""
    assert bencode(4) == b'i4e'
    assert bencode(0) == b'i0e'
    assert bencode(-10) == b'i-10e'
    assert bencode(12345678901234567890) == b'i12345678901234567890e'
    assert bencode('') == b'0:'
    assert bencode('abc') == b'3:abc'
    assert bencode('1234567890') == b'10:1234567890'
    assert bencode([]) == b'le'
    assert bencode([1, 2, 3]) == b'li1ei2ei3ee'
    assert bencode([['Alice', 'Bob'], [2, 3]]) == b'll5:Alice3:Bobeli2ei3eee'
    assert bencode({}) == b'de'
    assert bencode({'age': 25, 'eyes': 'blue'}) == b'd3:agei25e4:eyes4:bluee'
    assert bencode({'spam.mp3': {'author': 'Alice', 'length': 100000}}) == \
        b'd8:spam.mp3d6:author5:Alice6:lengthi100000eee'
    assert _test_exception(TypeError, bencode, {1: 'foo'})
    assert _test_exception(TypeError, bencode, {'foo': 1.0})

    cached = Bencached.cache({'age': 25})
    assert bencode(cached) == cached.bencoded

    assert bencode(u'') == bencode('')


def test_bdecode():
    """Test decoding of valid and erroneous sample strings"""
    assert _test_exception(ValueError, bdecode, b'0:0:')
    assert _test_exception(ValueError, bdecode, b'ie')
    assert _test_exception(ValueError, bdecode, b'i341foo382e')
    assert bdecode(b'i4e') == 4
    assert bdecode(b'i0e') == 0
    assert bdecode(b'i123456789e') == 123456789
    assert bdecode(b'i-10e') == -10
    assert _test_exception(ValueError, bdecode, b'i-0e')
    assert _test_exception(ValueError, bdecode, b'i123')
    assert _test_exception(ValueError, bdecode, b'')
    assert _test_exception(ValueError, bdecode, b'i6easd')
    assert _test_exception(ValueError, bdecode, b'35208734823ljdahflajhdf')
    assert _test_exception(ValueError, bdecode, b'2:abfdjslhfld')
    assert bdecode(b'0:') == ''
    assert bdecode(b'3:abc') == 'abc'
    assert bdecode(b'10:1234567890') == '1234567890'
    assert _test_exception(ValueError, bdecode, b'02:xy')
    assert _test_exception(ValueError, bdecode, b'l')
    assert bdecode(b'le') == []
    assert _test_exception(ValueError, bdecode, b'leanfdldjfh')
    assert bdecode(b'l0:0:0:e') == ['', '', '']
    assert _test_exception(ValueError, bdecode, b'relwjhrlewjh')
    assert bdecode(b'li1ei2ei3ee') == [1, 2, 3]
    assert bdecode(b'l3:asd2:xye') == ['asd', 'xy']
    assert bdecode(b'll5:Alice3:Bobeli2ei3eee') == [['Alice', 'Bob'], [2, 3]]
    assert _test_exception(ValueError, bdecode, b'd')
    assert _test_exception(ValueError, bdecode, b'defoobar')
    assert bdecode(b'de') == {}
    assert bdecode(b'd3:agei25e4:eyes4:bluee') == {'age': 25, 'eyes': 'blue'}
    assert bdecode(b'd8:spam.mp3d6:author5:Alice6:lengthi100000eee') == \
        {'spam.mp3': {'author': 'Alice', 'length': 100000}}
    assert _test_exception(ValueError, bdecode, b'd3:fooe')
    assert _test_exception(ValueError, bdecode, b'di1e0:e')
    assert _test_exception(ValueError, bdecode, b'd1:b0:1:a0:e')
    assert _test_exception(ValueError, bdecode, b'd1:a0:1:a0:e')
    assert _test_exception(ValueError, bdecode, b'i03e')
    assert _test_exception(ValueError, bdecode, b'l01:ae')
    assert _test_exception(ValueError, bdecode, b'9999:x')
    assert _test_exception(ValueError, bdecode, b'l0:')
    assert _test_exception(ValueError, bdecode, b'd0:0:')
    assert _test_exception(ValueError, bdecode, b'd0:')
