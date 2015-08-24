import os
import time
import base64
import threading
import socket
import random
import hashlib
from BitTornado.Network.zurllib import urlopen
from BitTornado.Network.NetworkAddress import IPv4, IPv6
from BitTornado.Meta.Info import check_type
from BitTornado.Meta.bencode import bdecode
from BitTornado.Meta.TypedCollections import TypedDict, TypedList, QueryDict
from io import StringIO
from traceback import print_exc


class KeyDict(dict):
    def __init__(self):
        self.basekeydata = '{:d}{!r}tracker'.format(os.getpid(),
                                                    time.time()).encode()

    def __getitem__(self, tracker):
        if tracker not in self:
            self[tracker] = base64.urlsafe_b64encode(
                hashlib.sha1(self.basekeydata + tracker.encode()).digest()[-6:]
                ).decode()
        return super(KeyDict, self).__getitem__(tracker)

keys = KeyDict()


class Peer(TypedDict):
    iptype = IPv4
    typemap = {'ip': str, 'port': int, 'peer id': bytes}
    def __init__(self, arg):
        if isinstance(arg, bytes):
            nbytes = self.iptype.bits // 8
            arg = {'ip': self.iptype.from_bytes(arg[:nbytes], 'big'),
                   'port': int.from_bytes(arg[nbytes:], 'big')}
        TypedDict.__init__(self, arg)


class Peer6(Peer):
    iptype = IPv6


class Response(TypedDict):
    class Peers(TypedList):
        valtype = Peer

        def __init__(self, arg):
            if isinstance(arg, bytes):
                arg = [arg[i:i+6] for i in range(0, len(arg), 6)]
            TypedList.__init__(self, arg)

    class Peers6(TypedList):
        valtype = Peer6

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

    def __add__(self, newdict):
        x = self.__class__(self)
        x.update(newdict)
        return x


class fakeflag:
    def __init__(self, state=False):
        self.state = state

    def wait(self):
        pass

    def isSet(self):
        return self.state


def check_peers(message):
    """Validate a dictionary with a list of peers"""
    check_type(message, dict)
    if 'failure reason' in message:
        check_type(message['failure reason'], str)
        return

    peers = message.get('peers')
    if isinstance(peers, list):
        for peer in peers:
            check_type(peer, dict)
            check_type(peer.get('ip'), str)
            check_type(peer.get('port'), int, pred=lambda x: x <= 0)
            if 'peer id' in peer:
                check_type(peer.get('peer id'), bytes,
                           pred=lambda x: len(x) != 20)

    elif not isinstance(peers, bytes) or len(peers) % 6 != 0:
        print(peers.encode())
        raise ValueError('peers misencoded')

    check_type(message.get('interval', 1), int, pred=lambda x: x <= 0)
    check_type(message.get('min interval', 1), int,
               pred=lambda x: x <= 0)
    check_type(message.get('tracker id', ''), str)
    check_type(message.get('num peers', 0), int, pred=lambda x: x < 0)
    check_type(message.get('done peers', 0), int, pred=lambda x: x < 0)
    check_type(message.get('last', 0), int, pred=lambda x: x < 0)


class Rerequester:
    def __init__(self, port, myid, infohash, trackerlist, config,
                 sched, externalsched, errorfunc, excfunc, connect,
                 howmany, amount_left, up, down, upratefunc, downratefunc,
                 doneflag, unpauseflag=fakeflag(True),
                 force_rapid_update=False):

        self.sched = sched                  # RawServer.add_task
        self.externalsched = externalsched  # RawServer.add_task
        self.errorfunc = errorfunc          # f(str) -> None
        self.excfunc = excfunc              # f(str) -> None
        self.connect = connect              # Encoder.start_connections
        self.howmany = howmany              # Connector.how_many_connections
        self.amount_left = amount_left      # StorageWrapper.get_amount_left
        self.up = up                        # Measure.get_total
        self.down = down                    # Measure.get_total
        self.upratefunc = upratefunc        # Measure.get_rate
        self.downratefunc = downratefunc    # Measure.get_rate
        self.doneflag = doneflag            # threading.Event
        self.unpauseflag = unpauseflag      # threading.Event|fakeflag(True)
        self.force_rapid_update = force_rapid_update    # Bool

        self.ip = config.get('ip', '')          # str (external IP)
        self.minpeers = config['min_peers']
        self.maxpeers = config['max_initiate']
        self.interval = config['rerequest_interval']
        self.timeout = config['http_timeout']

        # Permute trackers within each tier
        self.trackerlist = [random.sample(tier, len(tier))
                            for tier in trackerlist]

        self.lastsuccessful = ''    # str (tracker URL)
        self.rejectedmessage = 'rejected by tracker - '

        self.url = RequestURL({'info_hash': infohash, 'peer_id': myid,
                               'port': port})
        if config.get('crypto_allowed'):
            self.url['supportcrypto'] = True
            if config.get('crypto_only'):
                self.url['requirecrypto'] = True
                if config.get('crypto_stealth'):
                    self.url['port'] = 0
                    self.url['cryptoport'] = port

        seed_id = config.get('dedicated_seed_id')
        if seed_id:
            self.url['seed_id'] = seed_id

        self.last = None
        self.trackerid = None
        self.announce_interval = 30 * 60
        self.last_failed = True
        self.never_succeeded = True
        self.errorcodes = {}
        self.lock = SuccessLock()
        self.special = None
        self.stopped = False

    def start(self):
        self.sched(self.c, self.interval / 2)
        self.d(0)

    def c(self):
        if self.stopped:
            return
        if not self.unpauseflag.isSet() and (
                self.howmany() < self.minpeers or self.force_rapid_update):
            self.announce(3, self._c)
        else:
            self._c()

    def _c(self):
        self.sched(self.c, self.interval)

    def d(self, event=3):
        if self.stopped:
            return
        if not self.unpauseflag.isSet():
            self._d()
            return
        self.announce(event, self._d)

    def _d(self):
        if self.never_succeeded:
            self.sched(self.d, 60)  # retry in 60 seconds
        elif self.force_rapid_update:
            return
        else:
            self.sched(self.d, self.announce_interval)

    def hit(self, event=3):
        if not self.unpauseflag.isSet() and (
                self.howmany() < self.minpeers or self.force_rapid_update):
            self.announce(event)

    def announce(self, event=3, callback=lambda: None, specialurl=None):

        if specialurl is not None:
            # don't add to statistics
            s = self.url + {'uploaded': 0, 'downloaded': 0, 'left': 1}
            if self.howmany() >= self.maxpeers:
                s['numwant'] = 0
            else:
                s['no_peer_id'] = True
                s['compact'] = True
            self.last_failed = True     # force true, so will display an error
            self.special = specialurl
            self.rerequest(s, callback)
            return

        s = self.url + {'uploaded': self.up(), 'downloaded': self.down(),
                        'left': self.amount_left()}
        if self.last is not None:
            s['last'] = self.last
        if self.trackerid is not None:
            s['trackerid'] = self.trackerid
        if self.howmany() >= self.maxpeers:
            s['numwant'] = 0
        else:
            s['no_peer_id'] = True
            s['compact'] = True
        if event != 3:
            s['event'] = ['started', 'completed', 'stopped'][event]
        if event == 2:
            self.stopped = True
        self.rerequest(s, callback)

    def snoop(self, npeers, callback=lambda: None):  # tracker call support
        self.rerequest(self.url + {'event': 'stopped', 'port': 0,
                                   'uploaded': 0, 'downloaded': 0, 'left': 1,
                                   'tracker': True, 'numwant': npeers},
                       callback)

    def rerequest(self, s, callback):
        # still waiting for prior cycle to complete??
        if not self.lock.isfinished():
            def retry(self=self, s=s, callback=callback):
                self.rerequest(s, callback)
            self.sched(retry, 5)         # retry in 5 seconds
            return
        self.lock.reset()
        rq = threading.Thread(target=self._rerequest, args=[s, callback])
        rq.setDaemon(False)
        rq.start()

    def _rerequest(self, s, callback):
        try:
            def fail(self=self, callback=callback):
                self._fail(callback)
            if self.ip:
                try:
                    s['ip'] = socket.gethostbyname(self.ip)
                except socket.error:
                    self.errorcodes['troublecode'] = 'unable to resolve: ' + \
                        self.ip
                    self.externalsched(fail)
            self.errorcodes = {}
            if self.special is None:
                for tier in self.trackerlist:
                    # Iterating is ok, as the loop is ended after modification
                    for i, tracker in enumerate(tier):
                        if self.rerequest_single(tracker, s, callback):
                            if not self.last_failed and i != 0:
                                tier.pop(i)
                                tier.insert(0, tracker)
                            return
            else:
                tracker = self.special
                self.special = None
                if self.rerequest_single(tracker, s, callback):
                    return
            # no success from any tracker
            self.externalsched(fail)
        except Exception:
            self.exception(callback)

    def _fail(self, callback):
        if self.upratefunc() < 100 and self.downratefunc() < 100 or \
                not self.amount_left():
            for code in ['rejected', 'bad_data', 'troublecode']:
                if code in self.errorcodes:
                    msg = self.errorcodes[code]
                    break
            else:
                msg = 'Problem connecting to tracker - unspecified error'
            self.errorfunc(msg)

        self.last_failed = True
        self.lock.give_up()
        self.externalsched(callback)

    def rerequest_single(self, tracker, querystring, callback):
        code = self.lock.set()
        querystring['key'] = keys[tracker]
        rq = threading.Thread(target=self._rerequest_single,
                              args=[tracker, str(querystring), code, callback])
        rq.setDaemon(False)
        rq.start()
        self.lock.wait()
        if self.lock.success:
            self.lastsuccessful = tracker
            self.last_failed = False
            self.never_succeeded = False
            return True
        if not self.last_failed and self.lastsuccessful == tracker:
            # if the last tracker hit was successful, and you've just tried the
            # tracker you'd contacted before, don't go any further, just fail
            # silently.
            self.last_failed = True
            self.externalsched(callback)
            self.lock.give_up()
            return True
        return False    # returns true if it wants rerequest() to exit

    def _rerequest_single(self, tracker, querystring, code, callback):
        try:
            closer = [None]

            def timedout(self=self, code=code, closer=closer):
                if self.lock.trip(code):
                    self.errorcodes['troublecode'] = 'Problem connecting to ' \
                        'tracker - timeout exceeded'
                    self.lock.unwait(code)
                try:
                    closer[0]()
                except Exception:
                    pass

            self.externalsched(timedout, self.timeout)

            err = None
            if '?' in tracker:
                url, qstring = tracker.split('?', 1)
                querystring = qstring + '&' + querystring
            else:
                url = tracker

            try:
                with urlopen(url + '?' + querystring) as h:
                    closer[0] = h.close
                    data = h.read()
            except (IOError, socket.error) as e:
                err = 'Problem connecting to tracker - ' + str(e)
            except Exception:
                err = 'Problem connecting to tracker'
            if err:
                if self.lock.trip(code):
                    self.errorcodes['troublecode'] = err
                    self.lock.unwait(code)
                return

            if data == '':
                if self.lock.trip(code):
                    self.errorcodes['troublecode'] = 'no data from tracker'
                    self.lock.unwait(code)
                return

            try:
                response = Response(bdecode(data, sloppy=1))
                check_peers(response)
            except ValueError as e:
                if self.lock.trip(code):
                    self.errorcodes['bad_data'] = 'bad data from tracker - ' \
                        + str(e)
                    self.lock.unwait(code)
                return

            if 'failure reason' in response:
                if self.lock.trip(code):
                    self.errorcodes['rejected'] = self.rejectedmessage + \
                        response['failure reason']
                    self.lock.unwait(code)
                return

            if self.lock.trip(code, True):     # success!
                self.lock.unwait(code)
            else:
                # attempt timed out, don't do a callback
                callback = lambda: None

            # even if the attempt timed out, go ahead and process data
            def add(self=self, response=response, callback=callback):
                self.postrequest(response, callback)
            self.externalsched(add)
        except Exception:
            self.exception(callback)

    def postrequest(self, r, callback):
        if 'warning message' in r:
            self.errorfunc('warning from tracker - ' + r['warning message'])
        self.announce_interval = r.get('interval', self.announce_interval)
        self.interval = r.get('min interval', self.interval)
        self.trackerid = r.get('tracker id', self.trackerid)
        self.last = r.get('last')
        p = r['peers']
        peers = []
        lenpeers = len(p)
        cflags = r.get('crypto_flags')
        if cflags is None or len(cflags) != lenpeers:
            cflags = [None] * lenpeers
        for i, x in enumerate(p):
            peers.append(((x['ip'].strip(), x['port']), x.get('peer id', 0),
                          cflags[i]))
        ps = len(peers) + self.howmany()
        if ps < self.maxpeers:
            if self.doneflag.isSet():
                if r.get('num peers', 1000) - r.get('done peers', 0) > \
                        ps * 1.2:
                    self.last = None
            else:
                if r.get('num peers', 1000) > ps * 1.2:
                    self.last = None
        if peers:
            random.shuffle(peers)
            self.connect(peers)
        callback()

    def exception(self, callback):
        data = StringIO()
        print_exc(file=data)

        def r(s=data.getvalue(), callback=callback):
            if self.excfunc:
                self.excfunc(s)
            else:
                print(s)
            callback()
        self.externalsched(r)


class SuccessLock(object):
    def __init__(self):
        self.lock = threading.Lock()
        self.pause = threading.Lock()
        self.code = 0
        self.success = False
        self.finished = True

    def reset(self):
        self.success = False
        self.finished = False

    def set(self):
        with self.lock:
            if not self.pause.locked():
                self.pause.acquire()
            self.first = True
            self.code += 1
        return self.code

    def trip(self, code, success=False):
        with self.lock:
            if code == self.code and not self.finished:
                ret = self.first
                self.first = False
                if success:
                    self.finished = True
                    self.success = True
                return ret
        return False

    def give_up(self):
        with self.lock:
            self.success = False
            self.finished = True

    def wait(self):
        self.pause.acquire()

    def unwait(self, code):
        if code == self.code and self.pause.locked():
            self.pause.release()

    def isfinished(self):
        with self.lock:
            return self.finished
