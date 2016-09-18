from .primitives import TwentyBytes, UnsignedShort


class Infohash(TwentyBytes):
    """SHA-1 hash digest"""


class PeerID(TwentyBytes):
    """Unique peer identifier"""


class Port(UnsignedShort):
    """TCP/IP port number ranging from 0 to 65535"""
