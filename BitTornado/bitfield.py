"""Manipulable boolean list structure and related functions"""


def _int_to_booleans(integer):
    """Produce a tuple of booleans corresponding to 8 least significant bits
    in an integer
    """
    return tuple(bool((integer << nbits) & 0x80) for nbits in xrange(8))

CHARBITMAP = [_int_to_booleans(_chr) for _chr in xrange(256)]

BITCHARMAP = dict((_bits, chr(_chr)) for _chr, _bits in enumerate(CHARBITMAP))


class Bitfield(list):
    """Allow a sequence of booleans to be used as an indexable bitfield"""
    def __init__(self, length=None, bitstring=None, copyfrom=None, val=False):
        if copyfrom is not None:
            super(Bitfield, self).__init__(copyfrom)
            self.numfalse = copyfrom.numfalse
            return
        if length is None:
            raise ValueError('length must be provided unless copying from '
                             'another array')
        if bitstring is not None:
            extra = len(bitstring) * 8 - length
            if extra < 0 or extra >= 8:
                raise ValueError

            bits = [bit for char in bitstring for bit in CHARBITMAP[ord(char)]]
            if extra > 0:
                if bits[-extra:] != [False] * extra:
                    raise ValueError
                del bits[-extra:]
            self.numfalse = len(bits) - sum(bits)
        else:
            bits = [val] * length
            self.numfalse = 0 if val else length

        super(Bitfield, self).__init__(bits)

    def __setitem__(self, index, val):
        val = bool(val)
        self.numfalse += self[index] - val
        super(Bitfield, self).__setitem__(index, val)

    def __repr__(self):
        return "<Bitfield ({})>".format(','.join(str(int(i)) for i in self))

    def __str__(self):
        """Produce a bytestring corresponding to the current bitfield"""
        bits = self + [False] * (-len(self) % 8)
        return ''.join(BITCHARMAP[tuple(bits[x:x + 8])]
                       for x in xrange(0, len(bits), 8))

    @property
    def complete(self):
        """True if all booleans are True"""
        return not self.numfalse


class TrueBitfield(object):     # pylint: disable=R0903
    """A trivial structure that acts like an infinitely long field of
    True bits"""
    complete = True

    def __getitem__(self, index):
        return True


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
    assert str(Bitfield(0, '')) == ''
    assert str(Bitfield(1, chr(0x80))) == chr(0x80)
    assert str(Bitfield(7, chr(0x02))) == chr(0x02)
    assert str(Bitfield(8, chr(0xFF))) == chr(0xFF)
    assert str(Bitfield(9, chr(0) + chr(0x80))) == chr(0) + chr(0x80)
    testx = Bitfield(1)
    assert testx.numfalse == 1
    testx[0] = 1
    assert testx.numfalse == 0
    testx[0] = 1
    assert testx.numfalse == 0
    assert str(testx) == chr(0x80)
    testx = Bitfield(7)
    assert len(testx) == 7
    testx[6] = 1
    assert testx.numfalse == 6
    assert str(testx) == chr(0x02)
    testx = Bitfield(8)
    testx[7] = 1
    assert str(testx) == chr(1)
    testx = Bitfield(9)
    testx[8] = 1
    assert testx.numfalse == 8
    assert str(testx) == chr(0) + chr(0x80)
    testx = Bitfield(8, chr(0xC4))
    assert len(testx) == 8
    assert testx.numfalse == 5
    assert str(testx) == chr(0xC4)
