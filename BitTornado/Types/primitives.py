import math


class FixedLengthBytes(bytes):
    """Bytes variant that imposes a fixed length constraint on values"""
    length = None

    def __new__(cls, *args, **kwargs):
        if cls.length is None:
            raise NotImplementedError
        if not args and not kwargs:
            args = [bytes(cls.length)]
        val = super(FixedLengthBytes, cls).__new__(cls, *args, **kwargs)
        if len(val) != cls.length:
            raise ValueError("invalid length for {}: {!r}".format(cls.__name__,
                                                                  val))
        return val


class SixBytes(FixedLengthBytes):
    length = 6


class TwentyBytes(FixedLengthBytes):
    length = 20


class UnsignedInt(int):
    """Generic unsigned integer. Handles assertions and common
    functions for subclasses.
    """
    bits = None

    def __new__(cls, *args, **kwargs):
        """Create a new UnsignedInt object, verifying nonnegativity and checking
        bounds for subclasses where bits is defined"""
        val = super(UnsignedInt, cls).__new__(cls, *args, **kwargs)
        if val < 0:
            raise OverflowError("can't convert negative int to {}".format(
                cls.__name__))
        if cls.bits is not None and val.bit_length() > cls.bits:
            raise OverflowError("too large a value for {}: {!s}".format(
                cls.__name__, val))
        return val

    def byte_length(self):
        """Number of bytes required to represent the object.

        If bits is set, calculate from bits."""
        nbits = self.bit_length() if self.bits is None else self.bits
        return int(math.ceil(nbits / 8.0))

    def bytestring(self):
        """A big-endian bytestring representation of the integer.

        If maxbytes is set, length is always maxbytes."""
        return super(UnsignedInt, self).to_bytes(self.byte_length(), 'big')


class UnsignedShort(UnsignedInt):
    """
    Short:
        2 byte unsigned value, big-endian
    """
    bits = 16
