from ..Meta.bencode import bencode, Bencached, BencodedFile
from ..Types import TypedDict, BytesIndexed, Infohash, PeerID, Port, \
    UnsignedInt, IPv4, SixBytes
from .torrentlistparse import HashSet


class Counter(BytesIndexed):
    """Associate a count with an infohash"""
    keytype = Infohash
    valtype = UnsignedInt


class Times(BytesIndexed):
    """Update times for peers leeching/seeding each infohash"""
    class Pings(BytesIndexed):
        keytype = PeerID
        valtype = UnsignedInt
    keytype = Infohash
    valtype = Pings


class Peer(TypedDict):
    typemap = {'ip': str, 'port': Port, 'left': UnsignedInt, 'nat': bool,
               'requirecrypto': bool, 'supportcrypto': bool,
               'key': str, 'given ip': str}

    def validate(self):
        required_keys = ('ip', 'port', 'left', 'requirecrypto',
                         'supportcrypto')
        for key in required_keys:
            if key not in self:
                raise ValueError("Missing key: {}".format(key))


class Downloads(BytesIndexed):
    """Map from 20-byte infohash to connected Peers"""
    class Peers(BytesIndexed):
        """Map from 20-byte peer ID to Peer info"""
        keytype = PeerID
        valtype = Peer
    keytype = Infohash
    valtype = Peers


class TrackerState(TypedDict, BencodedFile):
    typemap = {'completed': Counter, 'peers': Downloads, 'allowed': dict,
               'allowed_dir_files': dict, 'allowed_list': HashSet}

    def validate(self):
        downloads = self.get('peers', Downloads())
        for peers in downloads.values():
            for peer in peers.values():
                peer.validate()

        allowed = self.get('allowed', {})
        ad_files = self.get('allowed_dir_files', {})
        allowed_hashes = set(allowed.keys())
        ad_hashes = set(ihash for meta, ihash in ad_files.values())
        if ad_hashes - allowed_hashes:
            raise ValueError("Allowed infohash mismatch")
        if len(ad_hashes) < len(ad_files):
            raise ValueError("Duplicate infohash in allowed directory")


class CachedResponse(BytesIndexed):
    keytype = PeerID
    valtype = bytes


class Compact(CachedResponse):
    valtype = SixBytes


class AllPeers(CachedResponse):
    valtype = (SixBytes, bool)


class Cache(object):
    def __init__(self, cachetype):
        self.leechers = cachetype()
        self.seeds = cachetype()

    def swap_peer(self, peerid, toseed):
        src = self.leechers if toseed else self.seeds
        dst = self.seeds if toseed else self.leechers
        if peerid in src:
            dst[peerid] = src.pop(peerid)

    def __getitem__(self, index):
        return self.seeds if index else self.leechers

    def __repr__(self):
        return '<Cache: leech={!r} seeds={!r}>'.format(self.leechers,
                                                       self.seeds)


class DownloadCache(object):
    def __init__(self, compact_required):
        self.compact_required = compact_required

        self.plaintext = Cache(Compact)
        self.encrypting = Cache(Compact)
        self.any_crypto = Cache(AllPeers)
        self._caches = (self.plaintext, self.encrypting, self.any_crypto)
        if not compact_required:
            self.identified_peers = Cache(CachedResponse)
            self.unidentified_peers = Cache(CachedResponse)
            self._caches += (self.identified_peers, self.identified_peers)

    def __repr__(self):
        return '<DownloadCache: any_crypto={!r}>'.format(self.any_crypto)

    def swap_peer(self, peerid, toseed):
        for cache in self._caches:
            cache.swap_peer(peerid, toseed)

    def remove_peer(self, peerid, seeding):
        for cache in self._caches:
            peers = cache.seeds if seeding else cache.leechers
            peers.pop(peerid, None)

    def add_peer(self, peerid, peer, ip, port):
        seed = not peer['left']
        cp = compact_peer_info(ip, port)
        reqc = bool(peer['requirecrypto'])
        self.any_crypto[seed][peerid] = (cp, reqc)
        if peer['supportcrypto']:
            self.encrypting[seed][peerid] = cp
        if not reqc:
            self.plaintext[seed][peerid] = cp
            if not self.compact_required:
                self.identified_peers[seed][peerid] = Bencached(
                    bencode({'ip': ip, 'port': port, 'peer id': peerid}))
                self.unidentified_peers[seed][peerid] = Bencached(
                    bencode({'ip': ip, 'port': port}))

    def get_peers(self, return_type):
        return self._caches[return_type]


class BencodedCache(BytesIndexed):
    keytype = Infohash
    valtype = DownloadCache

    def __init__(self, compact_required):
        super(BencodedCache, self).__init__()
        self.compact_required = bool(compact_required)

    def __getitem__(self, infohash):
        if infohash not in self:
            self[infohash] = DownloadCache(self.compact_required)
        return super(BencodedCache, self).__getitem__(infohash)


def compact_peer_info(ip, port):
    try:
        return IPv4(ip).to_bytes(4, 'big') + port.to_bytes(2, 'big')
    except ValueError:
        return b''  # not a valid IP, must be a domain name
