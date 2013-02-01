# Written by Bram Cohen, Uoti Urpala, and John Hoffman
# see LICENSE.txt for license information

def _int_to_booleans(x):
    return tuple(bool((x << i) & 0x80) for i in xrange(8))

charbitmap = [_int_to_booleans(i) for i in xrange(256)]

bitcharmap = dict((e,chr(i)) for i,e in enumerate(charbitmap))

class Bitfield:
    def __init__(self, length = None, bitstring = None, copyfrom = None):
        if copyfrom is not None:
            self.length = copyfrom.length
            self.array = copyfrom.array[:]
            self.numfalse = copyfrom.numfalse
            return
        if length is None:
            raise ValueError, "length must be provided unless copying from another array"
        self.length = length
        if bitstring is not None:
            extra = len(bitstring) * 8 - length
            if extra < 0 or extra >= 8:
                raise ValueError

            r = [bit for char in bitstring for bit in charbitmap[ord(char)]]
            if extra > 0:
                if r[-extra:] != [False] * extra:
                    raise ValueError
                del r[-extra:]
            self.array = r
            self.numfalse = len(r) - sum(r)
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
        bits = self.array + [False] * (-self.length % 8)
        return ''.join(bitcharmap[tuple(bits[x:x+8])]
                        for x in xrange(0, len(bits), 8))

    def complete(self):
        return not self.numfalse


def test_bitfield():
    try:
        x = Bitfield(7, 'ab')
        assert False
    except ValueError:
        pass
    try:
        x = Bitfield(7, 'ab')
        assert False
    except ValueError:
        pass
    try:
        x = Bitfield(9, 'abc')
        assert False
    except ValueError:
        pass
    try:
        x = Bitfield(0, 'a')
        assert False
    except ValueError:
        pass
    try:
        x = Bitfield(1, '')
        assert False
    except ValueError:
        pass
    try:
        x = Bitfield(7, '')
        assert False
    except ValueError:
        pass
    try:
        x = Bitfield(8, '')
        assert False
    except ValueError:
        pass
    try:
        x = Bitfield(9, 'a')
        assert False
    except ValueError:
        pass
    try:
        x = Bitfield(7, chr(1))
        assert False
    except ValueError:
        pass
    try:
        x = Bitfield(9, chr(0) + chr(0x40))
        assert False
    except ValueError:
        pass
    assert Bitfield(0, '').tostring() == ''
    assert Bitfield(1, chr(0x80)).tostring() == chr(0x80)
    assert Bitfield(7, chr(0x02)).tostring() == chr(0x02)
    assert Bitfield(8, chr(0xFF)).tostring() == chr(0xFF)
    assert Bitfield(9, chr(0) + chr(0x80)).tostring() == chr(0) + chr(0x80)
    x = Bitfield(1)
    assert x.numfalse == 1
    x[0] = 1
    assert x.numfalse == 0
    x[0] = 1
    assert x.numfalse == 0
    assert x.tostring() == chr(0x80)
    x = Bitfield(7)
    assert len(x) == 7
    x[6] = 1
    assert x.numfalse == 6
    assert x.tostring() == chr(0x02)
    x = Bitfield(8)
    x[7] = 1
    assert x.tostring() == chr(1)
    x = Bitfield(9)
    x[8] = 1
    assert x.numfalse == 8
    assert x.tostring() == chr(0) + chr(0x80)
    x = Bitfield(8, chr(0xC4))
    assert len(x) == 8
    assert x.numfalse == 5
    assert x.tostring() == chr(0xC4)
