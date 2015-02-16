import gzip
import socket
import httplib
import urlparse
from StringIO import StringIO
from BitTornado.Meta.bencode import bdecode
from BitTornado import product_name, version_short

VERSION = product_name + '/' + version_short
MAX_REDIRECTS = 10


class btHTTPcon(httplib.HTTPConnection):
    """Add automatic connection timeout to HTTPConnection"""
    def connect(self):
        httplib.HTTPConnection.connect(self)
        try:
            self.sock.settimeout(30)
        except socket.error:
            pass


class btHTTPScon(httplib.HTTPSConnection):
    """Add automatic connection timeout to HTTPSConnection"""
    def connect(self):
        httplib.HTTPSConnection.connect(self)
        try:
            self.sock.settimeout(30)
        except socket.error:
            pass


class urlopen:
    def __init__(self, url):
        self.tries = 0
        self._open(url.strip())
        self.error_return = None

    def _open(self, url):
        self.tries += 1
        if self.tries > MAX_REDIRECTS:
            raise IOError(('http error', 500,
                          "Internal Server Error: Redirect Recursion"))
        (scheme, netloc, path, pars, query, _) = urlparse.urlparse(url)
        if scheme != 'http' and scheme != 'https':
            raise IOError(('url error', 'unknown url type', scheme, url))
        url = path
        if pars:
            url += ';' + pars
        if query:
            url += '?' + query
#        if fragment:
        try:
            if scheme == 'http':
                self.connection = btHTTPcon(netloc)
            else:
                self.connection = btHTTPScon(netloc)
            self.connection.request('GET', url, None,
                                    {'User-Agent': VERSION,
                                     'Accept-Encoding': 'gzip'})
            self.response = self.connection.getresponse()
        except httplib.HTTPException as e:
            raise IOError(('http error', str(e)))
        status = self.response.status
        if status in (301, 302):
            try:
                self.connection.close()
            except socket.error:
                pass
            self._open(self.response.getheader('Location'))
            return
        if status != 200:
            try:
                data = self._read()
                d = bdecode(data)
                if 'failure reason' in d:
                    self.error_return = data
                    return
            except (IOError, ValueError):
                pass
            raise IOError(('http error', status, self.response.reason))

    def read(self):
        if self.error_return:
            return self.error_return
        return self._read()

    def _read(self):
        data = self.response.read()
        if self.response.getheader('Content-Encoding', '').find('gzip') >= 0:
            try:
                compressed = StringIO(data)
                f = gzip.GzipFile(fileobj=compressed)
                data = f.read()
            except IOError:
                raise IOError(('http error', 'got corrupt response'))
        return data

    def close(self):
        self.connection.close()
