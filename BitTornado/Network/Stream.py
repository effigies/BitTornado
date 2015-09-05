"""Manage transport-layer connections to trackers

SharedStreams are HTTP/HTTPS/UDP streams which allow multiple requests to
be sent over a single connection and reconnect when connections are lost.

These objects trade asynchronicity and speed for reduced connection
overhead. Announcing is a relatively infrequent activity for a client so
reducing demand on trackers is the greater concern. For single-download
clients, there should be no blocking at all.
"""
import io
import gzip
import socket
import random
import urllib
import threading
from http.client import HTTPConnection, HTTPSConnection, HTTPException
from BitTornado.clock import clock
from BitTornado import product_name, version_short

VERSION = product_name + '/' + version_short


def _url_sig(url):
    """Extract (scheme, host, port) from URL"""
    scheme, netloc, *_ = urllib.parse.urlsplit(url)
    host, *portstr = netloc.split(':', 1)
    defaults = {'http': 80, 'https': 443}
    port = int(portstr[0]) if portstr else \
        defaults[scheme] if scheme in defaults else None
    if port is None:
        return None

    return (scheme, host, port)


class SharedStream(object):
    """Share connections to trackers across objects.

    Subclasses are based on the relevant protocol, and may only depend on
    the protocol scheme, host and port of the connection. Subclasses must
    implement a request() method that sends data and returns the response,
    if any. To ensure synchronicity, request() must acquire and release
    self.lock.

    SharedStream(url) selects the appropriate subclasses.
    """
    shares = {}
    share_lock = threading.Lock()
    scheme = sig = lock = None

    def __new__(cls, tracker_url):
        """Return the SharedStream associated with the protocol, host and port
        in tracker_url, creating a new one if needed."""
        sig = _url_sig(tracker_url)
        if sig is None:
            return None

        if cls is SharedStream:
            return cls.subclasses[sig[0]](tracker_url)

        assert sig[0] == cls.scheme
        with cls.share_lock:
            if sig not in cls.shares:
                cls.shares[sig] = super(SharedStream, cls).__new__(cls)
                cls.shares[sig].sig = sig
                cls.shares[sig].lock = threading.Lock()
        return cls.shares[sig]

    def request(self, msg):
        """Send an announce request to the given host and return the response.
        """
        raise NotImplementedError


class ShareUDP(SharedStream):
    """Shared UDP stream allows multiple objects to make requests during the
    60-second window the tracker permits
    """
    scheme = 'udp'

    # BEP 15 Definitions <http://bittorrent.org/beps/bep_0015.html>
    INITIAL = 0x41727101980.to_bytes(8, 'big')
    CONNECT = b'\x00\x00\x00\x00'
    ANNOUNCE = b'\x00\x00\x00\x01'
    SCRAPE = b'\x00\x00\x00\x02'
    ERROR = b'\x00\x00\x00\x03'

    ERROR_ALT = b'\x03\x00\x00\x00'  # Little-endian error code seen in wild
    response_time = clock() - 60     # Start with expired session
    sock = tx_id = cnxn_id = None

    def _connect(self):
        """Send a connect request, and record the connection ID

        Return True/False on success/failure
        """
        # No cost to using a new UDP socket
        self.sock = socket.socket(type=socket.SOCK_DGRAM)
        self.sock.settimeout(15)
        self.sock.connect(self.sig[1:])
        self.tx_id = random.randint(0, 0xffffffff).to_bytes(4, 'big')
        self.sock.send(self.INITIAL + self.CONNECT + self.tx_id)
        response = self.sock.recv(1024)

        if len(response) < 8:
            return False

        if response[:4] in (self.ERROR, self.ERROR_ALT) and \
                response[4:8] == self.tx_id:
            raise IOError(response[8:-1].decode())
        elif response[:8] == self.CONNECT + self.tx_id:
            self.cnxn_id = response[8:16]
            self.response_time = clock()
            return True
        else:
            return False

    def request(self, msg):
        """Make an announce request to a UDP tracker

        Requests will have connection ID, announce code, and transaction ID
        prepended. Response headers are validated and stripped, and the
        remaining bytestring returned.

        None will be returned on a timed-out or malformed response. If an
        error message is received, an exception will be raised with its
        contents.
        """
        with self.lock:
            if clock() >= self.response_time + 60:
                if not self._connect():
                    return None

            packet = b''.join((self.cnxn_id, self.ANNOUNCE, self.tx_id, msg))
            self.sock.send(packet)
            response = self.sock.recv(2048)

            if len(response) < 8:
                return None

            if response[:4] in (self.ERROR, self.ERROR_ALT) and \
                    response[4:8] == self.tx_id:
                if response.endswith(b'\x00'):
                    response = response[:-1]
                raise IOError(response[8:].decode())
            elif response[:8] == self.ANNOUNCE + self.tx_id:
                return response[8:]
            else:
                return None


class ShareHTTP(SharedStream):
    """Shared HTTP stream allows multiple objects to make requests on a single
    TCP connection. When the stream is closed, it will be reopened by the
    first thread to try.

    This object does not perform redirects.
    """
    scheme = 'http'
    connection = None

    def _connect(self):
        """Establish HTTP Connection"""
        self.connection = HTTPConnection(*self.sig[1:], timeout=30)

    def request(self, msg):
        """Make an announce request to an HTTP tracker

        Argument should be the contents of a GET request, e.g. if the URL
        to be sent is <http://tracker.com:3669/announce?infohash=...>, then

        response, rawdata = stream.request('/announce?infohash=...')

        This function requests compressed responses and performs any
        decompression necessary.

        A tuple containing the HTTPResponse as its first value is returned;
        the second value depends on the response status code. For a 200
        status, a (uncompressed) bytestring is returned. For a (301, 302)
        status, the new location is returned as a string. On other errors,
        the raw response bytestring is returned, which may or may not
        contain a bencoded dictionary with an error message from the
        tracker.

        On errors, the connection is closed. It may be reopened, but this
        function makes no attempt to run multiple times.
        """
        with self.lock:
            if self.connection is None:
                self._connect()

            try:
                self.connection.request('GET', msg,
                                        headers={'User-Agent': VERSION,
                                                 'Accept-Encoding': 'gzip'})
                response = self.connection.getresponse()
                status = response.status
                if status == 200:
                    data = response.read()
                    if response.getheader('Content-Encoding',
                                          '').find('gzip') >= 0:
                        data = gzip.GzipFile(fileobj=io.BytesIO(data)).read()
                    return response, data
                elif status in (301, 302):
                    return response, response.getheader('Location')

                self.connection.close()
                self.connection = None
                return response, response.read()
            except (IOError, HTTPException):
                self.connection = None
                raise

SharedStream.subclasses = {'udp': ShareUDP, 'http': ShareHTTP}

try:
    import ssl

    class ShareHTTPS(ShareHTTP):
        """Shared HTTPS stream allows multiple objects to make requests on a
        single TLS connection. When the stream is closed, it will be reopened
        by the first thread to try.

        This object does not perform redirects.
        """
        scheme = 'https'

        SSLCONTEXT = ssl.create_default_context()
        # Disable insecure protocol versions
        SSLCONTEXT.options |= ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3
        # Prefer forward-secret, GCM-mode AES, then forward-secret, non-GCM
        # SHA1 and non-forward-secret accepted as last resorts
        _preferred = 'EECDH+AESGCM:EDH+AESGCM:EECDH:EDH:+SHA:ALL'
        # Restrict the use of obsolete/broken ciphers
        _restrict = '!MEDIUM:!LOW:!EXP:!DSS:!aNULL:!eNULL:!RC4:!3DES:!SEED' \
            ':!MD5'
        SSLCONTEXT.set_ciphers(_preferred + ':' + _restrict)

        def _connect(self):
            """Establish HTTPS Connection"""
            self.connection = HTTPSConnection(*self.sig[1:], timeout=30,
                                              context=self.SSLCONTEXT)

    SharedStream.subclasses['https'] = ShareHTTPS
except ImportError:
    pass


def geturl(url, max_redirects=10):
    """Simple URL fetcher"""
    for _ in range(max_redirects):
        try:
            stream = SharedStream(url)  # HTTP(S)
        except KeyError:
            raise IOError(('url error', 'unknown url type', url))
        query = urllib.parse.urlunsplit(('', '') +
                                        urllib.parse.urlsplit(url)[2:])
        response, raw = stream.request(query)
        if response.status == 200:
            return raw
        elif response.status in (301, 302):
            url = raw
        else:
            raise IOError(('http error', response.status, raw))
