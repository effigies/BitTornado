# Written by Bram Cohen
# see LICENSE.txt for license information

from cStringIO import StringIO
from binascii import b2a_hex
from socket import error as socketerror
from urllib import quote
from traceback import print_exc
from BitTornado.BTcrypto import Crypto

try:
    True
except:
    True = 1
    False = 0
    bool = lambda x: not not x

DEBUG = False

MAX_INCOMPLETE = 8

protocol_name = 'BitTorrent protocol'
option_pattern = chr(0)*8

def toint(s):
    return long(b2a_hex(s), 16)

def tobinary16(i):
    return chr((i >> 8) & 0xFF) + chr(i & 0xFF)

hexchars = '0123456789ABCDEF'
hexmap = []
for i in xrange(256):
    hexmap.append(hexchars[(i&0xF0)/16]+hexchars[i&0x0F])

def tohex(s):
    r = []
    for c in s:
        r.append(hexmap[ord(c)])
    return ''.join(r)

def make_readable(s):
    if not s:
        return ''
    if quote(s).find('%') >= 0:
        return tohex(s)
    return '"'+s+'"'
   

class IncompleteCounter:
    def __init__(self):
        self.c = 0
    def increment(self):
        self.c += 1
    def decrement(self):
        self.c -= 1
    def toomany(self):
        return self.c >= MAX_INCOMPLETE
    
incompletecounter = IncompleteCounter()


# header, options, download id, my id, [length, message]

class Connection:
    def __init__(self, Encoder, connection, id,
                 ext_handshake=False, encrypted = None, options = None):
        self.Encoder = Encoder
        self.connection = connection
        self.connecter = Encoder.connecter
        self.id = id
        self.locally_initiated = (id != None)
        self.readable_id = make_readable(id)
        self.complete = False
        self.keepalive = lambda: None
        self.closed = False
        self.buffer = ''
        self.bufferlen = None
        self.log = None
        self.read = self._read
        self.write = self._write
        self.cryptmode = 0
        self.encrypter = None
        if self.locally_initiated:
            incompletecounter.increment()
            if encrypted:
                self.encrypted = True
                self.encrypter = Crypto(True)
                self.write(self.encrypter.pubkey+self.encrypter.padding())
            else:
                self.encrypted = False
                self.write(chr(len(protocol_name)) + protocol_name + 
                    option_pattern + self.Encoder.download_id )
            self.next_len, self.next_func = 1+len(protocol_name), self.read_header
        elif ext_handshake:
            self.Encoder.connecter.external_connection_made += 1
            if encrypted:   # passed an already running encrypter
                self.encrypter = encrypted
                self.encrypted = True
                self._start_crypto()
                self.next_len, self.next_func = 14, self.read_crypto_block3c
            else:
                self.encrypted = False
                self.options = options
                self.write(self.Encoder.my_id)
                self.next_len, self.next_func = 20, self.read_peer_id
        else:
            self.encrypted = None       # don't know yet
            self.next_len, self.next_func = 1+len(protocol_name), self.read_header
        self.Encoder.raw_server.add_task(self._auto_close, 30)


    def _log_start(self):   # only called with DEBUG = True
        self.log = open('peerlog.'+self.get_ip()+'.txt','a')
        self.log.write('connected - ')
        if self.locally_initiated:
            self.log.write('outgoing\n')
        else:
            self.log.write('incoming\n')
        self._logwritefunc = self.write
        self.write = self._log_write

    def _log_write(self, s):
        self.log.write('w:'+b2a_hex(s)+'\n')
        self._logwritefunc(s)
        

    def get_ip(self, real=False):
        return self.connection.get_ip(real)

    def get_id(self):
        return self.id

    def get_readable_id(self):
        return self.readable_id

    def is_locally_initiated(self):
        return self.locally_initiated

    def is_encrypted(self):
        return bool(self.encrypted)

    def is_flushed(self):
        return self.connection.is_flushed()

    def _read_header(self, s):
        if s == chr(len(protocol_name))+protocol_name:
            return 8, self.read_options
        return None

    def read_header(self, s):
        if self._read_header(s):
            if self.encrypted or self.Encoder.config['crypto_stealth']:
                return None
            return 8, self.read_options
        if self.locally_initiated and not self.encrypted:
            return None
        elif not self.Encoder.config['crypto_allowed']:
            return None
        if not self.encrypted:
            self.encrypted = True
            self.encrypter = Crypto(self.locally_initiated)
        self._write_buffer(s)
        return self.encrypter.keylength, self.read_crypto_header

    ################## ENCRYPTION SUPPORT ######################

    def _start_crypto(self):
        self.encrypter.setrawaccess(self._read,self._write)
        self.write = self.encrypter.write
        self.read = self.encrypter.read
        if self.buffer:
            self.buffer = self.encrypter.decrypt(self.buffer)

    def _end_crypto(self):
        self.read = self._read
        self.write = self._write
        self.encrypter = None

    def read_crypto_header(self, s):
        self.encrypter.received_key(s)
        self.encrypter.set_skey(self.Encoder.download_id)
        if self.locally_initiated:
            if self.Encoder.config['crypto_only']:
                cryptmode = '\x00\x00\x00\x02'    # full stream encryption
            else:
                cryptmode = '\x00\x00\x00\x03'    # header or full stream
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
        self.write(self.encrypter.pubkey+self.encrypter.padding())
        self._max_search = 520
        return 0, self.read_crypto_block3a

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

    ### INCOMING CONNECTION ###

    def read_crypto_block3a(self, s):
        if not self._search_for_pattern(s,self.encrypter.block3a):
            return -1, self.read_crypto_block3a     # wait for more data
        return len(self.encrypter.block3b), self.read_crypto_block3b

    def read_crypto_block3b(self, s):
        if s != self.encrypter.block3b:
            return None
        self.Encoder.connecter.external_connection_made += 1
        self._start_crypto()
        return 14, self.read_crypto_block3c

    def read_crypto_block3c(self, s):
        if s[:8] != ('\x00'*8):             # check VC
            return None
        self.cryptmode = toint(s[8:12]) % 4
        if self.cryptmode == 0:
            return None                     # no encryption selected
        if ( self.cryptmode == 1            # only header encryption
             and self.Encoder.config['crypto_only'] ):
            return None
        padlen = (ord(s[12])<<8)+ord(s[13])
        if padlen > 512:
            return None
        return padlen+2, self.read_crypto_pad3

    def read_crypto_pad3(self, s):
        s = s[-2:]
        ialen = (ord(s[0])<<8)+ord(s[1])
        if ialen > 65535:
            return None
        if self.cryptmode == 1:
            cryptmode = '\x00\x00\x00\x01'    # header only encryption
        else:
            cryptmode = '\x00\x00\x00\x02'    # full stream encryption
        padd = self.encrypter.padding()
        self.write( ('\x00'*8)            # VC
                  + cryptmode             # encryption mode
                  + tobinary16(len(padd))
                  + padd )                # PadD
        if ialen:
            return ialen, self.read_crypto_ia
        return self.read_crypto_block3done()

    def read_crypto_ia(self, s):
        if DEBUG:
            self._log_start()
            self.log.write('r:'+b2a_hex(s)+'(ia)\n')
            if self.buffer:
                self.log.write('r:'+b2a_hex(self.buffer)+'(buffer)\n')
        return self.read_crypto_block3done(s)

    def read_crypto_block3done(self, ia=''):
        if DEBUG:
            if not self.log:
                self._log_start()
        if self.cryptmode == 1:     # only handshake encryption
            assert not self.buffer  # oops; check for exceptions to this
            self._end_crypto()
        if ia:
            self._write_buffer(ia)
        return 1+len(protocol_name), self.read_encrypted_header

    ### OUTGOING CONNECTION ###

    def read_crypto_block4a(self, s):
        if not self._search_for_pattern(s,self.encrypter.VC_pattern()):
            return -1, self.read_crypto_block4a     # wait for more data
        self._start_crypto()
        return 6, self.read_crypto_block4b

    def read_crypto_block4b(self, s):
        self.cryptmode = toint(s[:4]) % 4
        if self.cryptmode == 1:             # only header encryption
            if self.Encoder.config['crypto_only']:
                return None
        elif self.cryptmode != 2:
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
        self.options = s
        return 20, self.read_download_id

    def read_download_id(self, s):
        if ( s != self.Encoder.download_id
             or not self.Encoder.check_ip(ip=self.get_ip()) ):
            return None
        if not self.locally_initiated:
            if not self.encrypted:
                self.Encoder.connecter.external_connection_made += 1
            self.write(chr(len(protocol_name)) + protocol_name + 
                option_pattern + self.Encoder.download_id + self.Encoder.my_id)
        return 20, self.read_peer_id

    def read_peer_id(self, s):
        if not self.encrypted and self.Encoder.config['crypto_only']:
            return None     # allows older trackers to ping,
                            # but won't proceed w/ connections
        if not self.id:
            self.id = s
            self.readable_id = make_readable(s)
        else:
            if s != self.id:
                return None
        self.complete = self.Encoder.got_id(self)
        if not self.complete:
            return None
        if self.locally_initiated:
            self.write(self.Encoder.my_id)
            incompletecounter.decrement()
        self._switch_to_read2()
        c = self.Encoder.connecter.connection_made(self)
        self.keepalive = c.send_keepalive
        return 4, self.read_len

    def read_len(self, s):
        l = toint(s)
        if l > self.Encoder.max_len:
            return None
        return l, self.read_message

    def read_message(self, s):
        if s != '':
            self.connecter.got_message(self, s)
        return 4, self.read_len

    def read_dead(self, s):
        return None

    def _auto_close(self):
        if not self.complete:
            self.close()

    def close(self):
        if not self.closed:
            self.connection.close()
            self.sever()

    def sever(self):
        if self.log:
            self.log.write('closed\n')
            self.log.close()
        self.closed = True
        del self.Encoder.connections[self.connection]
        if self.complete:
            self.connecter.connection_lost(self)
        elif self.locally_initiated:
            incompletecounter.decrement()

    def send_message_raw(self, message):
        self.write(message)

    def _write(self, message):
        if not self.closed:
            self.connection.write(message)

    def data_came_in(self, connection, s):
        self.read(s)

    def _write_buffer(self, s):
        self.buffer = s+self.buffer

    def _read(self, s):
        if self.log:
            self.log.write('r:'+b2a_hex(s)+'\n')
        self.Encoder.measurefunc(len(s))
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
                self.next_len, self.next_func = 1, self.read_dead
                raise
            if x is None:
                self.close()
                return
            self.next_len, self.next_func = x
            if self.next_len < 0:  # already checked buffer
                return             # wait for additional data
            if self.bufferlen is not None:
                self._read2('')
                return

    def _switch_to_read2(self):
        self._write_buffer = None
        if self.encrypter:
            self.encrypter.setrawaccess(self._read2,self._write)
        else:
            self.read = self._read2
        self.bufferlen = len(self.buffer)
        self.buffer = [self.buffer]

    def _read2(self, s):    # more efficient, requires buffer['',''] & bufferlen
        if self.log:
            self.log.write('r:'+b2a_hex(s)+'\n')
        self.Encoder.measurefunc(len(s))
        while True:
            if self.closed:
                return
            p = self.next_len-self.bufferlen
            if self.next_len == 0:
                m = ''
            elif s:
                if p > len(s):
                    self.buffer.append(s)
                    self.bufferlen += len(s)
                    return
                self.bufferlen = len(s)-p
                self.buffer.append(s[:p])
                m = ''.join(self.buffer)
                if p == len(s):
                    self.buffer = []
                else:
                    self.buffer=[s[p:]]
                s = ''
            elif p <= 0:
                # assert len(self.buffer) == 1
                s = self.buffer[0]
                self.bufferlen = len(s)-self.next_len
                m = s[:self.next_len]
                if p == 0:
                    self.buffer = []
                else:
                    self.buffer = [s[self.next_len:]]
                s = ''
            else:
                return
            try:
                x = self.next_func(m)
            except:
                self.next_len, self.next_func = 1, self.read_dead
                raise
            if x is None:
                self.close()
                return
            self.next_len, self.next_func = x
            if self.next_len < 0:  # already checked buffer
                return             # wait for additional data
            

    def connection_flushed(self, connection):
        if self.complete:
            self.connecter.connection_flushed(self)

    def connection_lost(self, connection):
        if self.Encoder.connections.has_key(connection):
            self.sever()


class _dummy_banlist:
    def includes(self, x):
        return False

class Encoder:
    def __init__(self, connecter, raw_server, my_id, max_len,
            schedulefunc, keepalive_delay, download_id, 
            measurefunc, config, bans=_dummy_banlist() ):
        self.raw_server = raw_server
        self.connecter = connecter
        self.my_id = my_id
        self.max_len = max_len
        self.schedulefunc = schedulefunc
        self.keepalive_delay = keepalive_delay
        self.download_id = download_id
        self.measurefunc = measurefunc
        self.config = config
        self.connections = {}
        self.banned = {}
        self.external_bans = bans
        self.to_connect = []
        self.paused = False
        if self.config['max_connections'] == 0:
            self.max_connections = 2 ** 30
        else:
            self.max_connections = self.config['max_connections']
        schedulefunc(self.send_keepalives, keepalive_delay)

    def send_keepalives(self):
        self.schedulefunc(self.send_keepalives, self.keepalive_delay)
        if self.paused:
            return
        for c in self.connections.values():
            c.keepalive()

    def start_connections(self, list):
        if not self.to_connect:
            self.raw_server.add_task(self._start_connection_from_queue)
        self.to_connect = list

    def _start_connection_from_queue(self):
        if self.connecter.external_connection_made:
            max_initiate = self.config['max_initiate']
        else:
            max_initiate = int(self.config['max_initiate']*1.5)
        cons = len(self.connections)
        if cons >= self.max_connections or cons >= max_initiate:
            delay = 60
        elif self.paused or incompletecounter.toomany():
            delay = 1
        else:
            delay = 0
            dns, id, encrypted = self.to_connect.pop(0)
            self.start_connection(dns, id, encrypted)
        if self.to_connect:
            self.raw_server.add_task(self._start_connection_from_queue, delay)

    def start_connection(self, dns, id, encrypted = None):
        if ( self.paused
             or len(self.connections) >= self.max_connections
             or id == self.my_id
             or not self.check_ip(ip=dns[0]) ):
            return True
        if self.config['crypto_only']:
            if encrypted is None or encrypted:  # fails on encrypted = 0
                encrypted = True
            else:
                return True
        for v in self.connections.values():
            if v is None:
                continue
            if id and v.id == id:
                return True
            ip = v.get_ip(True)
            if self.config['security'] and ip != 'unknown' and ip == dns[0]:
                return True
        try:
            c = self.raw_server.start_connection(dns)
            con = Connection(self, c, id, encrypted = encrypted)
            self.connections[c] = con
            c.set_handler(con)
        except socketerror:
            return False
        return True

    def _start_connection(self, dns, id, encrypted = None):
        def foo(self=self, dns=dns, id=id, encrypted=encrypted):
            self.start_connection(dns, id, encrypted)
        self.schedulefunc(foo, 0)

    def check_ip(self, connection=None, ip=None):
        if not ip:
            ip = connection.get_ip(True)
        if self.config['security'] and self.banned.has_key(ip):
            return False
        if self.external_bans.includes(ip):
            return False
        return True

    def got_id(self, connection):
        if connection.id == self.my_id:
            self.connecter.external_connection_made -= 1
            return False
        ip = connection.get_ip(True)
        for v in self.connections.values():
            if connection is not v:
                if connection.id == v.id:
                    if ip == v.get_ip(True):
                        v.close()
                    else:
                        return False
                if self.config['security'] and ip != 'unknown' and ip == v.get_ip(True):
                    v.close()
        return True

    def external_connection_made(self, connection):
        if self.paused or len(self.connections) >= self.max_connections:
            connection.close()
            return False
        con = Connection(self, connection, None)
        self.connections[connection] = con
        connection.set_handler(con)
        return True

    def externally_handshaked_connection_made(self, connection, options,
                                              already_read, encrypted = None):
        if ( self.paused
             or len(self.connections) >= self.max_connections
             or not self.check_ip(connection=connection) ):
            connection.close()
            return False
        con = Connection(self, connection, None,
                ext_handshake = True, encrypted = encrypted, options = options)
        self.connections[connection] = con
        connection.set_handler(con)
        if already_read:
            con.data_came_in(con, already_read)
        return True

    def close_all(self):
        for c in self.connections.values():
            c.close()
        self.connections = {}

    def ban(self, ip):
        self.banned[ip] = 1

    def pause(self, flag):
        self.paused = flag
