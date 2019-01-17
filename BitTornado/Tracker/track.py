import sys
import os
import re
import time
import signal
import random
import threading
import urllib
from enum import IntEnum
from io import StringIO
from traceback import print_exc
from binascii import hexlify

from .Filter import Filter
from .HTTPHandler import HTTPHandler, months
from .T2T import T2TList
from .torrentlistparse import parsetorrentlist
from .State import TrackerState, Peer, Times, Counter, \
    BencodedCache, compact_peer_info
from BitTornado.Application.NumberFormats import formatSize
from BitTornado.Application.parseargs import parseargs, formatDefinitions
from BitTornado.Application.parsedir import parsedir
from BitTornado.Client.Announce import HTTPAnnouncer, Response
from BitTornado.Meta.bencode import bencode
from BitTornado.Network.BTcrypto import CRYPTO_OK
from BitTornado.Network.NatCheck import NatCheck, CHECK_PEER_ID_ENCRYPTED
from BitTornado.Network.NetworkAddress import is_valid_ip, to_ipv4, AddrList
from BitTornado.Network.RawServer import RawServer, autodetect_socket_style
from ..Types import TypedDict, Port
from BitTornado.clock import clock

from BitTornado import version
from BitTornado.Application.PeerID import createPeerID

defaults = [
    ('port', 80, "Port to listen on."),
    ('dfile', None, 'file to store recent downloader info in'),
    ('bind', '', 'comma-separated list of ips/hostnames to bind to locally'),
    # ('ipv6_enabled', autodetect_ipv6(),
    ('ipv6_enabled', 0, 'allow the client to connect to peers via IPv6'),
    ('ipv6_binds_v4', autodetect_socket_style(),
     'set if an IPv6 server socket will also field IPv4 connections'),
    ('socket_timeout', 15, 'timeout for closing connections'),
    ('save_dfile_interval', 5 * 60, 'seconds between saving dfile'),
    ('timeout_downloaders_interval', 45 * 60,
     'seconds between expiring downloaders'),
    ('reannounce_interval', 30 * 60,
     'seconds downloaders should wait between reannouncements'),
    ('response_size', 50, 'number of peers to send in an info message'),
    ('timeout_check_interval', 5,
        'time to wait between checking if any connections have timed out'),
    ('nat_check', 3,
     "how many times to check if a downloader is behind a NAT "
     "(0 = don't check)"),
    ('log_nat_checks', 0,
     "whether to add entries to the log for nat-check results"),
    ('min_time_between_log_flushes', 3.0,
     'minimum time it must have been since the last flush to do another one'),
    ('min_time_between_cache_refreshes', 600.0,
     'minimum time in seconds before a cache is considered stale and is '
     'flushed'),
    ('allowed_dir', '', 'only allow downloads for .torrents in this dir'),
    ('allowed_list', '',
     'only allow downloads for hashes in this list (hex format, one per '
     'line)'),
    ('allowed_controls', 0,
     'allow special keys in torrents in the allowed_dir to affect tracker '
     'access'),
    ('multitracker_enabled', 0, 'whether to enable multitracker operation'),
    ('multitracker_allowed', 'autodetect',
     'whether to allow incoming tracker announces (can be none, autodetect or '
     'all)'),
    ('multitracker_reannounce_interval', 2 * 60,
     'seconds between outgoing tracker announces'),
    ('multitracker_maxpeers', 20,
     'number of peers to get in a tracker announce'),
    ('aggregate_forward', '',
     'format: <url>[,<password>] - if set, forwards all non-multitracker to '
     'this url with this optional password'),
    ('aggregator', '0',
     'whether to act as a data aggregator rather than a tracker.  If enabled, '
     'may be 1, or <password>; if password is set, then an incoming password '
     'is required for access'),
    ('hupmonitor', 0,
     'whether to reopen the log file upon receipt of HUP signal'),
    ('http_timeout', 60,
     'number of seconds to wait before assuming that an http connection has '
     'timed out'),
    ('parse_dir_interval', 60,
     'seconds between reloading of allowed_dir or allowed_file and '
     'allowed_ips and banned_ips lists'),
    ('show_infopage', 1,
     "whether to display an info page when the tracker's root dir is loaded"),
    ('infopage_redirect', '', 'a URL to redirect the info page to'),
    ('show_names', 1, 'whether to display names from allowed dir'),
    ('favicon', '',
     'file containing x-icon data to return when browser requests '
     'favicon.ico'),
    ('allowed_ips', '',
     'only allow connections from IPs specified in the given file; file '
     'contains subnet data in the format: aa.bb.cc.dd/len'),
    ('banned_ips', '',
     "don't allow connections from IPs specified in the given file; file "
     'contains IP range data in the format: xxx:xxx:ip1-ip2'),
    ('only_local_override_ip', 2,
     "ignore the ip GET parameter from machines which aren't on local network "
     'IPs (0 = never, 1 = always, 2 = ignore if NAT checking is not enabled)'),
    ('logfile', '',
     'file to write the tracker logs, use - for stdout (default)'),
    ('allow_get', 0,
     'use with allowed_dir; adds a /file?hash={hash} url that allows users to '
     'download the torrent file'),
    ('keep_dead', 0, 'keep dead torrents after they expire (so they still '
     'show up on your /scrape and web page)'),
    ('scrape_allowed', 'full',
     'scrape access allowed (can be none, specific or full)'),
    ('dedicated_seed_id', '',
     'allows tracker to monitor dedicated seed(s) and flag torrents as '
     'seeded'),
    ('compact_reqd', 1, "only allow peers that accept a compact response"),
]


class CompactResponse(TypedDict):
    typemap = {'failure reason': str, 'warning message': str, 'interval': int,
               'min interval': int, 'tracker id': bytes, 'complete': int,
               'incomplete': int, 'crypto_flags': bytes, 'peers': bytes}

alas = b'your file may exist elsewhere in the universe\nbut alas, not here\n'

local_IPs = AddrList()
local_IPs.set_intranet_addresses()


def isotime(secs=None):
    if secs is None:
        secs = time.time()
    return time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(secs))

http_via_filter = re.compile(' for ([0-9.]+)\Z')


def _get_forwarded_ip(headers):
    header = headers.get('x-forwarded-for')
    if header:
        try:
            x, y = header.split(',')
            if is_valid_ip(x) and x not in local_IPs:
                return x
            return y
        except ValueError:
            return header
    header = headers.get('client-ip')
    if header:
        return header
    header = headers.get('via')
    if header:
        x = http_via_filter.search(header)
        try:
            return x.group(1)
        except AttributeError:
            pass
    return headers.get('from')


def get_forwarded_ip(headers):
    x = _get_forwarded_ip(headers)
    if not x or not is_valid_ip(x) or x in local_IPs:
        return None
    return x


class Return(IntEnum):
    """Type of representation of peers to return to client"""
    crypto_none = 0
    crypto_required = 1
    crypto_supported = 2
    with_peerid = 3
    no_peerid = 4


class Tracker(object):
    def __init__(self, config, rawserver):
        self.config = config
        self.response_size = config['response_size']            # int (# peers)
        self.dfile = config['dfile']                            # str|None
        self.natcheck = config['nat_check']                     # int
        self.parse_dir_interval = config['parse_dir_interval']  # int (sec)
        self.favicon = None                                     # bytes|None
        favicon = config['favicon']                             # str
        if favicon:
            try:
                with open(favicon, 'rb') as handle:
                    self.favicon = handle.read()
            except IOError:
                print("**warning** specified favicon file -- %s -- does not "
                      "exist." % favicon)

        self.rawserver = rawserver  # RawServer
        self.cached = {}    # format: infohash: [[time1, l1, s1], ...]
        self.cached_t = {}  # format: infohash: [time, cache]
        self.state = TrackerState()
        self.times = Times()
        self.seedcount = Counter()

        self.allowed_IPs = None
        self.banned_IPs = None
        if config['allowed_ips'] or config['banned_ips']:
            self.allowed_ip_mtime = 0
            self.banned_ip_mtime = 0
            self.read_ip_lists()

        self.only_local_override_ip = config['only_local_override_ip']
        if self.only_local_override_ip == 2:
            self.only_local_override_ip = not config['nat_check']

        if CHECK_PEER_ID_ENCRYPTED and not CRYPTO_OK:
            print('**warning** crypto library not installed, cannot '
                  'completely verify encrypted peers')

        if os.path.exists(self.dfile):
            try:
                tempstate = TrackerState.read(self.dfile)
                tempstate.validate()
                self.state = tempstate
            except (IOError, ValueError, TypeError):
                print('**warning** statefile ' + self.dfile +
                      ' corrupt; resetting')
        self.downloads = self.state.setdefault('peers', {})
        self.completed = self.state.setdefault('completed', {})

        self.becache = BencodedCache(config['compact_reqd'])
        for infohash, peers in self.downloads.items():
            self.seedcount[infohash] = 0
            for peerid, peer in list(peers.items()):
                ip = peer['ip']
                if self.allowed_IPs and ip not in self.allowed_IPs \
                        or self.banned_IPs and ip in self.banned_IPs:
                    del peers[peerid]
                    continue
                if not peer['left']:
                    self.seedcount[infohash] += 1
                if peer.get('nat', -1):
                    continue
                gip = peer.get('given_ip')
                if is_valid_ip(gip) and (not self.only_local_override_ip or
                                         ip in local_IPs):
                    ip = gip
                self.becache[infohash].add_peer(peerid, peer, ip, peer['port'])

        self.times = {dl: {sub: 0 for sub in subs}
                      for dl, subs in self.downloads.items()}

        self.trackerid = createPeerID(b'-T-')
        random.seed(self.trackerid)

        self.reannounce_interval = config['reannounce_interval']
        self.save_dfile_interval = config['save_dfile_interval']
        self.show_names = config['show_names']
        rawserver.add_task(self.save_state, self.save_dfile_interval)
        self.prevtime = clock()
        self.timeout_downloaders_interval = config[
            'timeout_downloaders_interval']
        rawserver.add_task(self.expire_downloaders,
                           self.timeout_downloaders_interval)
        self.logfile = None
        self.log = None
        if config['logfile'] and config['logfile'] != '-':
            try:
                self.logfile = config['logfile']
                self.log = open(self.logfile, 'a')
                sys.stdout = self.log
                print("# Log Started: ", isotime())
            except IOError:
                print("**warning** could not redirect stdout to log file:",
                      sys.exc_info()[0])

        if config['hupmonitor']:
            def huphandler(signum, frame, self=self):
                try:
                    self.log.close()
                    self.log = open(self.logfile, 'a')
                    sys.stdout = self.log
                    print("# Log reopened: ", isotime())
                except IOError:
                    print("**warning** could not reopen logfile")

            signal.signal(signal.SIGHUP, huphandler)

        self.allow_get = config['allow_get']

        self.t2tlist = T2TList(config['multitracker_enabled'], self.trackerid,
                               config['multitracker_reannounce_interval'],
                               config['multitracker_maxpeers'],
                               config['http_timeout'],
                               self.rawserver)

        if config['allowed_list']:
            if config['allowed_dir']:
                print('**warning** allowed_dir and allowed_list options '
                      'cannot be used together')
                print('**warning** disregarding allowed_dir')
                config['allowed_dir'] = ''
            self.allowed = self.state.setdefault('allowed_list', {})
            self.allowed_list_mtime = 0
            self.parse_allowed()
            self.remove_from_state('allowed', 'allowed_dir_files')
            if config['multitracker_allowed'] == 'autodetect':
                config['multitracker_allowed'] = 'none'
            config['allowed_controls'] = 0

        elif config['allowed_dir']:
            self.allowed = self.state.setdefault('allowed', {})
            self.allowed_dir_files = self.state.setdefault(
                'allowed_dir_files', {})
            self.allowed_dir_blocked = set()
            self.parse_allowed()
            self.remove_from_state('allowed_list')

        else:
            self.allowed = None
            self.remove_from_state('allowed', 'allowed_dir_files',
                                   'allowed_list')
            if config['multitracker_allowed'] == 'autodetect':
                config['multitracker_allowed'] = 'none'
            config['allowed_controls'] = 0

        self.uq_broken = urllib.parse.unquote('+') != ' '
        self.keep_dead = config['keep_dead']
        self.Filter = Filter(rawserver.add_task)

        aggregator = config['aggregator']
        self.is_aggregator = aggregator != '0'
        self.aggregator_key = None
        if self.is_aggregator:
            self.natcheck = 0
            if aggregator != '1':
                self.aggregator_key = aggregator

        send = config['aggregate_forward']
        if not send:
            self.aggregate_forward = None
        else:
            sends = send.split(',')
            self.aggregate_forward = HTTPAnnouncer(sends[0])
            self.aggregate_password = sends[1] if len(sends) > 1 else None

        self.dedicated_seed_id = config['dedicated_seed_id']
        self.is_seeded = {}

        self.cachetime = 0
        self.cachetimeupdate()

    def cachetimeupdate(self):
        self.cachetime += 1     # raw clock, but more efficient for cache
        self.rawserver.add_task(self.cachetimeupdate, 1)

    def aggregate_senddata(self, query):
        threading.Thread(target=self.aggregate_forward.forward_query,
                         args=(query, self.aggregate_password),
                         daemon=False).start()

    def get_infopage(self):
        try:
            if not self.config['show_infopage']:
                return (404, 'Not Found', {'Content-Type': 'text/plain',
                                           'Pragma': 'no-cache'}, alas)
            red = self.config['infopage_redirect']
            if red:
                return (302, 'Found', {'Content-Type': 'text/html',
                                       'Location': red},
                        '<A HREF="{}">Click Here</A>'.format(red).encode())

            s = StringIO()
            s.write('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" '
                    '"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n'
                    '<html><head><title>BitTorrent download info</title>\n')
            if self.favicon is not None:
                s.write('<link rel="shortcut icon" href="/favicon.ico">\n')
            s.write('</head>\n<body>\n<h3>BitTorrent download info</h3>\n'
                    '<ul>\n<li><strong>tracker version:</strong> %s</li>\n'
                    '<li><strong>server time:</strong> %s</li>\n'
                    '</ul>\n' % (version, isotime()))
            if self.config['allowed_dir']:
                if self.show_names:
                    names = [(self.allowed[infohash]['name'], infohash)
                             for infohash in self.allowed]
                else:
                    names = [(None, infohash) for infohash in self.allowed]
            else:
                names = [(None, infohash) for infohash in self.downloads]
            if not names:
                s.write('<p>not tracking any files yet...</p>\n')
            else:
                names.sort()
                tn = 0
                tc = 0
                td = 0
                tt = 0  # Total transferred
                ts = 0  # Total size
                nf = 0  # Number of files displayed
                if self.config['allowed_dir'] and self.show_names:
                    s.write('<table summary="files" border="1">\n'
                            '<tr><th>info hash</th><th>torrent name</th>'
                            '<th align="right">size</th><th align="right">'
                            'complete</th><th align="right">downloading</th>'
                            '<th align="right">downloaded</th>'
                            '<th align="right">transferred</th></tr>\n')
                else:
                    s.write('<table summary="files">\n'
                            '<tr><th>info hash</th><th align="right">complete'
                            '</th><th align="right">downloading</th>'
                            '<th align="right">downloaded</th></tr>\n')
                for name, infohash in names:
                    l = self.downloads[infohash]
                    n = self.completed.get(infohash, 0)
                    tn = tn + n
                    c = self.seedcount[infohash]
                    tc = tc + c
                    d = len(l) - c
                    td = td + d
                    if self.config['allowed_dir'] and self.show_names:
                        if infohash in self.allowed:
                            nf = nf + 1
                            sz = self.allowed[infohash]['length']  # size
                            ts = ts + sz
                            szt = sz * n   # Transferred for this torrent
                            tt = tt + szt
                            if self.allow_get == 1:
                                linkname = '<a href="/file?info_hash=' + \
                                    urllib.parse.quote(infohash) + '">' + \
                                    name + '</a>'
                            else:
                                linkname = name
                            s.write('<tr><td><code>%s</code></td><td>%s</td>'
                                    '<td align="right">%s</td>'
                                    '<td align="right">%i</td>'
                                    '<td align="right">%i</td>'
                                    '<td align="right">%i</td>'
                                    '<td align="right">%s</td></tr>\n' %
                                    (hexlify(infohash).decode(), linkname,
                                     formatSize(sz), c, d, n, formatSize(szt)))
                    else:
                        s.write('<tr><td><code>%s</code></td>'
                                '<td align="right"><code>%i</code></td>'
                                '<td align="right"><code>%i</code></td>'
                                '<td align="right"><code>%i</code></td>'
                                '</tr>\n' % (hexlify(infohash).decode(), c, d,
                                             n))
                if self.config['allowed_dir'] and self.show_names:
                    s.write('<tr><td align="right" colspan="2">%i files</td>'
                            '<td align="right">%s</td><td align="right">%i'
                            '</td><td align="right">%i</td><td align="right">'
                            '%i</td><td align="right">%s</td></tr>\n' %
                            (nf, formatSize(ts), tc, td, tn, formatSize(tt)))
                else:
                    s.write('<tr><td align="right">%i files</td>'
                            '<td align="right">%i</td><td align="right">%i'
                            '</td><td align="right">%i</td></tr>\n' %
                            (nf, tc, td, tn))
                s.write('</table>\n<ul>\n'
                        '<li><em>info hash:</em> SHA1 hash of the "info" '
                        'section of the metainfo (*.torrent)</li>\n'
                        '<li><em>complete:</em> number of connected clients '
                        'with the complete file</li>\n'
                        '<li><em>downloading:</em> number of connected clients'
                        ' still downloading</li>\n'
                        '<li><em>downloaded:</em> reported complete downloads'
                        '</li>\n'
                        '<li><em>transferred:</em> torrent size * total '
                        'downloaded (does not include partial '
                        'transfers)</li>\n</ul>\n')

            s.write('<h2>Peers</h2>')
            s.write('<textarea cols=128 readonly>{}</textarea>'.format(
                    self.state['peers']))
            s.write('<h2>Cache</h2>')
            s.write('<textarea cols=128 readonly>{}</textarea>'.format(
                    self.becache))
            s.write('</body>\n</html>\n')
            return (200, 'OK',
                    {'Content-Type': 'text/html; charset=iso-8859-1'},
                    s.getvalue().encode())
        except Exception:
            print_exc()
            return (500, 'Internal Server Error',
                    {'Content-Type': 'text/html; charset=iso-8859-1'},
                    b'Server Error')

    def scrapedata(self, infohash, return_name=True):
        l = self.downloads[infohash]
        n = self.completed.get(infohash, 0)
        c = self.seedcount[infohash]
        d = len(l) - c
        f = {'complete': c, 'incomplete': d, 'downloaded': n}
        if return_name and self.show_names and self.config['allowed_dir']:
            f['name'] = self.allowed[infohash]['name']
        return f

    def get_scrape(self, paramslist):
        fs = {}
        if 'info_hash' in paramslist:
            if self.config['scrape_allowed'] not in ['specific', 'full']:
                return (400, 'Not Authorized', {'Content-Type': 'text/plain',
                                                'Pragma': 'no-cache'},
                        bencode({'failure reason': 'specific scrape function '
                                 'is not available with this tracker.'}))
            for infohash in paramslist['info_hash']:
                if self.allowed is not None:
                    if infohash in self.allowed:
                        fs[infohash] = self.scrapedata(infohash)
                elif infohash in self.downloads:
                    fs[infohash] = self.scrapedata(infohash)
        else:
            if self.config['scrape_allowed'] != 'full':
                return (400, 'Not Authorized', {'Content-Type': 'text/plain',
                                                'Pragma': 'no-cache'},
                        bencode({'failure reason': 'full scrape function is '
                                 'not available with this tracker.'}))
            if self.allowed is not None:
                keys = self.allowed.keys()
            else:
                keys = self.downloads.keys()
            for infohash in keys:
                fs[infohash] = self.scrapedata(infohash)

        return (200, 'OK', {'Content-Type': 'text/plain'},
                bencode({'files': fs}))

    def get_file(self, infohash):
        if not self.allow_get:
            return (400, 'Not Authorized', {'Content-Type': 'text/plain',
                                            'Pragma': 'no-cache'},
                    'get function is not available with this tracker.')
        if infohash not in self.allowed:
            return (404, 'Not Found', {'Content-Type': 'text/plain',
                                       'Pragma': 'no-cache'}, alas)
        fname = self.allowed[infohash]['file']
        fpath = self.allowed[infohash]['path']
        with open(fpath, 'rb') as handle:
            return (200, 'OK',
                    {'Content-Type': 'application/x-bittorrent',
                     'Content-Disposition': 'attachment; filename=' + fname},
                    handle.read())

    def check_allowed(self, infohash, paramslist):
        if self.aggregator_key is not None and not (
                'password' in paramslist and
                paramslist['password'][0] == self.aggregator_key):
            return (200, 'Not Authorized', {'Content-Type': 'text/plain',
                                            'Pragma': 'no-cache'},
                    bencode({'failure reason': 'Requested download is not '
                             'authorized for use with this tracker.'}))

        if self.allowed is not None:
            if infohash not in self.allowed:
                return (200, 'Not Authorized', {'Content-Type': 'text/plain',
                                                'Pragma': 'no-cache'},
                        bencode({'failure reason': 'Requested download is not '
                                 'authorized for use with this tracker.'}))
            if self.config['allowed_controls']:
                if 'failure reason' in self.allowed[infohash]:
                    return (
                        200, 'Not Authorized', {'Content-Type': 'text/plain',
                                                'Pragma': 'no-cache'},
                        bencode({'failure reason':
                                 self.allowed[infohash]['failure reason']}))

        if 'tracker' in paramslist:
            # turned off or contacted self
            if self.config['multitracker_allowed'] == 'none' or \
                    paramslist['peer_id'][0] == self.trackerid:
                return (200, 'Not Authorized', {'Content-Type': 'text/plain',
                                                'Pragma': 'no-cache'},
                        bencode({'failure reason': 'disallowed'}))

            if self.config['multitracker_allowed'] == 'autodetect' and \
                    'announce-list' not in self.allowed[infohash]:
                return (200, 'Not Authorized', {'Content-Type': 'text/plain',
                                                'Pragma': 'no-cache'},
                        bencode({'failure reason': 'Requested download is not '
                                 'authorized for multitracker use.'}))

        return None

    def add_data(self, infohash, event, ip, paramslist):
        peers = self.downloads.setdefault(infohash, {})
        ts = self.times.setdefault(infohash, {})
        self.completed.setdefault(infohash, 0)
        self.seedcount.setdefault(infohash, 0)

        def params(key, default=None, l=paramslist):
            if key in l:
                return l[key][0]
            return default

        peerid = params('peer_id', '')
        if len(peerid) != 20:
            raise ValueError('id not of length 20')
        if event not in ('started', 'completed', 'stopped', 'snooped', None):
            raise ValueError('invalid event')
        port = params('cryptoport')
        if port is None:
            port = params('port', 'missing port')
        try:
            port = Port(port)
        except (ValueError, OverflowError):
            raise ValueError('invalid port')
        left = int(params('left', 'amount left not sent'))
        if left < 0:
            raise ValueError('invalid amount left')
        seeding = left == 0
        # uploaded = long(params('uploaded',''))
        # downloaded = long(params('downloaded',''))
        supportcrypto = int(bool(params('supportcrypto')))
        requirecrypto = supportcrypto and int(bool(params('requirecrypto')))

        peer = peers.get(peerid)
        islocal = ip in local_IPs
        mykey = params('key')
        if peer:
            auth = peer.get('key', -1) == mykey or peer.get('ip') == ip

        gip = params('ip')
        override = is_valid_ip(gip) and (islocal or
                                         not self.only_local_override_ip)
        real_ip = gip if override else ip

        rsize = min(int(params('numwant', self.response_size)),
                    self.response_size)

        if event == 'stopped':
            if peer and auth:
                self.delete_peer(infohash, peerid)
            return rsize

        if peer is None:
            ts[peerid] = clock()
            peer = Peer(ip=ip, port=port, left=left,
                        supportcrypto=supportcrypto,
                        requirecrypto=requirecrypto)
            if mykey:
                peer['key'] = mykey
            if gip:
                peer['given ip'] = gip
            if port:
                if self.natcheck == 0 or islocal:
                    peer['nat'] = 0
                    self.becache[infohash].add_peer(peerid, peer, real_ip,
                                                    port)
                else:
                    NatCheck(self.connectback_result, infohash, peerid,
                             real_ip, port, self.rawserver,
                             encrypted=requirecrypto)
            else:
                peer['nat'] = 2 ** 30

            self.completed[infohash] += event == 'completed'
            self.seedcount[infohash] += seeding

            peers[peerid] = peer
            return rsize

        if not auth:
            return rsize    # return w/o changing stats

        ts[peerid] = clock()
        if seeding != (not peer['left']):  # Changing seeding state
            update = 1 if seeding else -1  # +1 if seeding, -1 if unseeding
            self.completed[infohash] += update
            self.seedcount[infohash] += update
            if not peer.get('nat', -1):
                # Swap leecher/seeder state in the cache
                self.becache[infohash].swap_peer(peerid, seeding)
        peer['left'] = left

        if port == 0:
            return rsize

        recheck = False
        if ip != peer['ip']:
            peer['ip'] = ip
            recheck = True
        if gip != peer.get('given ip'):
            if gip:
                peer['given ip'] = gip
            elif 'given ip' in peer:
                del peer['given ip']
            recheck = True

        natted = peer.get('nat', -1)
        if recheck:
            if natted == 0:
                self.becache[infohash].remove_peer(peerid, seeding)
            if natted >= 0:
                del peer['nat']     # restart NAT testing
        if natted and natted < self.natcheck:
            recheck = True

        if recheck:
            if not self.natcheck or islocal:
                peer['nat'] = 0
                self.becache[infohash].add_peer(peerid, peer, real_ip, port)
            else:
                NatCheck(self.connectback_result, infohash, peerid, real_ip,
                         port, self.rawserver, encrypted=requirecrypto)

        return rsize

    def peerlist(self, infohash, stopped, tracker, is_seed,
                 return_type, rsize, supportcrypto):
        # Returns: Response|CompactResponse
        #
        # This does not but should resort to Response for DNS/IPv6 addresses
        # even when compact response is requested
        compact = tracker or return_type < 3
        data = CompactResponse() if compact else Response()
        seeds = self.seedcount[infohash]
        data['complete'] = seeds
        data['incomplete'] = len(self.downloads[infohash]) - seeds

        if self.config['allowed_controls'] and \
                'warning message' in self.allowed[infohash]:
            data['warning message'] = self.allowed[infohash]['warning message']

        if tracker:
            data['interval'] = self.config['multitracker_reannounce_interval']
            if not rsize:
                return data
            cache = self.cached_t.setdefault(infohash, None)
            if not cache or len(cache[1]) < rsize or cache[0] + \
                    self.config['min_time_between_cache_refreshes'] < clock():
                bc = self.becache[infohash]
                cache = [clock(),
                         list(bc.plaintext.leechers.values()) +
                         list(bc.plaintext.seeds.values())]
                self.cached_t[infohash] = cache
                random.shuffle(cache[1])
                cache = cache[1]

            data['peers'] = cache[-rsize:]
            del cache[-rsize:]
            return data

        data['interval'] = self.reannounce_interval
        if stopped or not rsize:     # save some bandwidth
            data['peers'] = []
            return data

        bc = self.becache[infohash]
        len_l = len(bc.any_crypto.leechers)
        len_s = len(bc.any_crypto.seeds)
        if not len_l + len_s:   # caches are empty!
            data['peers'] = []
            return data
        l_get_size = int(float(rsize) * (len_l) / (len_l + len_s))
        cache = self.cached.setdefault(infohash,
                                       [None, None, None])[return_type]
        if cache and \
                (not cache[1] or is_seed and len(cache[1]) < rsize or
                 len(cache[1]) < l_get_size or
                 cache[0] + self.config['min_time_between_cache_refreshes'] <
                 self.cachetime):
            cache = None
        if cache is None:
            peers = self.downloads[infohash]
            if self.config['compact_reqd']:
                vv = ([], [], [])
            else:
                vv = ([], [], [], [], [])
            # empty if disabled
            for key, ip, port in self.t2tlist.harvest(infohash):
                if key not in peers:
                    cp = compact_peer_info(ip, port)
                    vv[0].append(cp)
                    vv[2].append((cp, False))
                    if not self.config['compact_reqd']:
                        vv[3].append({'ip': ip, 'port': port, 'peer id': key})
                        vv[4].append({'ip': ip, 'port': port})
            cache = [self.cachetime,
                     list(bc.get_peers(return_type).leechers.values()) +
                     vv[return_type],
                     list(bc.get_peers(return_type).seeds.values())]
            random.shuffle(cache[1])
            random.shuffle(cache[2])
            self.cached[infohash][return_type] = cache
            for rr, cached in enumerate(self.cached[infohash]):
                if rr != return_type:
                    try:
                        cached[1].extend(vv[rr])
                    except (IndexError, TypeError, AttributeError):
                        pass
        if len(cache[1]) < l_get_size:
            peerdata = cache[1]
            if not is_seed:
                peerdata.extend(cache[2])
            cache[1] = []
            cache[2] = []
        else:
            if not is_seed:
                peerdata = cache[2][l_get_size - rsize:]
                del cache[2][l_get_size - rsize:]
                rsize -= len(peerdata)
            else:
                peerdata = []
            if rsize:
                peerdata.extend(cache[1][-rsize:])
                del cache[1][-rsize:]
        if return_type == Return.crypto_none:
            data['peers'] = b''.join(peerdata)
        elif return_type == Return.crypto_required:
            data['crypto_flags'] = b'\x01' * len(peerdata)
            data['peers'] = b''.join(peerdata)
        elif return_type == Return.crypto_supported:
            data['crypto_flags'] = bytes(p[1] for p in peerdata)
            data['peers'] = b''.join(p[0] for p in peerdata)
        else:
            data['peers'] = peerdata
        return data

    def get(self, connection, path, headers):
        # Returns (int, str, {str: str}, bytes) or None
        real_ip = connection.get_ip()
        ip = real_ip
        try:
            ip = to_ipv4(ip)
            ipv4 = True
        except ValueError:
            ipv4 = False

        if self.allowed_IPs and ip not in self.allowed_IPs or \
                self.banned_IPs and ip in self.banned_IPs:
            return (400, 'Not Authorized', {'Content-Type': 'text/plain',
                                            'Pragma': 'no-cache'},
                    bencode({'failure reason':
                             'your IP is not allowed on this tracker'}))

        nip = get_forwarded_ip(headers)
        if nip and not self.only_local_override_ip:
            ip = nip
            try:
                ip = to_ipv4(ip)
                ipv4 = True
            except ValueError:
                ipv4 = False

        paramslist = {}

        def params(key, default=None, l=paramslist):
            if key in l:
                return l[key][0]
            return default

        try:
            (_, _, path, _, query, _) = urllib.parse.urlparse(path)
            if self.uq_broken == 1:
                path = path.replace('+', ' ')
                query = query.replace('+', ' ')
            path = urllib.parse.unquote(path)[1:]
            for subquery in query.split('&'):
                if subquery:
                    key, eql, val = subquery.partition('=')
                    key = urllib.parse.unquote(key)
                    if key in ('info_hash', 'peer_id'):
                        val = urllib.parse.unquote_to_bytes(val)
                    else:
                        val = urllib.parse.unquote(val)
                    paramslist.setdefault(key, []).append(val)

            if path in ('', 'index.html'):
                return self.get_infopage()
            if path == 'file':
                return self.get_file(params('info_hash'))
            if path == 'favicon.ico' and self.favicon is not None:
                return (200, 'OK', {'Content-Type': 'image/x-icon'},
                        self.favicon)

            # automated access from here on

            if path in ('scrape', 'scrape.php', 'tracker.php/scrape'):
                return self.get_scrape(paramslist)

            if path not in ('announce', 'announce.php',
                            'tracker.php/announce'):
                return (404, 'Not Found', {'Content-Type': 'text/plain',
                                           'Pragma': 'no-cache'}, alas)

            # main tracker function

            # filtered = self.Filter.check(real_ip, paramslist, headers)
            # if filtered:
            #     return (400, 'Not Authorized', {'Content-Type': 'text/plain',
            #                                     'Pragma': 'no-cache'},
            #             bencode({'failure reason': filtered}))

            infohash = params('info_hash')
            if not infohash:
                raise ValueError('no info hash')

            notallowed = self.check_allowed(infohash, paramslist)
            if notallowed:
                return notallowed

            event = params('event')

            rsize = self.add_data(infohash, event, ip, paramslist)

        except ValueError as e:
            return (400, 'Bad Request', {'Content-Type': 'text/plain'},
                    'you sent me garbage - {!s}'.format(e).encode())

        if self.aggregate_forward and 'tracker' not in paramslist:
            self.aggregate_senddata(query)

        if self.is_aggregator:      # don't return peer data here
            return (200, 'OK', {'Content-Type': 'text/plain',
                                'Pragma': 'no-cache'},
                    bencode({'response': 'OK'}))

        if int(params('compact', 0)) and ipv4:
            if int(params('requirecrypto', 0)):
                return_type = Return.crypto_required
            elif int(params('supportcrypto', 0)):
                return_type = Return.crypto_supported
            else:
                return_type = Return.crypto_none
        elif self.config['compact_reqd'] and ipv4:
            return (400, 'Bad Request', {'Content-Type': 'text/plain'},
                    'your client is outdated, please upgrade')
        elif int(params('no_peer_id', 0)):
            return_type = Return.no_peerid
        else:
            return_type = Return.with_peerid

        data = self.peerlist(infohash, event == 'stopped',
                             params('tracker'), not int(params('left', 1)),
                             return_type, rsize,
                             int(params('supportcrypto', 0)))

        if 'scrape' in paramslist:    # deprecated
            data['scrape'] = self.scrapedata(infohash, False)

        if self.dedicated_seed_id:
            if params('seed_id') == self.dedicated_seed_id and \
                    int(params('left', 1)) == 0:
                self.is_seeded[infohash] = True
            if int(params('check_seeded', 0)) and self.is_seeded.get(infohash):
                data['seeded'] = 1

        return (200, 'OK', {'Content-Type': 'text/plain',
                            'Pragma': 'no-cache'},
                bencode(data))

    def natchecklog(self, peerid, ip, port, result):
        year, month, day, hour, minute, second = time.localtime()[:6]
        print('%s - %s [%02d/%3s/%04d:%02d:%02d:%02d] "!natcheck-%s:%i" %i '
              '0 - -' % (ip, urllib.parse.quote(peerid), day, months[month],
                         year, hour, minute, second, ip, port, result))

    def connectback_result(self, result, downloadid, peerid, ip, port):
        record = self.downloads.get(downloadid, {}).get(peerid)
        if record is None or record['port'] != port or \
                record['ip'] != ip and record.get('given ip') != ip:
            if self.config['log_nat_checks']:
                self.natchecklog(peerid, ip, port, 404)
            return
        if self.config['log_nat_checks']:
            if result:
                x = 200
            else:
                x = 503
            self.natchecklog(peerid, ip, port, x)
        if 'nat' not in record:
            record['nat'] = int(not result)
            if result:
                self.becache[downloadid].add_peer(peerid, record, ip, port)
        elif result and record['nat']:
            record['nat'] = 0
            self.becache[downloadid].add_peer(peerid, record, ip, port)
        elif not result:
            record['nat'] += 1

    def remove_from_state(self, *keys):
        for key in keys:
            self.state.pop(key, None)

    def save_state(self):
        self.rawserver.add_task(self.save_state, self.save_dfile_interval)
        self.state.write(self.dfile)

    def parse_allowed(self):
        self.rawserver.add_task(self.parse_allowed, self.parse_dir_interval)

        if self.config['allowed_dir']:
            try:
                r = parsedir(self.config['allowed_dir'], self.allowed,
                             self.allowed_dir_files, self.allowed_dir_blocked,
                             [".torrent"])
            except (KeyError, IndexError):
                print('**warning** Error updating allowed torrents. '
                      'Reparsing.')
                r = parsedir(self.config['allowed_dir'], {}, {}, set(),
                             [".torrent"])

            (self.allowed, self.allowed_dir_files, self.allowed_dir_blocked,
                added) = r[:-1]

            self.state['allowed'] = self.allowed
            self.state['allowed_dir_files'] = self.allowed_dir_files

            self.t2tlist.parse(self.allowed)

        else:
            f = self.config['allowed_list']
            if self.allowed_list_mtime == os.path.getmtime(f):
                return
            try:
                r = parsetorrentlist(f, self.allowed)
                (self.allowed, added) = r
                self.state['allowed_list'] = self.allowed
            except (IOError, OSError):
                print('**warning** unable to read allowed torrent list')
                return
            self.allowed_list_mtime = os.path.getmtime(f)

        for infohash in added:
            self.downloads.setdefault(infohash, {})
            self.completed.setdefault(infohash, 0)
            self.seedcount.setdefault(infohash, 0)

    def read_ip_lists(self):
        self.rawserver.add_task(self.read_ip_lists, self.parse_dir_interval)

        f = self.config['allowed_ips']
        if f and self.allowed_ip_mtime != os.path.getmtime(f):
            self.allowed_IPs = AddrList()
            try:
                self.allowed_IPs.read_fieldlist(f)
                self.allowed_ip_mtime = os.path.getmtime(f)
            except (IOError, OSError):
                print('**warning** unable to read allowed_IP list')

        f = self.config['banned_ips']
        if f and self.banned_ip_mtime != os.path.getmtime(f):
            self.banned_IPs = AddrList()
            try:
                self.banned_IPs.read_rangelist(f)
                self.banned_ip_mtime = os.path.getmtime(f)
            except (IOError, OSError):
                print('**warning** unable to read banned_IP list')

    def delete_peer(self, infohash, peerid):
        dls = self.downloads[infohash]
        peer = dls[peerid]
        seeding = not peer['left']
        if seeding:
            self.seedcount[infohash] -= 1
        if not peer.get('nat', -1):
            self.becache[infohash].remove_peer(peerid, seeding)
        del self.times[infohash][peerid]
        del dls[peerid]

    def expire_downloaders(self):
        for infohash, peertimes in self.times.items():
            for peerid, t in list(peertimes.items()):
                if t < self.prevtime:
                    self.delete_peer(infohash, peerid)
        self.prevtime = clock()
        if not self.keep_dead:
            for infohash, peers in list(self.downloads.items()):
                if len(peers) == 0 and (self.allowed is None or
                                        infohash not in self.allowed):
                    del self.times[infohash]
                    del self.downloads[infohash]
                    del self.seedcount[infohash]
        self.rawserver.add_task(self.expire_downloaders,
                                self.timeout_downloaders_interval)


def track(args):
    if len(args) == 0:
        print(formatDefinitions(defaults, 80))
        return
    try:
        config, _ = parseargs(args, defaults, 0, 0)
    except ValueError as e:
        print('error: ', str(e))
        print('run with no arguments for parameter explanations')
        return
    r = RawServer(threading.Event(), config['timeout_check_interval'],
                  config['socket_timeout'], ipv6_enable=config['ipv6_enabled'])
    t = Tracker(config, r)
    r.bind(config['port'], config['bind'],
           reuse=True, ipv6_socket_style=config['ipv6_binds_v4'])
    r.listen_forever(
        HTTPHandler(t.get, config['min_time_between_log_flushes']))
    t.save_state()
    print('# Shutting down: ', isotime())
