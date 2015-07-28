import io
import gzip
import socket
import urllib
from http.client import HTTPConnection, HTTPSConnection, HTTPException
from BitTornado.Meta.bencode import bdecode
from BitTornado import product_name, version_short
try:
    import ssl
    SSLCONTEXT = ssl.create_default_context()
    SSLCONTEXT.options |= ssl.OP_NO_SSLv2
    SSLCONTEXT.options |= ssl.OP_NO_SSLv3
    # Prefer forward-secret, GCM-mode AES, then forward-secret, non-GCM
    # SHA1 and non-forward-secret accepted as last resorts
    _preferred = 'EECDH+AESGCM:EDH+AESGCM:EECDH:EDH:+SHA:ALL'
    # Restrict the use of obsolete/broken ciphers
    _restrict = '!MEDIUM:!LOW:!EXP:!DSS:!aNULL:!eNULL:!RC4:!3DES:!SEED:!MD5'
    SSLCONTEXT.set_ciphers(_preferred + ':' + _restrict)
except ImportError:
    pass

VERSION = product_name + '/' + version_short
MAX_REDIRECTS = 10


class urlopen(object):
    """HTTP(S) urlopen that handles compressed connections

    Errors that respond with bencoded data can be read

    Raises IOError on other errors
    """
    conntypes = {'http': HTTPConnection, 'https': HTTPSConnection}

    def __init__(self, url):
        self.tries = 0
        self.error_return = None
        self.connection = None
        self.url = None
        self._open(url.strip())

    def _setconn(self, url):
        scheme, host, path, params, query, _ = urllib.parse.urlparse(url)
        if scheme not in self.conntypes:
            raise IOError(('url error', 'unknown url type', scheme, url))

        if self.connection is not None and not (
                isinstance(self.connection, self.conntypes[scheme]) and
                host == self.connection.host):
            try:
                self.connection.close()
            except socket.error:
                pass
            self.connection = None

        if self.connection is None:
            if scheme == 'http':
                self.connection = HTTPConnection(host, timeout=30)
            else:
                self.connection = HTTPSConnection(host, timeout=30,
                                                  context=SSLCONTEXT)

        # a[:len(b)] == (a if b else '')
        self.url = path + ';'[:len(params)] + params + '?'[:len(query)] + query

    def _open(self, url):
        try:
            self._setconn(url)
        except HTTPException as e:
            raise IOError(('http error', str(e)))

        for _ in range(MAX_REDIRECTS):
            try:
                self.connection.request('GET', self.url, None,
                                        {'User-Agent': VERSION,
                                         'Accept-Encoding': 'gzip'})
                self.response = self.connection.getresponse()
                if self.response.status == 200:  # Success
                    return
                if self.response.status in (301, 302):  # Redirect
                    self._setconn(self.response.getheader('Location'))
                    continue
            except HTTPException as e:
                raise IOError(('http error', str(e)))

            # Handle bencoded errors
            try:
                data = self._read()
                d = bdecode(data)
                if 'failure reason' in d:
                    self.error_return = data
                    return
            except (IOError, ValueError):
                pass

            # General HTTP error
            raise IOError(('http error', self.response.status,
                           self.response.reason))
        else:
            raise IOError(('http error', 500,
                           "Internal Server Error: Redirect Recursion"))

    def read(self):
        """Read response"""
        if self.error_return:
            return self.error_return
        return self._read()

    def _read(self):
        data = self.response.read()
        if self.response.getheader('Content-Encoding', '').find('gzip') >= 0:
            try:
                data = gzip.GzipFile(fileobj=io.BytesIO(data)).read()
            except IOError:
                raise IOError(('http error', 'got corrupt response'))
        return data

    def close(self):
        """Close connection

        Always succeeds"""
        if self.connection is not None:
            try:
                self.connection.close()
            except socket.error:
                pass

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        self.close()
