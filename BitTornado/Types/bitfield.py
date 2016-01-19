"""Manipulable boolean list structure and related functions"""

import math
import operator as ops

CHARBITMAP = [tuple(bool((integer << nbits) & 0x80) for nbits in range(8))
              for integer in range(256)]

BITCHARMAP = dict(zip(CHARBITMAP, range(256)))


class Bitfield(list):
    """Indexable sequence of mutable booleans

    Supports bitwise logical operations (&, ^, |, ~).

    Binary operations require the second operand to be interpretable as a
    Bitfield of the same size.

        - A Bitfield must be the same size as the first operand (arg1)
        - A bytes object must have the same length as bytes(arg1)
        - An int must be encodable as bytestring of length len(bytes(arg1))

    The first (most-significant) bit of a Bitfield is the first bit of its
    bytes representation. A Bitfield whose length is not divisible by 8
    will be zero-padded on the right. Binary operations with bytes or int
    may not behave intuitively in those cases.
    """
    def __init__(self, length=None, bitstring=None, copyfrom=None, val=False):
        if copyfrom is not None:
            super(Bitfield, self).__init__(copyfrom)
            if isinstance(copyfrom, Bitfield):
                self.numfalse = copyfrom.numfalse
            else:
                self.numfalse = len(self) - sum(self)
            return
        if length is None:
            raise ValueError('length must be provided unless copying from '
                             'another array')
        if bitstring is not None:
            extra = len(bitstring) * 8 - length
            if not 0 <= extra < 8:
                raise ValueError("Bitstring must be `ceiling(length // 8)` "
                                 "bytes long")

            if isinstance(bitstring, str):
                bitstring = map(ord, bitstring)
            bits = [bit for byte in bitstring for bit in CHARBITMAP[byte]]
            if extra > 0:
                if bits[-extra:] != [False] * extra:
                    raise ValueError("Excess (low order) bits must be zero")
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

    def __bytes__(self):
        """Produce a bytestring corresponding to the current bitfield

        NB: Zero-pads on the right. The first bit of the bytestring is the
        first bit of the bitfield.
        """
        bits = self + [False] * (-len(self) % 8)
        return bytes(BITCHARMAP[tuple(bits[x:x + 8])]
                     for x in range(0, len(bits), 8))

    def __invert__(self):
        """Flip all bits (~)"""
        return Bitfield(length=len(self), val=True) ^ Bitfield(copyfrom=self)

    def __and__(self, val):
        """Bitwise AND (&)

        Right-hand-side must be Bitfield, bytes, or int. (See object docs.)"""
        return self._bitwise_op(val, ops.and_)

    def __or__(self, val):
        """Bitwise OR (|)

        Right-hand-side must be Bitfield, bytes, or int. (See object docs.)"""
        return self._bitwise_op(val, ops.or_)

    def __xor__(self, val):
        """Bitwise XOR (^)

        Right-hand-side must be Bitfield, bytes, or int. (See object docs.)"""
        return self._bitwise_op(val, ops.xor)

    def _bitwise_op(self, val, op):
        """Perform bitwise operation"""
        nbits = len(self)
        nbytes = math.ceil(nbits / 8)

        if isinstance(val, Bitfield):
            if len(val) != nbits:
                raise ValueError("Cannot perform bitwise operation on "
                                 "differently sized Bitfields")
            val = bytes(val)
        if isinstance(val, bytes):
            if len(val) != nbytes:
                raise ValueError("Cannot perform bitwise operation on "
                                 "Bitfield and bytes object of unmatching "
                                 "length")
            val = int.from_bytes(val, 'big')
        if not isinstance(val, int):
            raise ValueError("Can only perform bitwise operations between "
                             "Bitfield object and Bitfield, bytes, or int")
        try:
            val.to_bytes(nbytes, 'big')
        except OverflowError:
            raise ValueError("Integer ({:d}) cannot be represented in {:d} "
                             "bits".format(val, nbits))
        if (val << nbits) & (2 ** nbits - 1):
            raise ValueError("Trailing bits must all be zero.")

        this = int.from_bytes(bytes(self), 'big')
        return Bitfield(nbits, op(this, val).to_bytes(nbytes, 'big'))

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
