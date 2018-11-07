from .Extension import PeerExtensions
from ..Meta.bencode import bdecode
from ..Types import Bitfield
from BitTornado.clock import clock

DEBUG1 = False
DEBUG2 = False


# Message IDs
CHOKE = b'\x00'             # no payload
UNCHOKE = b'\x01'           # no payload
INTERESTED = b'\x02'        # no payload
NOT_INTERESTED = b'\x03'    # no payload
HAVE = b'\x04'              # index
BITFIELD = b'\x05'          # index, bitfield
REQUEST = b'\x06'           # index, begin, length
PIECE = b'\x07'             # index, begin, piece
CANCEL = b'\x08'            # index, begin, piece
DHT_PORT = b'\x09'          # port (2 bytes)
FAST_SUGGEST = b'\x0d'      # index
FAST_HAVE_ALL = b'\x0e'     # no payload
FAST_HAVE_NONE = b'\x0f'    # no payload
FAST_REJECT = b'\x10'       # index, begin, length
ALLOW_FAST = b'\x11'        # index
EXTENDED = b'\x14'          # msg_id, payload

# Extended Message IDs
EXT_HANDSHAKE = b'\x00'


class Connection(object):
    def __init__(self, connection, connecter, ccount):
        self.connection = connection    # Encrypter.Connection
        self.connecter = connecter      # Connecter
        self.ccount = ccount            # Connecter.ccount (at time of init)
        self.got_anything = False       # Bool (set once)
        self.next_upload = None         # Connection (linked-list)
        self.outqueue = []              # [bytes]
        self.partial_message = None     # bytes
        self.download = None            # Downloader.SingleDownload
        self.upload = None              # Uploader.Upload
        self.send_choke_queued = False  # Bool (togglable)
        self.just_unchoked = None       # None -> 0 <-> clock()
        self.supported_exts = {}

        # Pass-through functions
        self.get_id = connection.get_id
        self.get_readable_id = connection.get_readable_id
        self.is_locally_initiated = connection.is_locally_initiated
        self.is_encrypted = connection.is_encrypted

    def get_ip(self, real=False):
        return self.connection.get_ip(real)

    def close(self):
        if DEBUG1:
            print((self.ccount, 'connection closed'))
        self.connection.close()

    def send_interested(self):
        self._send_message(INTERESTED)

    def send_not_interested(self):
        self._send_message(NOT_INTERESTED)

    def send_choke(self):
        if self.partial_message:
            self.send_choke_queued = True
        else:
            self._send_message(CHOKE)
            self.upload.choke_sent()
            self.just_unchoked = 0

    def send_unchoke(self):
        if self.send_choke_queued:
            self.send_choke_queued = False
            if DEBUG1:
                print((self.ccount, 'CHOKE SUPPRESSED'))
        else:
            self._send_message(UNCHOKE)
            if (self.partial_message or self.just_unchoked is None or
                    not self.upload.interested or
                    self.download.active_requests):
                self.just_unchoked = 0
            else:
                self.just_unchoked = clock()

    def send_request(self, index, begin, length):
        self._send_message(REQUEST + index.to_bytes(4, 'big') +
                           begin.to_bytes(4, 'big') +
                           length.to_bytes(4, 'big'))
        if DEBUG1:
            print((self.ccount, 'sent request', index, begin, begin + length))

    def send_cancel(self, index, begin, length):
        self._send_message(CANCEL + index.to_bytes(4, 'big') +
                           begin.to_bytes(4, 'big') +
                           length.to_bytes(4, 'big'))
        if DEBUG1:
            print((self.ccount, 'sent cancel', index, begin, begin + length))

    def send_bitfield(self, bitfield):
        self._send_message(BITFIELD + bitfield)

    def send_have(self, index):
        self._send_message(HAVE + index.to_bytes(4, 'big'))

    def send_extended(self, ext_id, payload):
        self._send_message(EXTENDED + ext_id.to_bytes(1, 'big') + payload)

    def send_keepalive(self):
        self._send_message(b'')

    def _send_message(self, s):
        if DEBUG2:
            if s:
                print((self.ccount, 'SENDING MESSAGE', ord(s[0]), len(s)))
            else:
                print((self.ccount, 'SENDING MESSAGE', -1, 0))
        s = len(s).to_bytes(4, 'big') + s
        if self.partial_message:
            self.outqueue.append(s)
        else:
            self.connection.send_message_raw(s)

    def send_partial(self, nbytes):
        if self.connection.closed:
            return 0
        if self.partial_message is None:
            s = self.upload.get_upload_chunk()
            if s is None:
                return 0
            index, begin, piece = s
            self.partial_message = b''.join((
                (len(piece) + 9).to_bytes(4, 'big'), PIECE,
                index.to_bytes(4, 'big'), begin.to_bytes(4, 'big'),
                piece.tostring()))
            if DEBUG1:
                print((self.ccount, 'sending chunk', index, begin,
                       begin + len(piece)))

        if nbytes < len(self.partial_message):
            self.connection.send_message_raw(self.partial_message[:nbytes])
            self.partial_message = self.partial_message[nbytes:]
            return nbytes

        q = [self.partial_message]
        self.partial_message = None
        if self.send_choke_queued:
            self.send_choke_queued = False
            self.outqueue.append(b'\x00\x00\x00\x01' + CHOKE)
            self.upload.choke_sent()
            self.just_unchoked = 0
        q.extend(self.outqueue)
        self.outqueue = []
        q = b''.join(q)
        self.connection.send_message_raw(q)
        return len(q)

    def get_upload(self):
        return self.upload

    def get_download(self):
        return self.download

    def set_download(self, download):
        self.download = download

    def set_upload(self, upload):
        self.upload = upload

    def backlogged(self):
        return not self.connection.is_flushed()

    def got_request(self, piece_num, pos, length):
        self.upload.got_request(piece_num, pos, length)
        if self.just_unchoked:
            self.connecter.ratelimiter.ping(clock() - self.just_unchoked)
            self.just_unchoked = 0

    def got_extended(self, message):
        message_id = message[:1]
        if message_id == EXT_HANDSHAKE:
            payload = bdecode(message[1:])
            supported_exts = payload['m']
            self.supported_exts.update((k, v)
                                       for k, v in supported_exts.items()
                                       if k in SUPPORTED_EXTS)
        else:
            pass


class Connecter(object):
    def __init__(self, make_upload, downloader, choker, numpieces, totalup,
                 config, ratelimiter, sched=None):
        self.make_upload = make_upload  # BT1Download._makeupload
        self.downloader = downloader    # Downloader
        self.choker = choker            # Choker
        self.numpieces = numpieces      # len(BT1Download.pieces) - From info
        self.totalup = totalup          # Measure(max_rate_period,
                                        #         upload_rate_fudge)
        self.config = config            # {flag: value}
        self.ratelimiter = ratelimiter  # RateLimiter
        self.sched = sched              # RawServer.add_task
        self.rate_capped = False
        self.connections = {}           # {Encrypter.Connection: Connection}
        self.external_connection_made = 0
        self.ccount = 0

    def how_many_connections(self):
        return len(self.connections)

    def connection_made(self, connection):
        self.ccount += 1
        c = Connection(connection, self, self.ccount)
        if DEBUG2:
            print((c.ccount, 'connection made'))
        self.connections[connection] = c
        c.set_upload(self.make_upload(c, self.ratelimiter, self.totalup))
        c.set_download(self.downloader.make_download(c))
        self.choker.connection_made(c)
        return c

    def connection_lost(self, connection):
        c = self.connections[connection]
        if DEBUG2:
            print((c.ccount, 'connection closed'))
        del self.connections[connection]
        if c.download:
            c.download.disconnected()
        self.choker.connection_lost(c)

    def connection_flushed(self, connection):
        conn = self.connections[connection]
        if conn.next_upload is None and (conn.partial_message is not None or
                                         len(conn.upload.buffer) > 0):
            self.ratelimiter.queue(conn)

    def got_piece(self, i):
        for co in self.connections.values():
            co.send_have(i)

    def got_message(self, connection, message):
        c = self.connections[connection]
        t = message[:1]
        if DEBUG2:
            print((c.ccount, 'message received', ord(t)))
        if t == BITFIELD and c.got_anything:
            if DEBUG2:
                print((c.ccount, 'misplaced bitfield'))
            connection.close()
            return
        c.got_anything = True
        if (t in [CHOKE, UNCHOKE, INTERESTED, NOT_INTERESTED] and
                len(message) != 1):
            if DEBUG2:
                print((c.ccount, 'bad message length'))
            connection.close()
            return
        if t == CHOKE:
            c.download.got_choke()
        elif t == UNCHOKE:
            c.download.got_unchoke()
        elif t == INTERESTED:
            if not c.download.have.complete:
                c.upload.got_interested()
        elif t == NOT_INTERESTED:
            c.upload.got_not_interested()
        elif t == HAVE:
            if len(message) != 5:
                if DEBUG2:
                    print((c.ccount, 'bad message length'))
                connection.close()
                return
            i = int.from_bytes(message[1:], 'big')
            if i >= self.numpieces:
                if DEBUG2:
                    print((c.ccount, 'bad piece number'))
                connection.close()
                return
            if c.download.got_have(i):
                c.upload.got_not_interested()
        elif t == BITFIELD:
            try:
                b = Bitfield(self.numpieces, message[1:])
            except ValueError:
                if DEBUG2:
                    print((c.ccount, 'bad bitfield'))
                connection.close()
                return
            if c.download.got_have_bitfield(b):
                c.upload.got_not_interested()
        elif t == REQUEST:
            if len(message) != 13:
                if DEBUG2:
                    print((c.ccount, 'bad message length'))
                connection.close()
                return
            piece_num = int.from_bytes(message[1:5], 'big')
            if piece_num >= self.numpieces:
                if DEBUG2:
                    print((c.ccount, 'bad piece number'))
                connection.close()
                return
            c.got_request(piece_num, int.from_bytes(message[5:9], 'big'),
                          int.from_bytes(message[9:], 'big'))
        elif t == CANCEL:
            if len(message) != 13:
                if DEBUG2:
                    print((c.ccount, 'bad message length'))
                connection.close()
                return
            i = int.from_bytes(message[1:5], 'big')
            if i >= self.numpieces:
                if DEBUG2:
                    print((c.ccount, 'bad piece number'))
                connection.close()
                return
            c.upload.got_cancel(i, int.from_bytes(message[5:9], 'big'),
                                int.from_bytes(message[9:], 'big'))
        elif t == PIECE:
            if len(message) <= 9:
                if DEBUG2:
                    print((c.ccount, 'bad message length'))
                connection.close()
                return
            i = int.from_bytes(message[1:5], 'big')
            if i >= self.numpieces:
                if DEBUG2:
                    print((c.ccount, 'bad piece number'))
                connection.close()
                return
            if c.download.got_piece(i, int.from_bytes(message[5:9], 'big'),
                                    message[9:]):
                self.got_piece(i)
        elif t == EXTENDED:
            c.got_extended(message)
        else:
            connection.close()
