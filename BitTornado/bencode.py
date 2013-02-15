"""Encode/decode data structures for use in BitTorrent applications
"""

from types import IntType, LongType, StringType, ListType, TupleType, \
    DictType, BooleanType
try:
    from types import UnicodeType
except ImportError:
    UnicodeType = None


class BTDecoder(object):
    """Stateless object that decodes bencoded strings into data structures"""
    def __call__(self, ctext, sloppy=0):
        """Decode a string encoded with bencode, such as the contents of a
        .torrent file"""
        try:
            data, length = self.decode_func[ctext[0]](self, ctext, 0)
        except (IndexError, KeyError, ValueError):
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
        newpos = ctext.index('e', pos)
        data = int(ctext[pos:newpos])

        # '-0' is invalid and strings beginning with '0' must be == '0'
        if ctext[pos:pos + 2] == '-0' or \
                ctext[pos] == '0' and newpos != pos + 1:
            raise ValueError

        return (data, newpos + 1)

    def decode_string(self, ctext, pos):
        """Decode string in ciphertext at a given position

        A string is encoded as an integer length, followed by a colon and a
        string of the length given. A ValueError is thrown if length begins
        with '0' but is not '0'.

        Returns (parsed string, next token start position)
        """
        colon = ctext.index(':', pos)
        length = int(ctext[pos:colon])

        # '0:' is the only valid string beginning with '0'
        if ctext[pos] == '0' and colon != pos + 1:
            raise ValueError

        colon += 1
        return (ctext[colon:colon + length], colon + length)

    def decode_unicode(self, ctext, pos):
        """Decode unicode string in ciphertext at a given position

        A unicode string is simply a string encoding preceded by a u.
        """
        data, pos = self.decode_string(ctext, pos + 1)
        return (data.decode('UTF-8'), pos)

    def decode_list(self, ctext, pos):
        """Decode list in ciphertext at a given position

        A list takes the form lXe where X is the concatenation of the
        encodings of all elements in the list.

        Returns (parsed list, next token start position)
        """
        data, pos = [], pos + 1
        while ctext[pos] != 'e':
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
        lastkey = None
        while ctext[pos] != 'e':
            key, pos = self.decode_string(ctext, pos)
            if lastkey >= key:
                raise ValueError
            lastkey = key
            data[key], pos = self.decode_func[ctext[pos]](self, ctext, pos)
        return (data, pos + 1)

    decode_func = {
        'l':    decode_list,
        'd':    decode_dict,
        'i':    decode_int,
        '0':    decode_string,
        '1':    decode_string,
        '2':    decode_string,
        '3':    decode_string,
        '4':    decode_string,
        '5':    decode_string,
        '6':    decode_string,
        '7':    decode_string,
        '8':    decode_string,
        '9':    decode_string,
        'u':    decode_unicode
    }

bdecode = BTDecoder().__call__


def _test_exception(exc, func, *data):
    """Validate that func(data) raises exc"""
    try:
        func(*data)
    except exc:
        return True
    except:
        pass
    return False


def test_bdecode():
    """Test decoding of valid and erroneous sample strings"""
    assert _test_exception(ValueError, bdecode, '0:0:')
    assert _test_exception(ValueError, bdecode, 'ie')
    assert _test_exception(ValueError, bdecode, 'i341foo382e')
    assert bdecode('i4e') == 4L
    assert bdecode('i0e') == 0L
    assert bdecode('i123456789e') == 123456789L
    assert bdecode('i-10e') == -10L
    assert _test_exception(ValueError, bdecode, 'i-0e')
    assert _test_exception(ValueError, bdecode, 'i123')
    assert _test_exception(ValueError, bdecode, '')
    assert _test_exception(ValueError, bdecode, 'i6easd')
    assert _test_exception(ValueError, bdecode, '35208734823ljdahflajhdf')
    assert _test_exception(ValueError, bdecode, '2:abfdjslhfld')
    assert bdecode('0:') == ''
    assert bdecode('3:abc') == 'abc'
    assert bdecode('10:1234567890') == '1234567890'
    assert _test_exception(ValueError, bdecode, '02:xy')
    assert _test_exception(ValueError, bdecode, 'l')
    assert bdecode('le') == []
    assert _test_exception(ValueError, bdecode, 'leanfdldjfh')
    assert bdecode('l0:0:0:e') == ['', '', '']
    assert _test_exception(ValueError, bdecode, 'relwjhrlewjh')
    assert bdecode('li1ei2ei3ee') == [1, 2, 3]
    assert bdecode('l3:asd2:xye') == ['asd', 'xy']
    assert bdecode('ll5:Alice3:Bobeli2ei3eee') == [['Alice', 'Bob'], [2, 3]]
    assert _test_exception(ValueError, bdecode, 'd')
    assert _test_exception(ValueError, bdecode, 'defoobar')
    assert bdecode('de') == {}
    assert bdecode('d3:agei25e4:eyes4:bluee') == {'age': 25, 'eyes': 'blue'}
    assert bdecode('d8:spam.mp3d6:author5:Alice6:lengthi100000eee') == \
        {'spam.mp3': {'author': 'Alice', 'length': 100000}}
    assert _test_exception(ValueError, bdecode, 'd3:fooe')
    assert _test_exception(ValueError, bdecode, 'di1e0:e')
    assert _test_exception(ValueError, bdecode, 'd1:b0:1:a0:e')
    assert _test_exception(ValueError, bdecode, 'd1:a0:1:a0:e')
    assert _test_exception(ValueError, bdecode, 'i03e')
    assert _test_exception(ValueError, bdecode, 'l01:ae')
    assert _test_exception(ValueError, bdecode, '9999:x')
    assert _test_exception(ValueError, bdecode, 'l0:')
    assert _test_exception(ValueError, bdecode, 'd0:0:')
    assert _test_exception(ValueError, bdecode, 'd0:')

BENCACHED_MARKER = []


class Bencached:
    """Store the ciphertext of repeatedly encoded data structures"""
    def __init__(self, ctext):
        self.marker = BENCACHED_MARKER
        self.bencoded = ctext

    @classmethod
    def get(cls, _encoder, data, ctext):
        """Get cached ciphertext from Bencached object

        Called with an encoder, so use class method to rearrange parameters
        """
        assert data.marker == BENCACHED_MARKER
        ctext.append(data.bencoded)

BencachedType = type(Bencached(''))     # insufficient, but good as a filter


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
        self.encode_func[type(data)](self, data, ctext)
        return ''.join(ctext)

    def encode_unicode(self, string, ctext):
        """Encode unicode string into string segments appended to
        ciphertext list

        A unicode string is converted into UTF-8 and encoded as any other
        string.
        """
        #ctext.append('u')
        self.encode_func[str](self, string.encode('UTF-8'), ctext)

    def encode_list(self, data, ctext):
        """Encode list into string segments appended to ciphertext list

        A list takes the form lXe where X is the concatenation of the
        encodings of all elements in the list.
        """
        ctext.append('l')
        for element in data:
            self.encode_func[type(element)](self, element, ctext)
        ctext.append('e')

    def encode_dict(self, data, ctext):
        """Encode dictionary into string segments appended to
        ciphertext list

        A dictionary is encoded as dXe where X is the concatenation of the
        encodings of all key,value pairs in the dictionary, sorted by key.
        Key, value pairs are themselves concatenations of the encodings of
        keys and values, where keys are assumed to be strings.
        """
        ctext.append('d')
        ilist = data.items()
        ilist.sort()
        for key, value in ilist:
            ctext.extend((str(len(key)), ':', key))
            self.encode_func[type(value)](self, value, ctext)
        ctext.append('e')

    encode_func = {
        # Cached values are retrieved directly from the cache object
        BencachedType:  Bencached.get,

        # An integer with decimal representation X is encoded as "iXe"
        IntType:        lambda _s, i, c: c.extend(('i', str(i), 'e')),
        LongType:       lambda _s, i, c: c.extend(('i', str(i), 'e')),

        # Booleans are encoded as integers of value 0 or 1
        BooleanType:    lambda _s, b, c: c.extend(('i', str(int(b)), 'e')),

        # Strings are encoded with decimal length, followed by a colon and
        # the string itself
        StringType:     lambda _s, s, c: c.extend((str(len(s)), ':', s)),

        # Types that are slightly less simple to encode
        UnicodeType:    encode_unicode,
        ListType:       encode_list,
        TupleType:      encode_list,
        DictType:       encode_dict
    }


bencode = BTEncoder().__call__


def test_bencode():
    """Test encoding of encodable and unencodable data structures"""
    assert bencode(4) == 'i4e'
    assert bencode(0) == 'i0e'
    assert bencode(-10) == 'i-10e'
    assert bencode(12345678901234567890L) == 'i12345678901234567890e'
    assert bencode('') == '0:'
    assert bencode('abc') == '3:abc'
    assert bencode('1234567890') == '10:1234567890'
    assert bencode([]) == 'le'
    assert bencode([1, 2, 3]) == 'li1ei2ei3ee'
    assert bencode([['Alice', 'Bob'], [2, 3]]) == 'll5:Alice3:Bobeli2ei3eee'
    assert bencode({}) == 'de'
    assert bencode({'age': 25, 'eyes': 'blue'}) == 'd3:agei25e4:eyes4:bluee'
    assert bencode({'spam.mp3': {'author': 'Alice', 'length': 100000}}) == \
        'd8:spam.mp3d6:author5:Alice6:lengthi100000eee'
    assert _test_exception(TypeError, bencode, {1: 'foo'})
    assert _test_exception(KeyError, bencode, {'foo': 1.0})

    cached = Bencached(bencode({'age': 25}))
    assert bencode(cached) == cached.bencoded

    assert bencode(u'') == bencode('')
