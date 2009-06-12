# Written by John Hoffman
# see LICENSE.txt for license information

from cStringIO import StringIO
#from RawServer import RawServer
from BTcrypto import Crypto
try:
    True
except:
    True = 1
    False = 0

from BT1.Encrypter import protocol_name

default_task_id = []

class SingleRawServer:
    def __init__(self, info_hash, multihandler, doneflag, protocol):
        self.info_hash = info_hash
        self.doneflag = doneflag
        self.protocol = protocol
        self.multihandler = multihandler
        self.rawserver = multihandler.rawserver
        self.finished = False
        self.running = False
        self.handler = None
        self.taskqueue = []

    def shutdown(self):
        if not self.finished:
            self.multihandler.shutdown_torrent(self.info_hash)

    def _shutdown(self):
        if not self.finished:
            self.finished = True
            self.running = False
            self.rawserver.kill_tasks(self.info_hash)
            if self.handler:
                self.handler.close_all()

    def _external_connection_made(self, c, options, already_read,
                                  encrypted = None ):
        if self.running:
            c.set_handler(self.handler)
            self.handler.externally_handshaked_connection_made(
                c, options, already_read, encrypted = encrypted)

    ### RawServer functions ###

    def add_task(self, func, delay=0, id = default_task_id):
        if id is default_task_id:
            id = self.info_hash
        if not self.finished:
            self.rawserver.add_task(func, delay, id)

#    def bind(self, port, bind = '', reuse = False):
#        pass    # not handled here
        
    def start_connection(self, dns, handler = None):
        if not handler:
            handler = self.handler
        c = self.rawserver.start_connection(dns, handler)
        return c

#    def listen_forever(self, handler):
#        pass    # don't call with this
    
    def start_listening(self, handler):
        self.handler = handler
        self.running = True
        return self.shutdown    # obviously, doesn't listen forever

    def is_finished(self):
        return self.finished

    def get_exception_flag(self):
        return self.rawserver.get_exception_flag()


class NewSocketHandler:     # hand a new socket off where it belongs
    def __init__(self, multihandler, connection):
        self.multihandler = multihandler
        self.connection = connection
        connection.set_handler(self)
        self.closed = False
        self.buffer = ''
        self.complete = False
        self.read = self._read
        self.write = connection.write
        self.next_len, self.next_func = 1+len(protocol_name), self.read_header
        self.multihandler.rawserver.add_task(self._auto_close, 30)

    def _auto_close(self):
        if not self.complete:
            self.close()
        
    def close(self):
        if not self.closed:
            self.connection.close()
            self.closed = True

    # copied from Encrypter and modified
    
    def _read_header(self, s):
        if s == chr(len(protocol_name))+protocol_name:
            self.protocol = protocol_name
            return 8, self.read_options
        return None

    def read_header(self, s):
        if self._read_header(s):
            if self.multihandler.config['crypto_only']:
                return None
            return 8, self.read_options
        if not self.multihandler.config['crypto_allowed']:
            return None
        self.encrypted = True
        self.encrypter = Crypto(False)
        self._write_buffer(s)
        return self.encrypter.keylength, self.read_crypto_header

    def read_crypto_header(self, s):
        self.encrypter.received_key(s)
        self.write(self.encrypter.pubkey+self.encrypter.padding())
        self._max_search = 520
        return 0, self.read_crypto_block3a

    def _search_for_pattern(self, s, pat):
        p = s.find(pat)
        if p < 0:
            self._max_search -= len(s)+1-len(pat)
            if self._max_search < 0:
                self.close()
                return False
            self._write_buffer(s[1-len(pat):])
            return False
        self._write_buffer(s[p+len(pat):])
        return True

    def read_crypto_block3a(self, s):
        if not self._search_for_pattern(s,self.encrypter.block3a):
            return -1, self.read_crypto_block3a     # wait for more data
        return 20, self.read_crypto_block3b

    def read_crypto_block3b(self, s):
        for k in self.multihandler.singlerawservers.keys():
            if self.encrypter.test_skey(s,k):
                self.multihandler.singlerawservers[k]._external_connection_made(
                        self.connection, None, self.buffer,
                        encrypted = self.encrypter )
                return True
        return None

    def read_options(self, s):
        self.options = s
        return 20, self.read_download_id

    def read_download_id(self, s):
        if self.multihandler.singlerawservers.has_key(s):
            if self.multihandler.singlerawservers[s].protocol == self.protocol:
                self.multihandler.singlerawservers[s]._external_connection_made(
                        self.connection, self.options, self.buffer)
                return True
        return None


    def read_dead(self, s):
        return None

    def data_came_in(self, garbage, s):
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
            if x == True:
                self.complete = True
                return
            self.next_len, self.next_func = x
            if self.next_len < 0:  # already checked buffer
                return             # wait for additional data


    def connection_flushed(self, ss):
        pass

    def connection_lost(self, ss):
        self.closed = True

class MultiHandler:
    def __init__(self, rawserver, doneflag, config):
        self.rawserver = rawserver
        self.masterdoneflag = doneflag
        self.config = config
        self.singlerawservers = {}
        self.connections = {}
        self.taskqueues = {}

    def newRawServer(self, info_hash, doneflag, protocol=protocol_name):
        new = SingleRawServer(info_hash, self, doneflag, protocol)
        self.singlerawservers[info_hash] = new
        return new

    def shutdown_torrent(self, info_hash):
        self.singlerawservers[info_hash]._shutdown()
        del self.singlerawservers[info_hash]

    def listen_forever(self):
        self.rawserver.listen_forever(self)
        for srs in self.singlerawservers.values():
            srs.finished = True
            srs.running = False
            srs.doneflag.set()
        
    ### RawServer handler functions ###
    # be wary of name collisions

    def external_connection_made(self, ss):
        NewSocketHandler(self, ss)
