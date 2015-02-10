import threading
import random
import httplib
import urllib
from urlparse import urlparse
from .CurrentRateMeasure import Measure
from BitTornado.bitfield import TrueBitfield
from BitTornado import product_name, version_short

EXPIRE_TIME = 60 * 60

VERSION = product_name + '/' + version_short


haveall = TrueBitfield()


class SingleDownload:
    def __init__(self, downloader, url):
        self.downloader = downloader
        self.baseurl = url
        try:
            (scheme, self.netloc, path, pars, query, _) = urlparse(url)
        except ValueError:
            self.downloader.errorfunc('cannot parse http seed address: ' + url)
            return
        if scheme != 'http':
            self.downloader.errorfunc('http seed url not http: ' + url)
            return
        try:
            self.connection = httplib.HTTPConnection(self.netloc)
        except Exception:
            self.downloader.errorfunc('cannot connect to http seed: ' + url)
            return
        self.seedurl = path
        if pars:
            self.seedurl += ';' + pars
        self.seedurl += '?'
        if query:
            self.seedurl += query + '&'
        self.seedurl += 'info_hash=' + urllib.quote(self.downloader.infohash)

        self.measure = Measure(downloader.max_rate_period)
        self.index = None
        self.url = ''
        self.requests = []
        self.request_size = 0
        self.endflag = False
        self.error = None
        self.retry_period = 30
        self._retry_period = None
        self.errorcount = 0
        self.goodseed = False
        self.active = False
        self.cancelled = False
        self.resched(random.randint(2, 10))

    def resched(self, len=None):
        if len is None:
            len = self.retry_period
        if self.errorcount > 3:
            len = len * (self.errorcount - 2)
        self.downloader.rawserver.add_task(self.download, len)

    def _want(self, index):
        if self.endflag:
            return self.downloader.storage.do_I_have_requests(index)
        else:
            return self.downloader.storage.is_unstarted(index)

    def download(self):
        self.cancelled = False
        if self.downloader.picker.am_I_complete():
            self.downloader.downloads.remove(self)
            return
        self.index = self.downloader.picker.next(haveall, self._want)
        if self.index is None and not self.endflag and \
                not self.downloader.peerdownloader.has_downloaders():
            self.endflag = True
            self.index = self.downloader.picker.next(haveall, self._want)
        if self.index is None:
            self.endflag = True
            self.resched()
        else:
            self.url = (self.seedurl + '&piece=' + str(self.index))
            self._get_requests()
            if self.request_size < \
                    self.downloader.storage._piecelen(self.index):
                self.url += '&ranges=' + self._request_ranges()
            rq = threading.Thread(target=self._request)
            rq.setDaemon(False)
            rq.start()
            self.active = True

    def _request(self):
        import encodings.ascii
        import encodings.punycode
        import encodings.idna

        self.error = None
        self.received_data = None
        try:
            self.connection.request('GET', self.url, None,
                                    {'User-Agent': VERSION})
            r = self.connection.getresponse()
            self.connection_status = r.status
            self.received_data = r.read()
        except Exception as e:
            self.error = 'error accessing http seed: ' + str(e)
            try:
                self.connection.close()
            except Exception:
                pass
            try:
                self.connection = httplib.HTTPConnection(self.netloc)
            except Exception:
                # will cause an exception and retry next cycle
                self.connection = None
        self.downloader.rawserver.add_task(self.request_finished)

    def request_finished(self):
        self.active = False
        if self.error is not None:
            if self.goodseed:
                self.downloader.errorfunc(self.error)
            self.errorcount += 1
        if self.received_data:
            self.errorcount = 0
            if not self._got_data():
                self.received_data = None
        if not self.received_data:
            self._release_requests()
            self.downloader.peerdownloader.piece_flunked(self.index)
        if self._retry_period:
            self.resched(self._retry_period)
            self._retry_period = None
            return
        self.resched()

    def _got_data(self):
        if self.connection_status == 503:   # seed is busy
            try:
                self.retry_period = max(int(self.received_data), 5)
            except ValueError:
                pass
            return False
        if self.connection_status != 200:
            self.errorcount += 1
            return False
        self._retry_period = 1
        if len(self.received_data) != self.request_size:
            if self.goodseed:
                self.downloader.errorfunc('corrupt data from http seed - '
                                          'redownloading')
            return False
        self.measure.update_rate(len(self.received_data))
        self.downloader.measurefunc(len(self.received_data))
        if self.cancelled:
            return False
        if not self._fulfill_requests():
            return False
        if not self.goodseed:
            self.goodseed = True
            self.downloader.seedsfound += 1
        if self.downloader.storage.do_I_have(self.index):
            self.downloader.picker.complete(self.index)
            self.downloader.peerdownloader.check_complete(self.index)
            self.downloader.gotpiecefunc(self.index)
        return True

    def _get_requests(self):
        self.requests = []
        self.request_size = 0L
        while self.downloader.storage.do_I_have_requests(self.index):
            r = self.downloader.storage.new_request(self.index)
            self.requests.append(r)
            self.request_size += r[1]
        self.requests.sort()

    def _fulfill_requests(self):
        start = 0L
        success = True
        while self.requests:
            begin, length = self.requests.pop(0)
            if not self.downloader.storage.piece_came_in(
                    self.index, begin,
                    self.received_data[start:start + length]):
                success = False
                break
            start += length
        return success

    def _release_requests(self):
        for begin, length in self.requests:
            self.downloader.storage.request_lost(self.index, begin, length)
        self.requests = []

    def _request_ranges(self):
        s = ''
        begin, length = self.requests[0]
        for begin1, length1 in self.requests[1:]:
            if begin + length == begin1:
                length += length1
                continue
            else:
                if s:
                    s += ','
                s += str(begin) + '-' + str(begin + length - 1)
                begin, length = begin1, length1
        if s:
            s += ','
        s += str(begin) + '-' + str(begin + length - 1)
        return s


class HTTPDownloader:
    def __init__(self, storage, picker, rawserver,
                 finflag, errorfunc, peerdownloader,
                 max_rate_period, infohash, measurefunc, gotpiecefunc):
        self.storage = storage
        self.picker = picker
        self.rawserver = rawserver
        self.finflag = finflag
        self.errorfunc = errorfunc
        self.peerdownloader = peerdownloader
        self.infohash = infohash
        self.max_rate_period = max_rate_period
        self.gotpiecefunc = gotpiecefunc
        self.measurefunc = measurefunc
        self.downloads = []
        self.seedsfound = 0

    def make_download(self, url):
        self.downloads.append(SingleDownload(self, url))
        return self.downloads[-1]

    def get_downloads(self):
        if self.finflag.isSet():
            return []
        return self.downloads

    def cancel_piece_download(self, pieces):
        for d in self.downloads:
            if d.active and d.index in pieces:
                d.cancelled = True
