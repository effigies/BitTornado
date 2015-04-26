"""Manipulable boolean list structure and related functions"""


def _int_to_booleans(integer):
    """Produce a tuple of booleans corresponding to 8 least significant bits
    in an integer
    """
    return tuple(bool((integer << nbits) & 0x80) for nbits in range(8))

CHARBITMAP = [_int_to_booleans(_chr) for _chr in range(256)]

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
            if not 0 <= extra < 8:
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
                       for x in range(0, len(bits), 8))

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
