from ..Types import Bitfield

protocol_name = b'\x13BitTorrent protocol'
reserved = Bitfield(64)

# Flags (See: http://www.bittorrent.org/beps/bep_0004.html)
# Byte Index: 0 1 2 3 4 5 6 7
DIST_HASH = 0x0000000000000001  # BEP 5: Distributed Hash Table
XBT_PEERX = 0x0000000000000002  # XBT Peer Exchange
FAST_EXTN = 0x0000000000000004  # BEP 6: Fast Extension
NAT_PUNCH = 0x0000000000000008  # NAT Traversal
# Byte Index: 0 1 2 3 4 5 6 7
EXT_NEG_1 = 0x0000000000010000  # Extension Negotiation Protocol (Deprecated)
EXT_NEG_2 = 0x0000000000020000  # Extension Negotiation Protocol (Deprecated)
EXTENSION = 0x0000000000100000  # BEP 10: Libtorrent Extension Protocol
# Byte Index: 0 1 2 3 4 5 6 7
LOC_AWARE = 0x0008000000000000  # BitTorrent Location-aware Protocol
COMET_BYT = 0x00ff000000000000  # BitComet Extension Protocol
# Byte Index: 0 1 2 3 4 5 6 7
AZURE_MSG = 0x8000000000000000  # Azureus Messaging Protocol
COMET_BYT = 0xff00000000000000  # BitComet Extension Protocol
