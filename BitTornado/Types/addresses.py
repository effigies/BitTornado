"""Tools for validating, parsing, and comparing network addresses.

Address is an abstract class, of which IPv4 and IPv6 are subclasses,
which builds on top of the socket parsing of network addresses and
represents addresses directly as their integer values. IP is the
direct superclass of IPv4 and IPv6, which accepts valid addresses for
either class, preferring IPv4 in ambiguous cases.
"""

import socket
from .primitives import UnsignedInt


class Address(UnsignedInt):
    """Unsigned integer representations of network addresses, building on the
    socket library.

    Subclass with number of bits and address family."""
    family = None

    def __new__(cls, val=0):
        """Convert a number or a string to an Address."""
        if cls.bits is None or cls.family is None:
            raise NotImplementedError(
                "Do not call {!s}() directly".format(cls.__name__))

        if isinstance(val, str):
            if val.find(':') < 0:
                try:
                    val = socket.gethostbyname(val)
                except socket.gaierror:
                    pass

            try:
                return cls.from_bytes(socket.inet_pton(cls.family, val), 'big')
            except OSError:
                raise ValueError("invalid literal for {}(): {!r}".format(
                    cls.__name__, val))
        return super(Address, cls).__new__(cls, val)

    def __str__(self):
        """Use socket library formatting"""
        return socket.inet_ntop(self.family,
                                self.to_bytes(self.bits // 8, 'big'))

    def mask(self, nbits):
        """Return an address with the first n bits preserved and the
        rest zeroes out."""
        ones = (1 << self.bits) - 1
        return self.__class__(self & (ones << (self.bits - nbits)))


class IP(Address):
    """Generic IP address

    IP() == IPv4('0.0.0.0')
    IP('::') == IPv6('::')

    Enables conversion between IP classes:

    IP().to(IPv6) == IPv6('::ffff:0:0')
    IP('::ffff:0:0').to(IPv4) == IPv4('0.0.0.0')
    """
    v4mask = 0xffff00000000

    def __new__(cls, val=0):
        if cls.family is None:
            for subclass in cls.subclasses:
                try:
                    return subclass(val)
                except (ValueError, OverflowError):
                    pass
            raise ValueError('Invalid address: {}'.format(val))
        return super(IP, cls).__new__(cls, val)

    def to(self, cls):  # pylint: disable=invalid-name
        """Convert between IP classes, if possible.

        IPv4('w.x.y.z').to(IPv6) == IPv6('::ffff:w.x.y.z')
        IPv6('::ffff:w.x.y.z').to(IPv4) == IPv4('w.x.y.z')
        """
        if isinstance(self, cls):
            return self
        try:
            return cls(self.convert[type(self)][cls](self))
        except (KeyError, OverflowError):
            raise ValueError("not convertible to {}".format(cls.__name__))


class IPv4(IP):
    """Integer representation of IPv4 network addresses, building on the
    socket library."""
    bits = 32
    family = socket.AF_INET


class IPv6(IP):
    """Integer representation of IPv6 network addresses, building on the
    socket library."""
    bits = 128
    family = socket.AF_INET6


IP.subclasses = (IPv4, IPv6)
IP.convert = {IPv4: {IPv6: lambda x: x | IP.v4mask},
              IPv6: {IPv4: lambda x: x ^ IP.v4mask}}
