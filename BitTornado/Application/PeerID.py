import os
import time
import base64
import hashlib
import itertools
import BitTornado

mapbase64 = b'0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.-'


def countwhile(predicate):
    """Count number of iterations taken until predicate is true"""
    return sum(1 for i in itertools.takewhile(predicate, iter(int, 1)))


class PeerID(object):
    randstr = None

    def __init__(self):
        initial, version = BitTornado.version_short.split('-')
        vbytes = bytes(mapbase64[int(sub or 0)] for sub in version.split('.'))
        padding = b'-' * (5 - len(vbytes))
        self.prefix = initial.encode() + vbytes + padding

        self.reset()

    def reset(self):
        try:
            with open('/dev/urandom', 'rb') as f:
                x = f.read(20)
        except IOError:
            x = b''

        tic = time.clock()
        toc1 = countwhile(lambda x: tic == time.clock())
        tic = int(time.time() * 100)
        toc2 = countwhile(lambda x: tic == int(time.time() * 100))
        tic = int(time.time() * 10)
        toc3 = 0 if toc2 >= 1000 else \
            countwhile(lambda x: tic == int(time.time() * 10))

        x += '{!r}/{}/{}/{}/{}/{}'.format(time.time(), time.time(), toc1, toc2,
                                          toc3, os.getpid()).encode()

        self.randstr = base64.urlsafe_b64encode(
            hashlib.sha1(x).digest()[-9:])[:11]

    def __str__(self):
        return self.create()

    def create(self, ins=b'---'):
        if isinstance(ins, int):
            assert ins < 0x3ffff
            ins = bytes(mapbase64[(ins >> 6 * i) & 0x3f] for i in range(3))
        assert isinstance(ins, bytes)
        assert len(ins) == 3
        return self.prefix + ins + self.randstr

createPeerID = PeerID().create
