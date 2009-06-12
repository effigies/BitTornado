# Written by Bram Cohen
# see LICENSE.txt for license information

from cStringIO import StringIO
from socket import error as socketerror
from traceback import print_exc
from BitTornado.BTcrypto import Crypto, CRYPTO_OK

try:
    True
except:
    True = 1
    False = 0

CHECK_PEER_ID_ENCRYPTED = True

protocol_name = 'BitTorrent protocol'

# header, reserved, download id, my id, [length, message]

class NatCheck:
    def __init__(self, resultfunc, downloadid, peerid, ip, port, rawserver,
                 encrypted = False):
        self.resultfunc = resultfunc
        self.downloadid = downloadid
        self.peerid = peerid
        self.ip = ip
        self.port = port
        self.encrypted = encrypted
        self.closed = False
        self.buffer = ''
        self.read = self._read
        self.write = self._write
        try:
            self.connection = rawserver.start_connection((ip, port), self)
            if encrypted:
                self._dc = not(CRYPTO_OK and CHECK_PEER_ID_ENCRYPTED)
                self.encrypter = Crypto(True, disable_crypto = self._dc)
                self.write(self.encrypter.pubkey+self.encrypter.padding())
            else:
                self.encrypter = None
                self.write(chr(len(protocol_name)) + protocol_name +
                    (chr(0) * 8) + downloadid)
        except socketerror:
            self.answer(False)
        except IOError:
            self.answer(False)
        self.next_len, self.next_func = 1+len(protocol_name), self.read_header

    def answer(self, result):
        self.closed = True
        try:
            self.connection.close()
        except AttributeError:
            pass
        self.resultfunc(result, self.downloadid, self.peerid, self.ip, self.port)

    def _read_header(self, s):
        if s == chr(len(protocol_name))+protocol_name:
            return 8, self.read_options
        return None

    def read_header(self, s):
        if self._read_header(s):
            if self.encrypted:
                return None
            return 8, self.read_options
        if not self.encrypted:
            return None
        self._write_buffer(s)
        return self.encrypter.keylength, self.read_crypto_header

    ################## ENCRYPTION SUPPORT ######################

    def _start_crypto(self):
        self.encrypter.setrawaccess(self._read,self._write)
        self.write = self.encrypter.write
        self.read = self.encrypter.read
        if self.buffer:
            self.buffer = self.encrypter.decrypt(self.buffer)

    def read_crypto_header(self, s):
        self.encrypter.received_key(s)
        self.encrypter.set_skey(self.downloadid)
        cryptmode = '\x00\x00\x00\x02'    # full stream encryption
        padc = self.encrypter.padding()
        self.write( self.encrypter.block3a
                  + self.encrypter.block3b
                  + self.encrypter.encrypt(
                        ('\x00'*8)            # VC
                      + cryptmode             # acceptable crypto modes
                      + tobinary16(len(padc))
                      + padc                  # PadC
                      + '\x00\x00' ) )        # no initial payload data
        self._max_search = 520
        return 1, self.read_crypto_block4a

    def _search_for_pattern(self, s, pat):
        p = s.find(pat)
        if p < 0:
            if len(s) >= len(pat):
                self._max_search -= len(s)+1-len(pat)
            if self._max_search < 0:
                self.close()
                return False
            self._write_buffer(s[1-len(pat):])
            return False
        self._write_buffer(s[p+len(pat):])
        return True

    ### OUTGOING CONNECTION ###

    def read_crypto_block4a(self, s):
        if not self._search_for_pattern(s,self.encrypter.VC_pattern()):
            return -1, self.read_crypto_block4a     # wait for more data
        if self._dc:                        # can't or won't go any further
            self.answer(True)
            return None
        self._start_crypto()
        return 6, self.read_crypto_block4b

    def read_crypto_block4b(self, s):
        self.cryptmode = toint(s[:4]) % 4
        if self.cryptmode != 2:
            return None                     # unknown encryption
        padlen = (ord(s[4])<<8)+ord(s[5])
        if padlen > 512:
            return None
        if padlen:
            return padlen, self.read_crypto_pad4
        return self.read_crypto_block4done()

    def read_crypto_pad4(self, s):
        # discard data
        return self.read_crypto_block4done()

    def read_crypto_block4done(self):
        if DEBUG:
            self._log_start()
        if self.cryptmode == 1:     # only handshake encryption
            if not self.buffer:  # oops; check for exceptions to this
                return None
            self._end_crypto()
        self.write(chr(len(protocol_name)) + protocol_name + 
            option_pattern + self.Encoder.download_id)
        return 1+len(protocol_name), self.read_encrypted_header

    ### START PROTOCOL OVER ENCRYPTED CONNECTION ###

    def read_encrypted_header(self, s):
        return self._read_header(s)

    ################################################

    def read_options(self, s):
        return 20, self.read_download_id

    def read_download_id(self, s):
        if s != self.downloadid:
            return None
        return 20, self.read_peer_id

    def read_peer_id(self, s):
        if s != self.peerid:
            return None
        self.answer(True)
        return None

    def _write(self, message):
        if not self.closed:
            self.connection.write(message)

    def data_came_in(self, connection, s):
        self.read(s)

    def _write_buffer(self, s):
        self.buffer = s+self.buffer

    def _read(self, s):
        self.buffer += s
        while True:
            if self.closed:
                return
            # self.next_len = # of characters function expects
            # or 0 = all characters in the buffer
            # or -1 = wait for next read, then all characters in the buffer
            # not compatible w/ keepalives, switch out after all negotiation complete
            if self.next_len <= 0:
                m = self.buffer
                self.buffer = ''
            elif len(self.buffer) >= self.next_len:
                m = self.buffer[:self.next_len]
                self.buffer = self.buffer[self.next_len:]
            else:
                return
            try:
                x = self.next_func(m)
            except:
                if not self.closed:
                    self.answer(False)
                return
            if x is None:
                if not self.closed:
                    self.answer(False)
                return
            self.next_len, self.next_func = x
            if self.next_len < 0:  # already checked buffer
                return             # wait for additional data
            if self.bufferlen is not None:
                self._read2('')
                return

    def connection_lost(self, connection):
        if not self.closed:
            self.closed = True
            self.resultfunc(False, self.downloadid, self.peerid, self.ip, self.port)

    def connection_flushed(self, connection):
        pass
