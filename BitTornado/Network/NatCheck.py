import socket
from .BTcrypto import Crypto, CRYPTO_OK, padding
from .Encrypter import protocol_name, option_pattern

CHECK_PEER_ID_ENCRYPTED = True

# header, reserved, download id, my id, [length, message]


class NatCheck(object):
    def __init__(self, resultfunc, downloadid, peerid, ip, port, rawserver,
                 encrypted=False):
        self.resultfunc = resultfunc
        self.downloadid = downloadid
        self.peerid = peerid
        self.ip = ip
        self.port = port
        self.encrypted = encrypted
        self.closed = False
        self.buffer = b''
        self.read = self._read
        self.write = self._write
        try:
            self.connection = rawserver.start_connection((ip, port), self)
            if encrypted:
                self._dc = not(CRYPTO_OK and CHECK_PEER_ID_ENCRYPTED)
                self.encrypter = Crypto(True, disable_crypto=self._dc)
                self.write(self.encrypter.padded_pubkey())
            else:
                self.encrypter = None
                self.write(protocol_name + bytes(8) + downloadid)
        except socket.error:
            self.answer(False)
        except IOError:
            self.answer(False)
        self.next_len = len(protocol_name)
        self.next_func = self.read_header

    def answer(self, result):
        self.closed = True
        try:
            self.connection.close()
        except AttributeError:
            pass
        self.resultfunc(result, self.downloadid, self.peerid, self.ip,
                        self.port)

    def _read_header(self, s):
        if s == protocol_name:
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
        self.encrypter.setrawaccess(self._read, self._write)
        self.write = self.encrypter.write
        self.read = self.encrypter.read
        if self.buffer:
            self.buffer = self.encrypter.decrypt(self.buffer)

    def read_crypto_header(self, s):
        self.encrypter.received_key(s)
        self.encrypter.set_skey(self.downloadid)
        cryptmode = b'\x00\x00\x00\x02'    # full stream encryption
        padc = padding()
        self.write(self.encrypter.block3a +
                   self.encrypter.block3b +
                   self.encrypter.encrypt(
                       bytes(8)                       # VC
                       + cryptmode                    # acceptable crypto modes
                       + len(padc).to_bytes(2, 'big')
                       + padc                         # PadC
                       + bytes(2)))                   # no initial payload data
        self._max_search = 520
        return 1, self.read_crypto_block4a

    def _search_for_pattern(self, s, pat):
        p = s.find(pat)
        if p < 0:
            if len(s) >= len(pat):
                self._max_search -= len(s) + 1 - len(pat)
            if self._max_search < 0:
                self.close()
                return False
            self._write_buffer(s[1 - len(pat):])
            return False
        self._write_buffer(s[p + len(pat):])
        return True

    ### OUTGOING CONNECTION ###

    def read_crypto_block4a(self, s):
        if not self._search_for_pattern(s, self.encrypter.VC_pattern()):
            return -1, self.read_crypto_block4a     # wait for more data
        if self._dc:                        # can't or won't go any further
            self.answer(True)
            return None
        self._start_crypto()
        return 6, self.read_crypto_block4b

    def read_crypto_block4b(self, s):
        self.cryptmode = int.from_bytes(s[:4], 'big') % 4
        if self.cryptmode != 2:
            return None                     # unknown encryption
        padlen = int.from_bytes(s[4:6], 2)
        if padlen > 512:
            return None
        if padlen:
            return padlen, self.read_crypto_pad4
        return self.read_crypto_block4done()

    def read_crypto_pad4(self, s):
        # discard data
        return self.read_crypto_block4done()

    def read_crypto_block4done(self):
        if self.cryptmode == 1:     # only handshake encryption
            if not self.buffer:  # oops; check for exceptions to this
                return None
            self._end_crypto()
        self.write(protocol_name + option_pattern + self.Encoder.download_id)
        return len(protocol_name), self.read_encrypted_header

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
        self.buffer = s + self.buffer

    def _read(self, s):
        self.buffer += s
        while True:
            if self.closed:
                return
            # self.next_len = # of characters function expects
            # or 0 = all characters in the buffer
            # or -1 = wait for next read, then all characters in the buffer
            # not compatible w/ keepalives, switch out after all negotiation
            # complete
            if self.next_len <= 0:
                m = self.buffer
                self.buffer = b''
            elif len(self.buffer) >= self.next_len:
                m = self.buffer[:self.next_len]
                self.buffer = self.buffer[self.next_len:]
            else:
                return
            try:
                x = self.next_func(m)
            except Exception:
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
                self._read2(b'')
                return

    def connection_lost(self, connection):
        if not self.closed:
            self.closed = True
            self.resultfunc(False, self.downloadid, self.peerid, self.ip,
                            self.port)

    def connection_flushed(self, connection):
        pass
