# Written by John Hoffman
# based on code by Uoti Urpala
# see LICENSE.txt for license information

from __future__ import generators   # for python 2.2
from random import randrange,randint,seed
try:
    from os import urandom
except:
    seed()
    urandom = lambda x: ''.join([chr(randint(0,255)) for i in xrange(x)])
from sha import sha

try:
    True
except:
    True = 1
    False = 0
    
try:
    from Crypto.Cipher import ARC4
    CRYPTO_OK = True
except:
    CRYPTO_OK = False

KEY_LENGTH = 160
DH_PRIME = 0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A63A36210000000000090563
PAD_MAX = 200 # less than protocol maximum, and later assumed to be < 256
DH_BYTES = 96

def bytetonum(x):
    return long(x.encode('hex'), 16)

def numtobyte(x):
    x = hex(x).lstrip('0x').rstrip('Ll')
    x = '0'*(192 - len(x)) + x
    return x.decode('hex')

class Crypto:
    def __init__(self, initiator, disable_crypto = False):
        self.initiator = initiator
        self.disable_crypto = disable_crypto
        if not disable_crypto and not CRYPTO_OK:
            raise NotImplementedError, "attempt to run encryption w/ none installed"
        self.privkey = bytetonum(urandom(KEY_LENGTH/8))
        self.pubkey = numtobyte(pow(2, self.privkey, DH_PRIME))
        self.keylength = DH_BYTES
        self._VC_pattern = None

    def received_key(self, k):
        self.S = numtobyte(pow(bytetonum(k), self.privkey, DH_PRIME))
        self.block3a = sha('req1'+self.S).digest()
        self.block3bkey = sha('req3'+self.S).digest()
        self.block3b = None

    def _gen_block3b(self, SKEY):
        a = sha('req2'+SKEY).digest()
        return ''.join([ chr(ord(a[i])^ord(self.block3bkey[i]))
                         for i in xrange(20) ])

    def test_skey(self, s, SKEY):
        block3b = self._gen_block3b(SKEY)
        if block3b != s:
            return False
        self.block3b = block3b
        if not self.disable_crypto:
            self.set_skey(SKEY)
        return True

    def set_skey(self, SKEY):
        if not self.block3b:
            self.block3b = self._gen_block3b(SKEY)
        crypta = ARC4.new(sha('keyA'+self.S+SKEY).digest())
        cryptb = ARC4.new(sha('keyB'+self.S+SKEY).digest())
        if self.initiator:
            self.encrypt = crypta.encrypt
            self.decrypt = cryptb.decrypt
        else:
            self.encrypt = cryptb.encrypt
            self.decrypt = crypta.decrypt
        self.encrypt('x'*1024)  # discard first 1024 bytes
        self.decrypt('x'*1024)

    def VC_pattern(self):
        if not self._VC_pattern:
            self._VC_pattern = self.decrypt('\x00'*8)
        return self._VC_pattern


    def read(self, s):
        self._read(self.decrypt(s))

    def write(self, s):
        self._write(self.encrypt(s))

    def setrawaccess(self, _read, _write):
        self._read = _read
        self._write = _write

    def padding(self):
        return urandom(randrange(PAD_MAX-16)+16)
     
        
