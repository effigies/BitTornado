def _int_to_booleans(integer):
    """Produce a tuple of booleans corresponding to 8 least significant bits
    in an integer
    """
    return tuple(bool((integer << nbits) & 0x80) for nbits in xrange(8))

charbitmap = [_int_to_booleans(_chr) for _chr in xrange(256)]

bitcharmap = dict((_bits, chr(_chr)) for _chr, _bits in enumerate(charbitmap))


class Bitfield:
    """Allow a sequence of booleans to be used as an indexable bitfield"""
    def __init__(self, length=None, bitstring=None, copyfrom=None):
        if copyfrom is not None:
            self.length = copyfrom.length
            self.array = copyfrom.array[:]
            self.numfalse = copyfrom.numfalse
            return
        if length is None:
            raise ValueError('length must be provided unless copying from '
                             'another array')
        self.length = length
        if bitstring is not None:
            extra = len(bitstring) * 8 - length
            if extra < 0 or extra >= 8:
                raise ValueError

            bits = [bit for char in bitstring for bit in charbitmap[ord(char)]]
            if extra > 0:
                if bits[-extra:] != [False] * extra:
                    raise ValueError
                del bits[-extra:]
            self.array = bits
            self.numfalse = len(bits) - sum(bits)
        else:
            self.array = [False] * length
            self.numfalse = length

    def __setitem__(self, index, val):
        val = bool(val)
        self.numfalse += self.array[index] - val
        self.array[index] = val

    def __getitem__(self, index):
        return self.array[index]

    def __len__(self):
        return self.length

    def tostring(self):
        """Produce a bytestring corresponding to the current bitfield"""
        bits = self.array + [False] * (-self.length % 8)
        return ''.join(bitcharmap[tuple(bits[x:x + 8])]
                       for x in xrange(0, len(bits), 8))

    def complete(self):
        """Return true if all booleans are True"""
        return not self.numfalse


def _test_exception(exc, func, *data):
    """Validate that func(data) raises exc"""
    try:
        func(*data)
    except exc:
        return True
    except:
        pass
    return False


def test_bitfield():
    """Unit test Bitfield"""
    assert _test_exception(ValueError, Bitfield, 7, 'ab')
    assert _test_exception(ValueError, Bitfield, 7, 'ab')
    assert _test_exception(ValueError, Bitfield, 9, 'abc')
    assert _test_exception(ValueError, Bitfield, 0, 'a')
    assert _test_exception(ValueError, Bitfield, 1, '')
    assert _test_exception(ValueError, Bitfield, 7, '')
    assert _test_exception(ValueError, Bitfield, 8, '')
    assert _test_exception(ValueError, Bitfield, 9, 'a')
    assert _test_exception(ValueError, Bitfield, 7, chr(1))
    assert _test_exception(ValueError, Bitfield, 9, chr(0) + chr(0x40))
    assert Bitfield(0, '').tostring() == ''
    assert Bitfield(1, chr(0x80)).tostring() == chr(0x80)
    assert Bitfield(7, chr(0x02)).tostring() == chr(0x02)
    assert Bitfield(8, chr(0xFF)).tostring() == chr(0xFF)
    assert Bitfield(9, chr(0) + chr(0x80)).tostring() == chr(0) + chr(0x80)
    testx = Bitfield(1)
    assert testx.numfalse == 1
    testx[0] = 1
    assert testx.numfalse == 0
    testx[0] = 1
    assert testx.numfalse == 0
    assert testx.tostring() == chr(0x80)
    testx = Bitfield(7)
    assert len(testx) == 7
    testx[6] = 1
    assert testx.numfalse == 6
    assert testx.tostring() == chr(0x02)
    testx = Bitfield(8)
    testx[7] = 1
    assert testx.tostring() == chr(1)
    testx = Bitfield(9)
    testx[8] = 1
    assert testx.numfalse == 8
    assert testx.tostring() == chr(0) + chr(0x80)
    testx = Bitfield(8, chr(0xC4))
    assert len(testx) == 8
    assert testx.numfalse == 5
    assert testx.tostring() == chr(0xC4)
