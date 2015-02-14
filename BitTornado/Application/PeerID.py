import os
import time
import base64
import hashlib
import itertools
import BitTornado

mapbase64 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.-'


def countwhile(predicate):
    """Count number of iterations taken until predicate is true"""
    return sum(1 for i in itertools.takewhile(predicate, iter(int, 1)))


class PeerID(object):
    randstr = None

    def __init__(self):
        self.prefix = '{}{:-<5}'.format(
            BitTornado.version_short[0], ''.join(
                mapbase64[int(subversion or 0)] for subversion in
                BitTornado.version_short[2:].split('.')))

        self.reset()

    def reset(self):
        try:
            with open('/dev/urandom', 'rb') as f:
                x = f.read(20)
        except IOError:
            x = ''

        tic = time.clock()
        toc1 = countwhile(lambda x: tic == time.clock())
        tic = long(time.time() * 100)
        toc2 = countwhile(lambda x: tic == long(time.time() * 100))
        tic = long(time.time() * 10)
        toc3 = 0 if toc2 >= 1000 else \
            countwhile(lambda x: tic == long(time.time() * 10))

        x += '{}/{}/{}/{}/{}/{}'.format(repr(time.time()), time.time(),
                                        toc1, toc2, toc3, os.getpid())

        self.randstr = base64.urlsafe_b64encode(
            hashlib.sha1(x).digest()[-9:])[:11]

    def __str__(self):
        return self.create()

    def create(self, ins='---'):
        assert isinstance(ins, str)
        assert len(ins) == 3
        return self.prefix + ins + self.randstr

createPeerID = PeerID().create
