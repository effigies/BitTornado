"""Manage connections to trackers for announcing torrents

Announcers are HTTP(S)/UDP objects which maintain connections to specific
tracker URLS and the small amount of client state needed to communicate
with trackers, and provide an announce() method for updating trackers.
"""
import random
import urllib
import base64
import threading
from BitTornado.Meta.bencode import bdecode
from BitTornado.Meta.TypedCollections import TypedDict, TypedList, QueryDict
from BitTornado.Network.NetworkAddress import IPv4, IPv6
from BitTornado.Network.Stream import SharedStream


class _Peer(TypedDict):
    """IPv4 peer descriptor"""
    iptype = IPv4
    typemap = {'ip': str, 'port': int, 'peer id': bytes}

    def __init__(self, arg):
        """Accept bytes or dict representations"""
        if isinstance(arg, bytes):
            nbytes = self.iptype.bits // 8
            arg = {'ip': self.iptype.from_bytes(arg[:nbytes], 'big'),
                   'port': int.from_bytes(arg[nbytes:], 'big')}
        TypedDict.__init__(self, arg)


class _Peer6(_Peer):
    """IPv6 peer descriptor"""
    iptype = IPv6


class Response(TypedDict):
    """Parse and validate tracker responses"""
    class Peers(TypedList):
        valtype = _Peer

        def __init__(self, arg):
            if isinstance(arg, bytes):
                arg = [arg[i:i+6] for i in range(0, len(arg), 6)]
            TypedList.__init__(self, arg)

    class Peers6(TypedList):
        valtype = _Peer6

        def __init__(self, arg):
            assert isinstance(arg, bytes)
            arg = [arg[i:i+18] for i in range(0, len(arg), 18)]
            TypedList.__init__(self, arg)

    typemap = {'failure reason': str, 'warning message': str, 'interval': int,
               'min interval': int, 'tracker id': bytes, 'complete': int,
               'incomplete': int, 'crypto_flags': bytes, 'peers': Peers,
               'peers6': Peers6}
    valmap = {str: str.encode}


class RequestURL(QueryDict):
    typemap = {'info_hash': bytes, 'peer_id': bytes, 'port': int,
               'supportcrypto': bool, 'requirecrypto': bool, 'cryptoport': int,
               'seed_id': bytes, 'check_seeded': bool, 'uploaded': int,
               'downloaded': int, 'left': int, 'numwant': int,
               'no_peer_id': bool, 'compact': bool, 'last': int,
               'trackerid': bytes, 'event': str, 'tracker': bool,
               'key': str}


class Announcer(object):
    """Announcers for tracker URLs that can be used for several downloads, if
    the same URL is used.

    Subclasses are based on the tracker type (HTTP(S)/UDP), and may depend
    on the full tracker URL, the client port number and a 4-byte random
    key.

    Subclasses must implement the announce() function. To prevent multiple
    initializations, subclass __init__ methods should acquire a lock and
    mark themselves initialized.
    """
    announcers = {}
    announcer_lock = threading.Lock()
    initialized = False

    def __new__(cls, tracker_url, port, *args, **kwargs):
        """Return the Announcer associated with the tracker URL, creating a
        new one, if needed.

        Client port is made available to Announcer objects, but is assumed
        not to vary within a program, so calling with the same URL and two
        different ports will return the same object."""

        # Use Announcer() to allow scheme to decide on subclass
        if cls is Announcer:
            scheme = urllib.parse.urlsplit(tracker_url)[0]
            return cls.subclasses[scheme](tracker_url, port, *args, **kwargs)

        with cls.announcer_lock:
            # Assume port will not change within single Python instance
            # If this changes, change key to (tracker_url, port)
            if tracker_url not in cls.announcers:
                announcer = super(Announcer, cls).__new__(cls)
                # Keys allow trackers to recognize clients with IP changes
                announcer.key = random.randint(0, 0xffffffff).to_bytes(4,
                                                                       'big')
                announcer.stream = SharedStream(tracker_url)
                cls.announcers[tracker_url] = announcer
        return cls.announcers[tracker_url]

    def announce(self, infohash, peer_id, event=0, downloaded=0, uploaded=0,
                 left=0, num_want=-1, snoop=False):
        """Send an announce request

        Arguments:
            infohash    bytes[20]   SHA1 hash of bencoded Info dictionary
            peer_id     bytes       unique peer ID
            event       int         Code indicating purpose of request
                                        0 (empty/update statistics)
                                        1 (download started)
                                        2 (download completed)
                                        3 (download stoped)
            downloaded  int         number of bytes downloaded
            uploaded    int         number of bytes uploaded
            left        int         number of bytes left to download
            num_want    int         number of peers to request (optional)
            snoop       bool        query tracker without affecting stats

        Returns:
            {'interval':        int,    number of seconds to wait to
                                        reannounce
             'complete':        int,    number of seeders
             'incomplete':      int,    number of leechers
             'peers': [{'ip':   str,    Peer IP address
                        'port': int}]}  Peer port number

        If called with infohash and peer_id, a 'stopped' event is sent, and
        most trackers will respond with an empty list of peers.

        Subclasses may return more complete return values.
        """
        raise NotImplementedError


class UDPAnnouncer(Announcer):
    """Announce peer status over UDP

    This object maintains tracker-specific client state.

    Implements
        BEP 15      UDP tracker protocol
        BEP 41      URL data extension to UDP protocol
    """
    class_lock = threading.Lock()

    def __init__(self, tracker_url, port, ip=0, *args, **kwargs):
        """Retrieve the announcer object associated with tracker_url

        On the first call, initializes object according to parameters. On
        later calls, does nothing. Parameters may be set on existing
        objects with set_options().
        """
        with self.class_lock:
            if self.initialized:
                return

            super(UDPAnnouncer, self).__init__()

            _, _, path, query, _ = urllib.parse.urlsplit(tracker_url)
            self.urldata = b''
            if path or query:
                urldata = b''.join((path.encode(), query.encode()))
                while len(urldata) > 256:
                    self.urldata += b'\x02\xff' + urldata[:256]
                    urldata = urldata[256:]
                self.urldata += bytes([2, len(urldata)]) + urldata + b'\x00'

            self.set_options(port, ip)
            self.initialized = True

    def set_options(self, port, ip=0):
        """Set client port/IP to send to tracker.

        Called during __init__(), so only use this if changing parameters
        DURING program execution."""
        self.port = port
        self.ip = IPv4(ip)

    def announce(self, infohash, peer_id, event=0, downloaded=0, uploaded=0,
                 left=0, num_want=-1, snoop=False):
        """Send an announce request

        Arguments:
            infohash    bytes[20]   SHA1 hash of bencoded Info dictionary
            peer_id     bytes       unique peer ID
            event       int         Code indicating purpose of request
                                        0 (empty/update statistics)
                                        1 (download started)
                                        2 (download completed)
                                        3 (download stoped)
            downloaded  int         number of bytes downloaded
            uploaded    int         number of bytes uploaded
            left        int         number of bytes left to download
            num_want    int         number of peers to request (optional)
            snoop       bool        query tracker without affecting stats

        Returns:
            {'interval':        int,    number of seconds to wait to reannounce
             'complete':        int,    number of seeders
             'incomplete':      int,    number of leechers
             'peers': [{'ip':   str,    Peer IP address
                        'port': int}]}  Peer port number

        If called with infohash and peer_id, a 'stopped' event is sent, and
        most trackers will respond with an empty list of peers.
        """
        data = b''.join((infohash, peer_id, downloaded.to_bytes(8, 'big'),
                         left.to_bytes(8, 'big'), uploaded.to_bytes(8, 'big'),
                         event.to_bytes(4, 'big'), self.ip.to_bytes(4, 'big'),
                         self.key, num_want.to_bytes(4, 'big', signed=True),
                         self.port.to_bytes(2, 'big'), self.urldata))
        rawdata = self.stream.request(data)
        return Response(interval=int.from_bytes(rawdata[:4], 'big'),
                        incomplete=int.from_bytes(rawdata[4:8], 'big'),
                        complete=int.from_bytes(rawdata[8:12], 'big'),
                        peers=rawdata[12:])
    announce.__doc__ = Announcer.announce.__doc__


class HTTPAnnouncer(Announcer):
    """Announce peer status over HTTP(S)

    This object maintains tracker-specific client state and handles HTTP
    redirects. New attempts to use the original tracker URL will instead
    use the redirected URL. This permits transparent HTTP->HTTPS upgrades
    without revealing client information more than once, as well as
    reducing the effective latency of announces.

    Implements
        BEP  3      Original request format for trackers
        BEP  7      IPv6 response entry ``peers6''
        BEP 23      Compact peer lists

    Non-BEP standards
        MSE         Announces supportcrypto, requirecrypto, cryptoport
        no_peer_id  Request tracker to exclude peer IDs from responses

    Additional otherwise undocumented BitTornado extensions implemented:
        seed_id     Dedicated seed IDs may be sent to trackers
    """
    class_lock = threading.Lock()
    trackerid = None
    events = ['empty', 'started', 'completed', 'stopped']
    _redirects = 0
    MAX_REDIRECTS = 10

    def __init__(self, tracker_url, port, ip=0, seed_id=None,
                 supportcrypto=True, requirecrypto=False, cryptostealth=False,
                 no_peer_id=True, compact=True):
        """Retrieve the announcer object associated with tracker_url

        On the first call, initializes object according to parameters. On
        later calls, does nothing. Parameters may be set on existing
        objects with set_options().
        """
        with self.class_lock:
            if self.initialized:
                return

            super(HTTPAnnouncer, self).__init__()
            self.redirect_lock = threading.Lock()

            _, _, path, query, _ = urllib.parse.urlsplit(tracker_url)
            # a[:bool(b)] == (a if b else '')
            self.basequery = path + '?' + query + '&'[:bool(query)]
            self.set_options(port, ip, seed_id, supportcrypto, requirecrypto,
                             cryptostealth, no_peer_id, compact)
            self.initialized = True

    def set_options(self, port, ip=0, seed_id=None, supportcrypto=True,
                    requirecrypto=False, cryptostealth=False, no_peer_id=True,
                    compact=True):
        """Prepare query parameters according to state variables. Crypto
        parameters will be set to the *least secure* logically consistent
        configuration.

        Called during __init__(), so only use this if changing parameters
        DURING program execution."""
        # Enforce logical consistency
        requirecrypto &= supportcrypto
        cryptostealth &= requirecrypto

        # Port is required; IP if specified; seed_id if specified
        self.client = [('ip', str(IPv4(ip)))][:bool(ip)] + \
            [('port', port if not cryptostealth else 0)] + \
            [('seed_id', seed_id)][:bool(seed_id)]
        # Compact precludes peer_id, so don't bother with no_peer_id
        self.peer_options = [('compact', int(compact))] + \
            [('no_peer_id', 1)][:(no_peer_id and not compact)]

        self.crypto_options = [('supportcrypto', int(supportcrypto)),
                               ('requirecrypto', int(requirecrypto))] + \
            [('cryptoport', port)][:cryptostealth]

    def _redirect(self, new_url, old_query):
        """Update announce URL from HTTP redirect"""
        if self._redirects >= self.MAX_REDIRECTS:
            raise IOError(('http error', 500,
                           'Internal Server Error: Redirect Recursion'))
        scheme, netloc, path, query, frag = urllib.parse.urlsplit(new_url)

        # If we got our own query string back, remove it
        oq_dict = urllib.parse.parse_qs(old_query)
        new_query = urllib.parse.urlencode(
            (key, val) for key, val in urllib.parse.parse_qsl(query)
            if val != oq_dict.get(key, ''))
        tracker_url = urllib.parse.urlunsplit((scheme, netloc, path,
                                               new_query, frag))

        with self.announcer_lock:
            # It's possible to have the same redirect happen
            if tracker_url in self.announcers and \
                    self.announcers[tracker_url] == self:
                return
            self._redirects += 1
            self.announcers[tracker_url] = self

            self.stream = SharedStream(tracker_url)
            self.basequery = path + '?' + new_query + '&'[:bool(new_query)]

    def announce(self, infohash, peer_id, event=0, downloaded=0, uploaded=0,
                 left=0, num_want=-1, snoop=False):
        """Send an announce request

        Arguments:
            infohash    bytes[20]   SHA1 hash of bencoded Info dictionary
            peer_id     bytes       unique peer ID
            event       int         Code indicating purpose of request
                                        0 (empty/update statistics)
                                        1 (download started)
                                        2 (download completed)
                                        3 (download stoped)
            downloaded  int         number of bytes downloaded
            uploaded    int         number of bytes uploaded
            left        int         number of bytes left to download
            num_want    int         number of peers to request (optional)
            snoop       bool        query tracker without affecting stats

        Returns:
            {'interval':        int,    number of seconds to wait to
                                        reannounce
             'complete':        int,    number of seeders
             'incomplete':      int,    number of leechers
             'peers': [{'ip':   str,    Peer IPv4 address
                        'port': int}]   Peer port number
             'peers6': [{'ip':  str,    Peer IPv6 address
                         'port':int}]   Peer port number
             'crypto_flags':    bytes,  crypto capabilities of each peer
                                            b'\\x00' Prefers plaintext
                                            b'\\x01' Requires encryption
             'min interval':    int,    strict reannounce interval
             'tracker id':      bytes,  unique tracker ID
             'warning message': str}    message from tracker

            OR

            {'failure reason':  str}    error message from tracker

        If called with infohash and peer_id, a 'stopped' event is sent, and
        most trackers will respond with an empty list of peers.
        """
        if snoop:
            options = [('info_hash', infohash), ('peer_id', peer_id),
                       ('event', 'stopped'), ('port', 0), ('compact', True),
                       ('uploaded', 0), ('downloaded', 0), ('left', 1),
                       ('tracker', True), ('numwant', num_want)]
        else:
            # a[:bool(b)] == (a if b else '')
            basic = [('info_hash', infohash), ('peer_id', peer_id)] + \
                [('event', self.events[event])][:bool(event)]
            stats = [('uploaded', uploaded), ('downloaded', downloaded),
                     ('left', left)]
            trackercomm = [('key', base64.urlsafe_b64encode(self.key))] + \
                [('trackerid', self.trackerid)][:bool(self.trackerid)] + \
                [('numwant', num_want)][:(num_want >= 0)]
            options = basic + self.client + self.peer_options + stats + \
                self.crypto_options + trackercomm

        # In Python 3.5, we can switch to the urlencode line. In the meantime,
        # keep using RequestURL
        query = str(RequestURL(options))
        #query = urllib.parse.urlencode(options, quote_via=urllib.parse.quote)
        response, raw = self.send_query(query)

        if response.status == 200:
            ret = Response(bdecode(raw))
            if 'trackerid' in ret:
                self.trackerid = ret['trackerid']
            return ret

        try:
            return Response(bdecode(raw))
        except ValueError:
            raise IOError(('http error', response.status, response.reason))

    def send_query(self, query):
        """Send query, redirecting as needed"""
        with self.redirect_lock:
            response, raw = self.stream.request(self.basequery + query)
            while response.status in (301, 302):
                self._redirect(raw, query)
                response, raw = self.stream.request(self.basequery + query)

        return response, raw

    def forward_query(self, query, password=None):
        """Send a pre-formed query, optionally appending password

        Do not attempt to check errors or parse a response."""
        if password is not None:
            query += '&password=' + password

        try:
            self.send_query(query)
        except IOError:
            pass

Announcer.subclasses = {'http': HTTPAnnouncer, 'https': HTTPAnnouncer,
                        'udp': UDPAnnouncer}


def urls_to_announcers(trackerlist, *args, **kwargs):
    """Map URLs to appropriate Announcers"""
    return [[Announcer(url, *args, **kwargs) for url in tier]
            for tier in trackerlist]
