import os
import random
import hashlib

URANDOM = getattr(os, 'urandom', None)
if not URANDOM:
    random.seed()
    URANDOM = lambda x: bytes(random.randrange(256) for _ in range(x))

try:
    from Crypto.Cipher import ARC4
    CRYPTO_OK = True
except ImportError:
    CRYPTO_OK = False

KEY_LENGTH = 160
DH_PRIME = int('0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1'
               '29024E088A67CC74020BBEA63B139B22514A08798E3404DDEF'
               '9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485'
               'B576625E7EC6F44C42E9A63A36210000000000090563', 16)
PAD_MAX = 200   # less than protocol maximum, and later assumed to be < 256
DH_BYTES = 96


def padding():
    """Return 16-200 random bytes"""
    return URANDOM(random.randrange(16, PAD_MAX))


#pylint: disable=E1101
class Crypto(object):
    encrypt = None
    decrypt = None
    block3a = None
    block3b = None
    block3bkey = None
    S = None
    _read = None
    _write = None

    def __init__(self, initiator, disable_crypto=False):
        self.initiator = initiator
        self.disable_crypto = disable_crypto
        if not disable_crypto and not CRYPTO_OK:
            raise NotImplementedError("attempt to run encryption w/ none "
                                      "installed")
        self.privkey = int.from_bytes(URANDOM(KEY_LENGTH // 8), 'big')
        self.pubkey = pow(2, self.privkey, DH_PRIME).to_bytes(96, 'big')
        self.keylength = DH_BYTES
        self._VC_pattern = None

    def received_key(self, k):
        self.S = pow(int.from_bytes(k, 'big'), self.privkey,
                     DH_PRIME).to_bytes(96, 'big')
        self.block3a = hashlib.sha1(b'req1' + self.S).digest()
        self.block3bkey = hashlib.sha1(b'req3' + self.S).digest()
        self.block3b = None

    def _gen_block3b(self, SKEY):
        req2key = hashlib.sha1(b'req2' + SKEY).digest()
        return bytes(a ^ b for a, b in zip(req2key, self.block3bkey))

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
        crypta = ARC4.new(hashlib.sha1(b'keyA' + self.S + SKEY).digest())
        cryptb = ARC4.new(hashlib.sha1(b'keyB' + self.S + SKEY).digest())
        if self.initiator:
            self.encrypt = crypta.encrypt
            self.decrypt = cryptb.decrypt
        else:
            self.encrypt = cryptb.encrypt
            self.decrypt = crypta.decrypt
        self.encrypt(b'x' * 1024)  # discard first 1024 bytes
        self.decrypt(b'x' * 1024)

    def VC_pattern(self):
        if not self._VC_pattern:
            self._VC_pattern = self.decrypt(b'\x00' * 8)
        return self._VC_pattern

    def read(self, string):
        """Decrypt string and read"""
        self._read(self.decrypt(string))

    def write(self, string):
        """Encrypt string and write"""
        self._write(self.encrypt(string))

    def setrawaccess(self, _read, _write):
        """Set read/write functions to mediate with decryption/encryption"""
        self._read = _read
        self._write = _write

    def padded_pubkey(self):
        """Return public key followed by 16-200 bytes of padding"""
        return self.pubkey + padding()
