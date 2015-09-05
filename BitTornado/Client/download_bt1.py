import os
import warnings
import threading
from BitTornado.Meta.Info import MetaInfo, check_info
from urllib.parse import urlparse
from .Announce import urls_to_announcers
from .Choker import Choker
from BitTornado.Storage.Storage import Storage
from BitTornado.Storage.StorageWrapper import StorageWrapper
from BitTornado.Storage.FileSelector import FileSelector
from .Uploader import Upload
from .Downloader import Downloader
from .HTTPDownloader import HTTPDownloader
from .Connecter import Connecter
from .RateLimiter import RateLimiter
from BitTornado.Network.Encrypter import Encoder
from BitTornado.Network.NetworkAddress import IPv4
from BitTornado.Network.RawServer import autodetect_socket_style
from BitTornado.Network.Stream import geturl
from .Rerequester import Rerequester
from .DownloaderFeedback import DownloaderFeedback
from .RateMeasure import RateMeasure
from .CurrentRateMeasure import Measure
from .PiecePicker import PiecePicker
from .Statistics import Statistics
from BitTornado.Application.ConfigDir import ConfigDir
from BitTornado.Meta.bencode import bdecode
from BitTornado.Application.parseargs import parseargs, formatDefinitions
from BitTornado.Network.BTcrypto import CRYPTO_OK

defaults = [
    ('max_uploads', 7,
        "the maximum number of uploads to allow at once."),
    ('keepalive_interval', 120.0,
        'number of seconds to pause between sending keepalives'),
    ('download_slice_size', 2 ** 14,
        "How many bytes to query for per request."),
    ('upload_unit_size', 1460,
        "when limiting upload rate, how many bytes to send at a time"),
    ('request_backlog', 10,
        "maximum number of requests to keep in a single pipe at once."),
    ('max_message_length', 2 ** 23,
        "maximum length prefix encoding you'll accept over the wire - "
        "larger values get the connection dropped."),
    ('ip', '',
        "ip to report you have to the tracker."),
    ('minport', 10000, 'minimum port to listen on, counts up if unavailable'),
    ('maxport', 60000, 'maximum port to listen on'),
    ('random_port', 1, 'whether to choose randomly inside the port range '
        'instead of counting up linearly'),
    ('metafile', '',
        'file the server response was stored in, alternative to url'),
    ('url', '',
        'url to get file from, alternative to metafile'),
    ('crypto_allowed', int(CRYPTO_OK),
        'whether to allow the client to accept encrypted connections'),
    ('crypto_only', 0,
        'whether to only create or allow encrypted connections'),
    ('crypto_stealth', 0,
        'whether to prevent all non-encrypted connection attempts; '
        'will result in an effectively firewalled state on older trackers'),
    ('selector_enabled', 1,
        'whether to enable the file selector and fast resume function'),
    ('expire_cache_data', 10,
        'the number of days after which you wish to expire old cache data '
        '(0 = disabled)'),
    ('priority', '',
        'a list of file priorities separated by commas, must be one per file, '
        '0 = highest, 1 = normal, 2 = lowest, -1 = download disabled'),
    ('saveas', '',
        'local file name to save the file as, null indicates query user'),
    ('timeout', 300.0,
        'time to wait between closing sockets which nothing has been received '
        'on'),
    ('timeout_check_interval', 60.0,
        'time to wait between checking if any connections have timed out'),
    ('max_slice_length', 2 ** 17,
        "maximum length slice to send to peers, larger requests are ignored"),
    ('max_rate_period', 20.0,
        "maximum amount of time to guess the current rate estimate "
        "represents"),
    ('bind', '',
        'comma-separated list of ips/hostnames to bind to locally'),
    #('ipv6_enabled', autodetect_ipv6(),
    ('ipv6_enabled', 0, 'allow the client to connect to peers via IPv6'),
    ('ipv6_binds_v4', autodetect_socket_style(),
        "set if an IPv6 server socket won't also field IPv4 connections"),
    ('upnp_nat_access', 1,
        'attempt to autoconfigure a UPnP router to forward a server port '
        '(0 = disabled, 1 = mode 1 [fast], 2 = mode 2 [slow])'),
    ('upload_rate_fudge', 5.0,
        'time equivalent of writing to kernel-level TCP buffer, for rate '
        'adjustment'),
    ('tcp_ack_fudge', 0.03,
        'how much TCP ACK download overhead to add to upload rate calculations'
        ' (0 = disabled)'),
    ('display_interval', .5,
        'time between updates of displayed information'),
    ('rerequest_interval', 5 * 60,
        'time to wait between requesting more peers'),
    ('min_peers', 20,
        'minimum number of peers to not do rerequesting'),
    ('http_timeout', 60,
        'number of seconds to wait before assuming that an http connection has'
        'timed out'),
    ('max_initiate', 40,
        'number of peers at which to stop initiating new connections'),
    ('check_hashes', 1,
        'whether to check hashes on disk'),
    ('max_upload_rate', 0,
        'maximum kB/s to upload at (0 = no limit, -1 = automatic)'),
    ('max_download_rate', 0,
        'maximum kB/s to download at (0 = no limit)'),
    ('alloc_type', 'normal',
        'allocation type (may be normal, background, pre-allocate or sparse)'),
    ('alloc_rate', 2.0,
        'rate (in MiB/s) to allocate space at using background allocation'),
    ('buffer_reads', 1,
        'whether to buffer disk reads'),
    ('write_buffer_size', 4,
        'the maximum amount of space to use for buffering disk writes '
        '(in megabytes, 0 = disabled)'),
    ('breakup_seed_bitfield', 1,
        'sends an incomplete bitfield and then fills with have messages, '
        'in order to get around stupid ISP manipulation'),
    ('snub_time', 30.0,
        "seconds to wait for data to come in over a connection before assuming"
        "it's semi-permanently choked"),
    ('spew', 0,
        "whether to display diagnostic info to stdout"),
    ('rarest_first_cutoff', 2,
        "number of downloads at which to switch from random to rarest first"),
    ('rarest_first_priority_cutoff', 5,
        'the number of peers which need to have a piece before other partials '
        'take priority over rarest first'),
    ('min_uploads', 4,
        "the number of uploads to fill out to with extra optimistic unchokes"),
    ('max_files_open', 50,
        'the maximum number of files to keep open at a time, 0 means no '
        'limit'),
    ('round_robin_period', 30,
        "the number of seconds between the client's switching upload targets"),
    ('super_seeder', 0,
        "whether to use special upload-efficiency-maximizing routines (only "
        "for dedicated seeds)"),
    ('security', 1,
        "whether to enable extra security features intended to prevent abuse"),
    ('max_connections', 0,
        "the absolute maximum number of peers to connect with (0 = no limit)"),
    ('auto_kick', 1,
        "whether to allow the client to automatically kick/ban peers that "
        "send bad data"),
    ('double_check', 1,
        "whether to double-check data being written to the disk for errors "
        "(may increase CPU load)"),
    ('triple_check', 0,
        "whether to thoroughly check data being written to the disk (may slow"
        "disk access)"),
    ('lock_files', 1,
        "whether to lock files the client is working with"),
    ('lock_while_reading', 0,
        "whether to lock access to files being read"),
    ('auto_flush', 0,
        "minutes between automatic flushes to disk (0 = disabled)"),
    ('dedicated_seed_id', '',
        "code to send to tracker identifying as a dedicated seed"),
]

argslistheader = 'Arguments are:\n\n'


def parse_params(params, presets={}):
    if len(params) == 0:
        return None
    config, args = parseargs(params, defaults, 0, 1, presets=presets)
    if args:
        if config['metafile'] or config['url']:
            raise ValueError('must have metafile or url as arg or '
                             'parameter, not both')
        if os.path.isfile(args[0]):
            config['metafile'] = args[0]
        else:
            try:
                urlparse(args[0])
            except ValueError:
                raise ValueError('bad filename or url')
            config['url'] = args[0]
    elif (config['metafile'] == '') == (config['url'] == ''):
        raise ValueError('need metafile or url, must have one, cannot have '
                         'both')
    return config


def get_usage(defaults=defaults, cols=100, presets={}):
    return argslistheader + formatDefinitions(defaults, cols, presets)


def get_metainfo(fname, url, errorfunc):
    with WarningLock(lambda *args: errorfunc("warning: bad data in metafile")):
        if fname:
            try:
                metainfo = MetaInfo.read(fname)
            except (OSError, TypeError, KeyError, ValueError):
                errorfunc(fname + ' is not a valid metafile')
                return None
        else:
            try:
                metainfo = MetaInfo(bdecode(geturl(url)))
            except IOError as e:
                errorfunc('problem getting response info - ' + str(e))
                return None
            except (TypeError, KeyError, ValueError):
                errorfunc(fname + ' is not a valid metafile')
                return None

    try:
        check_info(metainfo.get('info'))
    except ValueError as e:
        errorfunc("got bad file info - " + str(e))
        return None

    return metainfo


class BT1Download:
    def __init__(self, statusfunc, finfunc, errorfunc, excfunc, doneflag,
                 config, metainfo, infohash, peerid, rawserver, port,
                 appdataobj=None):
        self.statusfunc = statusfunc
        self.finfunc = finfunc
        self.errorfunc = errorfunc
        self.excfunc = excfunc
        self.doneflag = doneflag
        self.config = config
        self.metainfo = metainfo    # MetaInfo
        self.infohash = infohash    # bytes[20]
        self.myid = peerid          # bytes
        self.rawserver = rawserver
        self.port = port

        self.pieces = self.metainfo['info'].hasher.pieces   # [bytes[20]]
        self.len_pieces = len(self.pieces)
        self.argslistheader = argslistheader
        self.unpauseflag = threading.Event()
        self.unpauseflag.set()
        self.downloader = None
        self.storagewrapper = None
        self.fileselector = None
        self.super_seeding_active = False
        self.filedatflag = threading.Event()
        self.spewflag = threading.Event()
        self.superseedflag = threading.Event()
        self.whenpaused = None
        self.finflag = threading.Event()
        self.rerequest = None
        self.tcp_ack_fudge = config['tcp_ack_fudge']

        self.selector_enabled = config['selector_enabled']
        if appdataobj:
            self.appdataobj = appdataobj
        elif self.selector_enabled:
            self.appdataobj = ConfigDir()
            self.appdataobj.deleteOldCacheData(config['expire_cache_data'],
                                               [self.infohash])

        self.excflag = self.rawserver.get_exception_flag()
        self.failed = False
        self.checking = False
        self.started = False

        self.picker = PiecePicker(self.len_pieces,
                                  config['rarest_first_cutoff'],
                                  config['rarest_first_priority_cutoff'])
        self.choker = Choker(config, rawserver.add_task,
                             self.picker, self.finflag.is_set)

    def saveAs(self, filefunc, pathfunc=None):
        try:
            def make(f, forcedir=False):
                if not forcedir:
                    f = os.path.split(f)[0]
                if f != '' and not os.path.exists(f):
                    os.makedirs(f)

            info = self.metainfo['info']
            if 'length' in info:
                file_length = info['length']
                fname = filefunc(info['name'], file_length,
                                 self.config['saveas'], False)
                if fname is None:
                    return None
                make(fname)
                files = [(fname, file_length)]
            else:
                file_length = sum(x['length'] for x in info['files'])
                fname = filefunc(info['name'], file_length,
                                 self.config['saveas'], True)
                if fname is None:
                    return None

                # if this path exists, and no files from the info dict exist,
                # we assume it's a new download and the user wants to create a
                # new directory with the default name
                existing = 0
                if os.path.exists(fname):
                    if not os.path.isdir(fname):
                        self.errorfunc(fname + 'is not a dir')
                        return None
                    if len(os.listdir(fname)) > 0:  # if it's not empty
                        existing = any(
                            os.path.exists(os.path.join(fname, x['path'][0]))
                            for x in info['files'])
                        if not existing:
                            fname = os.path.join(fname, info['name'])
                            if os.path.exists(fname) and \
                                    not os.path.isdir(fname):
                                if fname[-8:] == '.torrent':
                                    fname = fname[:-8]
                                if os.path.exists(fname) and \
                                        not os.path.isdir(fname):
                                    self.errorfunc("Can't create dir - " +
                                                   info['name'])
                                    return None
                make(fname, True)

                # alert the UI to any possible change in path
                if pathfunc is not None:
                    pathfunc(fname)

                files = []
                for x in info['files']:
                    n = os.path.join(fname, *x['path'])
                    files.append((n, x['length']))
                    make(n)
        except OSError as e:
            self.errorfunc("Couldn't allocate dir - " + str(e))
            return None

        self.filename = fname
        self.files = files
        self.datalength = file_length

        return fname

    def _finished(self):
        self.finflag.set()
        try:
            self.storage.set_readonly()
        except (IOError, OSError) as e:
            self.errorfunc('trouble setting readonly at end - ' + str(e))
        if self.superseedflag.is_set():
            self._set_super_seed()
        self.choker.set_round_robin_period(
            max(self.config['round_robin_period'],
                self.config['round_robin_period'] *
                self.metainfo['info']['piece length'] / 200000))
        self.rerequest_complete()
        self.finfunc()

    def _data_flunked(self, amount, index):
        self.ratemeasure_datarejected(amount)
        if not self.doneflag.is_set():
            self.errorfunc('piece {:d} failed hash check, re-downloading it'
                           ''.format(index))

    def _failed(self, reason):
        self.failed = True
        self.doneflag.set()
        if reason is not None:
            self.errorfunc(reason)

    def initFiles(self, old_style=False, statusfunc=None):
        if self.doneflag.is_set():
            return None
        if not statusfunc:
            statusfunc = self.statusfunc

        disabled_files = None
        if self.selector_enabled:
            self.priority = self.config['priority']
            if self.priority:
                try:
                    self.priority = self.priority.split(',')
                    assert len(self.priority) == len(self.files)
                    self.priority = [int(p) for p in self.priority]
                    for p in self.priority:
                        assert p >= -1
                        assert p <= 2
                except (AssertionError, ValueError):
                    self.errorfunc('bad priority list given, ignored')
                    self.priority = None

            data = self.appdataobj.getTorrentData(self.infohash)
            try:
                d = data['resume data']['priority']
                assert len(d) == len(self.files)
                disabled_files = [x == -1 for x in d]
            except (KeyError, TypeError, AssertionError):
                try:
                    disabled_files = [x == -1 for x in self.priority]
                except TypeError:
                    pass

        piece_length = self.metainfo['info']['piece length']
        try:
            try:
                self.storage = Storage(self.files, piece_length, self.doneflag,
                                       self.config, disabled_files)
            except IOError as e:
                self.errorfunc('trouble accessing files - ' + str(e))
                return None
            if self.doneflag.is_set():
                return None

            self.storagewrapper = StorageWrapper(
                self.storage, self.config['download_slice_size'],
                self.pieces, piece_length, self._finished,
                self._failed, statusfunc, self.doneflag,
                self.config['check_hashes'], self._data_flunked,
                self.rawserver.add_task, self.config, self.unpauseflag)

        except ValueError as e:
            self._failed('bad data - ' + str(e))
        except IOError as e:
            self._failed('IOError - ' + str(e))
        if self.doneflag.is_set():
            return None

        if self.selector_enabled:
            self.fileselector = FileSelector(
                self.files, piece_length,
                self.appdataobj.getPieceDir(self.infohash), self.storage,
                self.storagewrapper, self.rawserver.add_task, self._failed)
            if data:
                data = data.get('resume data')
                if data:
                    self.fileselector.unpickle(data)

        self.checking = True
        if old_style:
            return self.storagewrapper.old_style_init()
        return self.storagewrapper.initialize

    def _make_upload(self, connection, ratelimiter, totalup):
        return Upload(connection, ratelimiter, totalup,
                      self.choker, self.storagewrapper, self.picker,
                      self.config)

    def _kick_peer(self, connection):
        self.rawserver.add_task(connection.close, 0)

    def _ban_peer(self, ip):
        self.encoder.ban(ip)

    def _received_raw_data(self, x):
        if self.tcp_ack_fudge:
            x = int(x * self.tcp_ack_fudge)
            self.ratelimiter.adjust_sent(x)

    def _received_data(self, x):
        self.downmeasure.update_rate(x)
        self.ratemeasure.data_came_in(x)

    def _received_http_data(self, x):
        self.downmeasure.update_rate(x)
        self.ratemeasure.data_came_in(x)
        self.downloader.external_data_received(x)

    def _cancelfunc(self, pieces):
        self.downloader.cancel_piece_download(pieces)
        self.httpdownloader.cancel_piece_download(pieces)

    def _reqmorefunc(self, pieces):
        self.downloader.requeue_piece_download(pieces)

    def startEngine(self, ratelimiter=None, statusfunc=None):
        if self.doneflag.is_set():
            return False
        if not statusfunc:
            statusfunc = self.statusfunc

        self.checking = False

        if not CRYPTO_OK:
            if self.config['crypto_allowed']:
                self.errorfunc('warning - crypto library not installed')
            self.config['crypto_allowed'] = 0
            self.config['crypto_only'] = 0
            self.config['crypto_stealth'] = 0

        for i in range(self.len_pieces):
            if self.storagewrapper.do_I_have(i):
                self.picker.complete(i)
        self.upmeasure = Measure(self.config['max_rate_period'],
                                 self.config['upload_rate_fudge'])
        self.downmeasure = Measure(self.config['max_rate_period'])

        if ratelimiter:
            self.ratelimiter = ratelimiter
        else:
            self.ratelimiter = RateLimiter(self.rawserver.add_task,
                                           self.config['upload_unit_size'],
                                           self.setConns)
            self.ratelimiter.set_upload_rate(self.config['max_upload_rate'])

        self.ratemeasure = RateMeasure()
        self.ratemeasure_datarejected = self.ratemeasure.data_rejected

        self.downloader = Downloader(
            self.storagewrapper, self.picker, self.config['request_backlog'],
            self.config['max_rate_period'], self.len_pieces,
            self.config['download_slice_size'], self._received_data,
            self.config['snub_time'], self.config['auto_kick'],
            self._kick_peer, self._ban_peer)
        self.downloader.set_download_rate(self.config['max_download_rate'])
        self.connecter = Connecter(
            self._make_upload, self.downloader, self.choker, self.len_pieces,
            self.upmeasure, self.config, self.ratelimiter,
            self.rawserver.add_task)
        self.encoder = Encoder(
            self.connecter, self.rawserver, self.myid,
            self.config['max_message_length'], self.rawserver.add_task,
            self.config['keepalive_interval'], self.infohash,
            self._received_raw_data, self.config)

        self.httpdownloader = HTTPDownloader(
            self.storagewrapper, self.picker, self.rawserver, self.finflag,
            self.errorfunc, self.downloader, self.config['max_rate_period'],
            self.infohash, self._received_http_data, self.connecter.got_piece)
        if 'httpseeds' in self.metainfo and not self.finflag.is_set():
            for u in self.metainfo['httpseeds']:
                self.httpdownloader.make_download(u)

        if self.selector_enabled:
            self.fileselector.tie_in(self.picker, self._cancelfunc,
                                     self._reqmorefunc,
                                     self.rerequest_ondownloadmore)
            if self.priority:
                self.fileselector.set_priorities_now(self.priority)

            # erase old data once you've started modifying it
            self.appdataobj.deleteTorrentData(self.infohash)

        if self.config['super_seeder']:
            self.set_super_seed()

        self.started = True
        return True

    def rerequest_complete(self):
        if self.rerequest:
            self.rerequest.announce(2)

    def rerequest_stopped(self):
        if self.rerequest:
            self.rerequest.announce(3)

    def rerequest_lastfailed(self):
        if self.rerequest:
            return self.rerequest.last_failed
        return False

    def rerequest_ondownloadmore(self):
        if self.rerequest:
            self.rerequest.hit()

    def startRerequester(self, force_rapid_update=False):
        tracker_urls = self.metainfo.get('announce-list',
                                         [[self.metainfo['announce']]])
        kwargs = {'port': self.port,
                  'ip': IPv4(self.config['ip']),
                  'seed_id': self.config['dedicated_seed_id'],
                  'supportcrypto': self.config['crypto_allowed'],
                  'requirecrypto': self.config['crypto_only'],
                  'cryptostealth': self.config['crypto_stealth'],
                  'no_peer_id': True,
                  'compact': True}
        announcers = urls_to_announcers(tracker_urls, **kwargs)

        self.rerequest = Rerequester(
            self.myid, self.infohash, announcers, self.config,
            self.rawserver.add_task, self.errorfunc, self.excfunc,
            self.encoder.start_connections,
            self.connecter.how_many_connections,
            self.storagewrapper.get_amount_left, self.upmeasure.get_total,
            self.downmeasure.get_total, self.upmeasure.get_rate,
            self.downmeasure.get_rate, self.doneflag, self.unpauseflag,
            force_rapid_update)

        self.rerequest.start()

    def _init_stats(self):
        self.statistics = Statistics(
            self.upmeasure, self.downmeasure, self.connecter,
            self.httpdownloader, self.ratelimiter, self.rerequest_lastfailed,
            self.filedatflag)
        if 'files' in self.metainfo['info']:
            self.statistics.set_dirstats(self.files,
                                         self.metainfo['info']['piece length'])
        if self.config['spew']:
            self.spewflag.set()

    def autoStats(self, displayfunc=None):
        if not displayfunc:
            displayfunc = self.statusfunc

        self._init_stats()
        DownloaderFeedback(
            self.choker, self.httpdownloader, self.rawserver.add_task,
            self.upmeasure.get_rate, self.downmeasure.get_rate,
            self.ratemeasure, self.storagewrapper.get_stats, self.datalength,
            self.finflag, self.spewflag, self.statistics, displayfunc,
            self.config['display_interval'])

    def startStats(self):
        self._init_stats()
        d = DownloaderFeedback(
            self.choker, self.httpdownloader, self.rawserver.add_task,
            self.upmeasure.get_rate, self.downmeasure.get_rate,
            self.ratemeasure, self.storagewrapper.get_stats, self.datalength,
            self.finflag, self.spewflag, self.statistics)
        return d.gather

    def getPortHandler(self):
        return self.encoder

    def shutdown(self, torrentdata={}):
        if self.checking or self.started:
            self.storagewrapper.sync()
            self.storage.close()
            self.rerequest_stopped()
        if self.fileselector and self.started:
            if not self.failed:
                self.fileselector.finish()
                torrentdata['resume data'] = self.fileselector.pickle()
            try:
                self.appdataobj.writeTorrentData(self.infohash, torrentdata)
            except Exception as e:
                print(e)
                self.appdataobj.deleteTorrentData(self.infohash)  # clear it
        return not self.failed and not self.excflag.is_set()
        # if returns false, you may wish to auto-restart the torrent

    def setConns(self, conns, conns2=None):
        if not conns2:
            conns2 = conns
        try:
            def s(self=self, conns=conns, conns2=conns2):
                self.config['min_uploads'] = conns
                self.config['max_uploads'] = conns2
                if conns > 30:
                    self.config['max_initiate'] = conns + 10
            self.rawserver.add_task(s)
        except AttributeError:
            pass

    def set_super_seed(self):
        try:
            self.superseedflag.set()

            def s(self=self):
                if self.finflag.is_set():
                    self._set_super_seed()
            self.rawserver.add_task(s)
        except AttributeError:
            pass

    def _set_super_seed(self):
        if not self.super_seeding_active:
            self.super_seeding_active = True
            self.errorfunc('        ** SUPER-SEED OPERATION ACTIVE **\n  '
                           'please set Max uploads so each peer gets 6-8 kB/s')

            def s(self=self):
                self.downloader.set_super_seed()
                self.choker.set_super_seed()
            self.rawserver.add_task(s)
            # mode started when already finished
            if self.finflag.is_set():
                def r(self=self):
                    # so after kicking everyone off, reannounce
                    self.rerequest.announce(0)
                self.rawserver.add_task(r)

    def am_I_finished(self):
        return self.finflag.is_set()


class WarningLock(object):
    lock = threading.Lock()

    def __init__(self, showwarning=lambda *args: None):
        self.showwarning = showwarning

    def __enter__(self):
        self.lock.acquire()
        self.old_showwarning = warnings.showwarning
        warnings.showwarning = self.showwarning

    def __exit__(self, _type, _value, _traceback):
        warnings.showwarning = self.old_showwarning
        del self.old_showwarning
        self.lock.release()
