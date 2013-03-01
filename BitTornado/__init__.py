product_name = 'BitTornado'
version_short = 'T-0.3.18'

version = version_short + ' (' + product_name + ')'
report_email = version_short + '@degreez.net'

__author__ = """
Christopher J. Johnson <effigies@gmail.com>

Original BitTornado code by:
Bram Cohen, Henry 'Pi' James, Bill Bumgarner, Petru Paler,
Uoti Urpala, Ross Cohen, Edward Keyes and John Hoffman
"""
__credits__ = """
Yejun Yang and Myers Carpenter for NAT port mapping code adapted
    in natpunch
"""
__version__ = version_short

from sha import sha
from time import time, clock
try:
    from os import getpid
except ImportError:
    def getpid():
        return 1

mapbase64 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.-'

_idprefix = version_short[0]
for subver in version_short[2:].split('.'):
    try:
        subver = int(subver)
    except:
        subver = 0
    _idprefix += mapbase64[subver]
_idprefix += ('-' * (6 - len(_idprefix)))
_idrandom = [None]


def resetPeerIDs():
    try:
        with open('/dev/urandom', 'rb') as f:
            x = f.read(20)
    except:
        x = ''

    l1 = 0
    t = clock()
    while t == clock():
        l1 += 1
    l2 = 0
    t = long(time() * 100)
    while t == long(time() * 100):
        l2 += 1
    l3 = 0
    if l2 < 1000:
        t = long(time() * 10)
        while t == long(clock() * 10):
            l3 += 1
    x += '{}/{}/{}/{}/{}/{}'.format(repr(time()), time(), l1, l2, l3, getpid())

    s = ''
    for i in sha(x).digest()[-11:]:
        s += mapbase64[ord(i) & 0x3F]
    _idrandom[0] = s

resetPeerIDs()


def createPeerID(ins='---'):
    assert isinstance(ins, str)
    assert len(ins) == 3
    return _idprefix + ins + _idrandom[0]
