import os
import socket
import threading
import random
from cStringIO import StringIO
from traceback import print_exc
from .download_bt1 import BT1Download
from BitTornado.Network.RawServer import RawServer
from BitTornado.Network.SocketHandler import UPnP_ERROR
from .RateLimiter import RateLimiter
from BitTornado.Network.ServerPortHandler import MultiHandler
from BitTornado.Application.NumberFormats import formatIntClock
from BitTornado.Application.parsedir import parsedir
from BitTornado.Network.natpunch import UPnP_test
from BitTornado.clock import clock
from BitTornado.Application.PeerID import createPeerID, mapbase64


class SingleDownload:
    def __init__(self, controller, hash, response, config, myid):
        self.controller = controller
        self.hash = hash
        self.response = response
        self.config = config

        self.doneflag = threading.Event()
        self.waiting = True
        self.checking = False
        self.working = False
        self.seed = False
        self.closed = False

        self.status_msg = ''
        self.status_err = ['']
        self.status_errtime = 0
        self.status_done = 0.0

        self.rawserver = controller.handler.newRawServer(hash, self.doneflag)

        d = BT1Download(self.display, self.finished, self.error,
                        controller.exchandler, self.doneflag, config, response,
                        hash, myid, self.rawserver, controller.listen_port)
        self.d = d

    def start(self):
        if not self.d.saveAs(self.saveAs):
            self._shutdown()
            return
        self._hashcheckfunc = self.d.initFiles()
        if not self._hashcheckfunc:
            self._shutdown()
            return
        self.controller.hashchecksched(self.hash)

    def saveAs(self, name, length, saveas, isdir):
        return self.controller.saveAs(self.hash, name, saveas, isdir)

    def hashcheck_start(self, donefunc):
        if self.is_dead():
            self._shutdown()
            return
        self.waiting = False
        self.checking = True
        self._hashcheckfunc(donefunc)

    def hashcheck_callback(self):
        self.checking = False
        if self.is_dead():
            self._shutdown()
            return
        if not self.d.startEngine(ratelimiter=self.controller.ratelimiter):
            self._shutdown()
            return
        self.d.startRerequester()
        self.statsfunc = self.d.startStats()
        self.rawserver.start_listening(self.d.getPortHandler())
        self.working = True

    def is_dead(self):
        return self.doneflag.isSet()

    def _shutdown(self):
        self.shutdown(False)

    def shutdown(self, quiet=True):
        if self.closed:
            return
        self.doneflag.set()
        self.rawserver.shutdown()
        if self.checking or self.working:
            self.d.shutdown()
        self.waiting = False
        self.checking = False
        self.working = False
        self.closed = True
        self.controller.was_stopped(self.hash)
        if not quiet:
            self.controller.died(self.hash)

    def display(self, activity=None, fractionDone=None):
        # really only used by StorageWrapper now
        if activity:
            self.status_msg = activity
        if fractionDone is not None:
            self.status_done = float(fractionDone)

    def finished(self):
        self.seed = True

    def error(self, msg):
        if self.doneflag.isSet():
            self._shutdown()
        self.status_err.append(msg)
        self.status_errtime = clock()


class LaunchMany:
    def __init__(self, config, Output):
        try:
            self.config = config
            self.Output = Output

            self.torrent_dir = config['torrent_dir']
            self.torrent_cache = {}
            self.file_cache = {}
            self.blocked_files = {}
            self.scan_period = config['parse_dir_interval']
            self.stats_period = config['display_interval']

            self.torrent_list = []
            self.downloads = {}
            self.counter = 0
            self.doneflag = threading.Event()

            self.hashcheck_queue = []
            self.hashcheck_current = None

            self.rawserver = RawServer(
                self.doneflag, config['timeout_check_interval'],
                config['timeout'], ipv6_enable=config['ipv6_enabled'],
                failfunc=self.failed, errorfunc=self.exchandler)

            upnp_type = UPnP_test(config['upnp_nat_access'])
            while True:
                try:
                    self.listen_port = self.rawserver.find_and_bind(
                        config['minport'], config['maxport'], config['bind'],
                        ipv6_socket_style=config['ipv6_binds_v4'],
                        upnp=upnp_type, randomizer=config['random_port'])
                    break
                except socket.error as e:
                    if upnp_type and e == UPnP_ERROR:
                        self.Output.message(
                            'WARNING: COULD NOT FORWARD VIA UPnP')
                        upnp_type = 0
                        continue
                    self.failed("Couldn't listen - " + str(e))
                    return

            self.ratelimiter = RateLimiter(self.rawserver.add_task,
                                           config['upload_unit_size'])
            self.ratelimiter.set_upload_rate(config['max_upload_rate'])

            self.handler = MultiHandler(self.rawserver, self.doneflag, config)
            random.seed(createPeerID())
            self.rawserver.add_task(self.scan, 0)
            self.rawserver.add_task(self.stats, 0)

            self.handler.listen_forever()

            self.Output.message('shutting down')
            self.hashcheck_queue = []
            for hash in self.torrent_list:
                self.Output.message('dropped "{}"'.format(
                    self.torrent_cache[hash]['path']))
                self.downloads[hash].shutdown()
            self.rawserver.shutdown()

        except Exception:
            data = StringIO()
            print_exc(file=data)
            Output.exception(data.getvalue())

    def scan(self):
        self.rawserver.add_task(self.scan, self.scan_period)

        r = parsedir(self.torrent_dir, self.torrent_cache, self.file_cache,
                     self.blocked_files, return_metainfo=True,
                     errfunc=self.Output.message)

        (self.torrent_cache, self.file_cache, self.blocked_files, added,
         removed) = r

        for hash, data in removed.iteritems():
            self.Output.message('dropped "{}"'.format(data['path']))
            self.remove(hash)
        for hash, data in added.iteritems():
            self.Output.message('added "{}"'.format(data['path']))
            self.add(hash, data)

    def stats(self):
        self.rawserver.add_task(self.stats, self.stats_period)
        data = []
        for hash in self.torrent_list:
            cache = self.torrent_cache[hash]
            if self.config['display_path']:
                name = cache['path']
            else:
                name = cache['name']
            size = cache['length']
            d = self.downloads[hash]
            progress = '0.0%'
            peers = 0
            seeds = 0
            seedsmsg = "S"
            dist = 0.0
            uprate = 0.0
            dnrate = 0.0
            upamt = 0
            dnamt = 0
            t = 0
            if d.is_dead():
                status = 'stopped'
            elif d.waiting:
                status = 'waiting for hash check'
            elif d.checking:
                status = d.status_msg
                progress = '{:.1%}'.format(d.status_done)
            else:
                stats = d.statsfunc()
                s = stats['stats']
                if d.seed:
                    status = 'seeding'
                    progress = '100.0%'
                    seeds = s.numOldSeeds
                    seedsmsg = "s"
                    dist = s.numCopies
                else:
                    if s.numSeeds + s.numPeers:
                        t = stats['time']
                        if t == 0:  # unlikely
                            t = 0.01
                        status = formatIntClock(t) or 'downloading'
                    else:
                        t = -1
                        status = 'connecting to peers'
                    progress = '{:.1%}'.format(stats['frac'])
                    seeds = s.numSeeds
                    dist = s.numCopies2
                    dnrate = stats['down']
                peers = s.numPeers
                uprate = stats['up']
                upamt = s.upTotal
                dnamt = s.downTotal

            if d.is_dead() or d.status_errtime + 300 > clock():
                msg = d.status_err[-1]
            else:
                msg = ''

            data.append((name, status, progress, peers, seeds, seedsmsg, dist,
                         uprate, dnrate, upamt, dnamt, size, t, msg))
        stop = self.Output.display(data)
        if stop:
            self.doneflag.set()

    def remove(self, hash):
        self.torrent_list.remove(hash)
        self.downloads[hash].shutdown()
        del self.downloads[hash]

    def add(self, hash, data):
        c = self.counter
        self.counter += 1
        x = ''
        for _ in xrange(3):
            x = mapbase64[c & 0x3F] + x
            c >>= 6
        peer_id = createPeerID(x)
        d = SingleDownload(self, hash, data['metainfo'], self.config, peer_id)
        self.torrent_list.append(hash)
        self.downloads[hash] = d
        d.start()

    def saveAs(self, hash, name, saveas, isdir):
        x = self.torrent_cache[hash]
        style = self.config['saveas_style']
        if style == 1 or style == 3:
            if saveas:
                saveas = os.path.join(saveas, x['file'][:-1 - len(x['type'])])
            else:
                saveas = x['path'][:-1 - len(x['type'])]
            if style == 3:
                if not os.path.isdir(saveas):
                    try:
                        os.mkdir(saveas)
                    except OSError:
                        raise OSError("couldn't create directory for {} ({})"
                                      ''.format(x['path'], saveas))
                if not isdir:
                    saveas = os.path.join(saveas, name)
        else:
            if saveas:
                saveas = os.path.join(saveas, name)
            else:
                saveas = os.path.join(os.path.split(x['path'])[0], name)

        if isdir and not os.path.isdir(saveas):
            try:
                os.mkdir(saveas)
            except OSError:
                raise OSError("couldn't create directory for {} ({})".format(
                              x['path'], saveas))
        return saveas

    def hashchecksched(self, hash=None):
        if hash:
            self.hashcheck_queue.append(hash)
        if not self.hashcheck_current:
            self._hashcheck_start()

    def _hashcheck_start(self):
        self.hashcheck_current = self.hashcheck_queue.pop(0)
        self.downloads[self.hashcheck_current].hashcheck_start(
            self.hashcheck_callback)

    def hashcheck_callback(self):
        self.downloads[self.hashcheck_current].hashcheck_callback()
        if self.hashcheck_queue:
            self._hashcheck_start()
        else:
            self.hashcheck_current = None

    def died(self, hash):
        if hash in self.torrent_cache:
            self.Output.message('DIED: "{}"'.format(
                self.torrent_cache[hash]['path']))

    def was_stopped(self, hash):
        try:
            self.hashcheck_queue.remove(hash)
        except ValueError:
            pass
        if self.hashcheck_current == hash:
            self.hashcheck_current = None
            if self.hashcheck_queue:
                self._hashcheck_start()

    def failed(self, s):
        self.Output.message('FAILURE: ' + s)

    def exchandler(self, s):
        self.Output.exception(s)
