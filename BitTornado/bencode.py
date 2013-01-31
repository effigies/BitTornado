# Written by Petru Paler, Uoti Urpala, Ross Cohen and John Hoffman
# see LICENSE.txt for license information

from types import IntType, LongType, StringType, ListType, TupleType, DictType, BooleanType
try:
    from types import UnicodeType
except ImportError:
    UnicodeType = None

def decode_int(x, f):
    """Decode integer in string x at position f

    An integer with ASCII representation X will be encoded as "iXe". A
    ValueError will be thrown if X begins with 0 but is not simply '0', or if
    X begins with '-0'.
    
    Returns (parsed integer, next token start position)
    """
    f += 1
    newf = x.index('e', f)
    n = int(x[f:newf])

    # '-0' is invalid and strings beginning with '0' must be == '0'
    if x[f:f+2] == '-0' or (x[f] == '0' and newf != f+1):
        raise ValueError

    return (n, newf+1)
  
def decode_string(x, f):
    """Decode string in string x at position f

    A string is encoded as an integer length, followed by a colon and a string
    of the length given. A ValueError is thrown if length begins with '0' but
    is not '0'.
    
    Returns (parsed string, next token start position)
    """
    colon = x.index(':', f)
    n = int(x[f:colon])

    # '0:' is the only valid string beginning with '0'
    if x[f] == '0' and colon != f+1:
        raise ValueError

    colon += 1
    return (x[colon:colon+n], colon+n)

def decode_unicode(x, f):
    """Decode unicode string in string x at position f

    A unicode string is simply a string encoding preceded by a u.
    """
    s, f = decode_string(x, f+1)
    return (s.decode('UTF-8'),f)

def decode_list(x, f):
    """Decode list in string x at position f
    
    A list takes the form lXe where X is the concatenation of the encodings of
    all elements in the list.
    
    Returns (parsed list, next token start position)
    """
    r, f = [], f+1
    while x[f] != 'e':
        v, f = decode_func[x[f]](x, f)
        r.append(v)
    return (r, f + 1)

def decode_dict(x, f):
    """Decode dictionary in string x at position f

    A dictionary is encoded as dXe where X is the concatenation of the
    encodings of all key,value pairs in the dictionary, sorted by key.
    Key, value paris are themselves concatenations of the encodings of
    keys and values, where keys are assumed to be strings.
    
    Returns (parsed dictionary, next token start position)
    """
    r, f = {}, f+1
    lastkey = None
    while x[f] != 'e':
        k, f = decode_string(x, f)
        if lastkey >= k:
            raise ValueError
        lastkey = k
        r[k], f = decode_func[x[f]](x, f)
    return (r, f + 1)

decode_func = {}
decode_func['l'] = decode_list
decode_func['d'] = decode_dict
decode_func['i'] = decode_int
decode_func['0'] = decode_string
decode_func['1'] = decode_string
decode_func['2'] = decode_string
decode_func['3'] = decode_string
decode_func['4'] = decode_string
decode_func['5'] = decode_string
decode_func['6'] = decode_string
decode_func['7'] = decode_string
decode_func['8'] = decode_string
decode_func['9'] = decode_string
#decode_func['u'] = decode_unicode
  
def bdecode(x, sloppy = 0):
    """Decode a string encoded with bencode, such as the contents of a
    .torrent file"""
    try:
        r, l = decode_func[x[0]](x, 0)
    except (IndexError, KeyError, ValueError):
        raise ValueError, "bad bencoded data"
    if not sloppy and l != len(x):
        raise ValueError, "bad bencoded data"
    return r

def test_bdecode():
    try:
        bdecode('0:0:')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('ie')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('i341foo382e')
        assert 0
    except ValueError:
        pass
    assert bdecode('i4e') == 4L
    assert bdecode('i0e') == 0L
    assert bdecode('i123456789e') == 123456789L
    assert bdecode('i-10e') == -10L
    try:
        bdecode('i-0e')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('i123')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('i6easd')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('35208734823ljdahflajhdf')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('2:abfdjslhfld')
        assert 0
    except ValueError:
        pass
    assert bdecode('0:') == ''
    assert bdecode('3:abc') == 'abc'
    assert bdecode('10:1234567890') == '1234567890'
    try:
        bdecode('02:xy')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('l')
        assert 0
    except ValueError:
        pass
    assert bdecode('le') == []
    try:
        bdecode('leanfdldjfh')
        assert 0
    except ValueError:
        pass
    assert bdecode('l0:0:0:e') == ['', '', '']
    try:
        bdecode('relwjhrlewjh')
        assert 0
    except ValueError:
        pass
    assert bdecode('li1ei2ei3ee') == [1, 2, 3]
    assert bdecode('l3:asd2:xye') == ['asd', 'xy']
    assert bdecode('ll5:Alice3:Bobeli2ei3eee') == [['Alice', 'Bob'], [2, 3]]
    try:
        bdecode('d')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('defoobar')
        assert 0
    except ValueError:
        pass
    assert bdecode('de') == {}
    assert bdecode('d3:agei25e4:eyes4:bluee') == {'age': 25, 'eyes': 'blue'}
    assert bdecode('d8:spam.mp3d6:author5:Alice6:lengthi100000eee') == {'spam.mp3': {'author': 'Alice', 'length': 100000}}
    try:
        bdecode('d3:fooe')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('di1e0:e')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('d1:b0:1:a0:e')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('d1:a0:1:a0:e')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('i03e')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('l01:ae')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('9999:x')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('l0:')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('d0:0:')
        assert 0
    except ValueError:
        pass
    try:
        bdecode('d0:')
        assert 0
    except ValueError:
        pass

bencached_marker = []

class Bencached:
    def __init__(self, s):
        self.marker = bencached_marker
        self.bencoded = s

BencachedType = type(Bencached('')) # insufficient, but good as a filter

def encode_bencached(x,r):
    assert x.marker == bencached_marker
    r.append(x.bencoded)

def encode_int(x, r):
    """Encode integer x into string segments appended to list r

    An integer with ASCII representation X will be encoded as "iXe".
    """
    r.extend(('i',str(x),'e'))

def encode_bool(x, r):
    """Encode boolean x into string segments appended to list r

    A boolean is treated as an integer (0 or 1).
    """
    encode_int(int(x),r)

def encode_string(x, r):
    """Encode string x into string segments appended to list r

    A string is encoded as an integer length, followed by a colon and a string
    of the length given.
    """
    r.extend((str(len(x)),':',x))

def encode_unicode(x, r):
    """Encode unicode string x into string segments appended to list r

    A unicode string is converted into UTF-8 and encoded as any other string.
    """
    #r.append('u')
    encode_string(x.encode('UTF-8'),r)

def encode_list(x, r):
    """Encode list x into string segments appended to list r
    
    A list takes the form lXe where X is the concatenation of the encodings of
    all elements in the list.
    """
    r.append('l')
    for e in x:
        encode_func[type(e)](e, r)
    r.append('e')

def encode_dict(x, r):
    """Encode dictionary x into string segments appended to list r

    A dictionary is encoded as dXe where X is the concatenation of the
    encodings of all key,value pairs in the dictionary, sorted by key.
    Key, value paris are themselves concatenations of the encodings of
    keys and values, where keys are assumed to be strings.
    """
    r.append('d')
    ilist = x.items()
    ilist.sort()
    for k,v in ilist:
        r.extend((str(len(k)),':',k))
        encode_func[type(v)](v, r)
    r.append('e')

encode_func = {}
encode_func[BencachedType] = encode_bencached
encode_func[IntType] = encode_int
encode_func[LongType] = encode_int
encode_func[StringType] = encode_string
encode_func[ListType] = encode_list
encode_func[TupleType] = encode_list
encode_func[DictType] = encode_dict
encode_func[BooleanType] = encode_bool
if UnicodeType:
    encode_func[UnicodeType] = encode_unicode
    
def bencode(x):
    """Encode a data structure into a string.
    
    Creates a list in which to collect string segments and returns the
    joined result.
    
    See encode_* for details."""
    r = []
    encode_func[type(x)](x, r)
    return ''.join(r)

def test_bencode():
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
    assert bencode({'spam.mp3': {'author': 'Alice', 'length': 100000}}) == 'd8:spam.mp3d6:author5:Alice6:lengthi100000eee'
    try:
        bencode({1: 'foo'})
        assert 0
    except TypeError:
        pass
    try:
        bencode({'foo': 1.0})
        assert 0
    except KeyError:
        pass

  
try:
    import psyco
    psyco.bind(bdecode)
    psyco.bind(bencode)
except ImportError:
    pass
