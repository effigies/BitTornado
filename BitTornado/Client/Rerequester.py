import threading
import socket
import random
from BitTornado.Meta.Info import check_type
from io import StringIO
from traceback import print_exc


class fakeflag:
    def __init__(self, state=False):
        self.state = state

    def wait(self):
        pass

    def is_set(self):
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
        raise ValueError('peers misencoded')

    check_type(message.get('interval', 1), int, pred=lambda x: x <= 0)
    check_type(message.get('min interval', 1), int,
               pred=lambda x: x <= 0)
    check_type(message.get('tracker id', ''), str)
    check_type(message.get('num peers', 0), int, pred=lambda x: x < 0)
    check_type(message.get('done peers', 0), int, pred=lambda x: x < 0)
    check_type(message.get('last', 0), int, pred=lambda x: x < 0)


class Rerequester:
    def __init__(self, myid, infohash, announcers, config,
                 sched, errorfunc, excfunc, connect,
                 howmany, amount_left, up, down, upratefunc, downratefunc,
                 doneflag, unpauseflag=fakeflag(True),
                 force_rapid_update=False):

        self.myid = myid
        self.infohash = infohash
        self.sched = sched                  # RawServer.add_task
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

        self.minpeers = config['min_peers']
        self.maxpeers = config['max_initiate']
        self.interval = config['rerequest_interval']
        self.timeout = config['http_timeout']

        # Permute trackers within each tier
        self.announcers = [random.sample(tier, len(tier))
                           for tier in announcers]

        self.lastsuccessful = None    # str (tracker URL)
        self.rejectedmessage = 'rejected by tracker - '

        self.last = None
        self.trackerid = None
        self.announce_interval = 30 * 60
        self.last_failed = True
        self.never_succeeded = True
        self.errorcodes = {}
        self.lock = SuccessLock()
        self.stopped = False

    def start(self):
        self.sched(self.c, self.interval / 2)
        self.d(0)

    def c(self):
        if self.stopped:
            return
        if not self.unpauseflag.is_set() and (
                self.howmany() < self.minpeers or self.force_rapid_update):
            self.announce(0, lambda: self.sched(self.c, self.interval))
        else:
            self.sched(self.c, self.interval)

    def d(self, event=0):
        if self.stopped:
            return
        if not self.unpauseflag.is_set():
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

    def hit(self, event=0):
        if not self.unpauseflag.is_set() and (
                self.howmany() < self.minpeers or self.force_rapid_update):
            self.announce(event)

    def announce(self, event=0, callback=lambda: None):
        announce_kwargs = {'uploaded': self.up(), 'downloaded': self.down(),
                           'left': self.amount_left(), 'event': event}
        if self.howmany() >= self.maxpeers:
            announce_kwargs['num_want'] = 0
        if event == 3:
            self.stopped = True
        self.rerequest(announce_kwargs, callback)

    def snoop(self, npeers, callback=lambda: None):  # tracker call support
        self.rerequest({'snoop': True, 'num_want': npeers}, callback)

    def rerequest(self, announce_kwargs, callback):
        # still waiting for prior cycle to complete??
        if not self.lock.isfinished():
            def retry(self=self, s=announce_kwargs, callback=callback):
                self.rerequest(s, callback)
            self.sched(retry, 5)         # retry in 5 seconds
            return
        self.lock.reset()
        rq = threading.Thread(target=self._rerequest,
                              args=[announce_kwargs, callback])
        rq.setDaemon(False)
        rq.start()

    def _rerequest(self, announce_kwargs, callback):
        try:
            def fail(self=self, callback=callback):
                self._fail(callback)
            self.errorcodes = {}
            for tier in self.announcers:
                # Iterating is ok, as the loop is ended after modification
                for i, announcer in enumerate(tier):
                    if self.rerequest_single(announcer, announce_kwargs,
                                             callback):
                        # Push successful announcer to front of list
                        if not self.last_failed and i != 0:
                            tier.pop(i)
                            tier.insert(0, announcer)
                        return
            # no success from any tracker
            self.sched(fail)
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
        self.sched(callback)

    def rerequest_single(self, announcer, kwargs, callback):
        code = self.lock.set()
        rq = threading.Thread(target=self._rerequest_single,
                              args=[announcer, kwargs, code, callback])
        rq.setDaemon(False)
        rq.start()
        self.lock.wait()
        if self.lock.success:
            self.lastsuccessful = announcer
            self.last_failed = False
            self.never_succeeded = False
            return True
        if not self.last_failed and self.lastsuccessful == announcer:
            # if the last tracker hit was successful, and you've just tried the
            # tracker you'd contacted before, don't go any further, just fail
            # silently.
            self.last_failed = True
            self.sched(callback)
            self.lock.give_up()
            return True
        return False    # returns true if it wants rerequest() to exit

    def _rerequest_single(self, announcer, kwargs, code, callback):
        try:
            def timedout(self=self, code=code):
                if self.lock.trip(code):
                    self.errorcodes['troublecode'] = 'Problem connecting to ' \
                        'tracker - timeout exceeded'
                    self.lock.unwait(code)

            self.sched(timedout, self.timeout)

            try:
                response = announcer.announce(self.infohash, self.myid,
                                              **kwargs)
                check_peers(response)
            except (IOError, socket.error) as e:
                if self.lock.trip(code):
                    self.errorcodes['troublecode'] = 'Problem connecting to ' \
                        'tracker - ' + str(e)
                    self.lock.unwait(code)
                return
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
            self.sched(add)
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
            if self.doneflag.is_set():
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
        self.sched(r)


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
