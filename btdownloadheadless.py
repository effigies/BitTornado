#!/usr/bin/env python3

# Written by Bram Cohen
# see LICENSE.txt for license information

import sys
import os
import time
import random
import socket
import hashlib
import threading
from BitTornado.Client.download_bt1 import BT1Download, defaults, \
    parse_params, get_usage, get_metainfo
from BitTornado.Network.RawServer import RawServer
from BitTornado.Network.SocketHandler import UPnP_ERROR
from BitTornado.Meta.bencode import bencode
from BitTornado.Network.natpunch import UPnP_test
from BitTornado.clock import clock
from BitTornado import version
from BitTornado.Application.ConfigDir import ConfigDir
from BitTornado.Application.NumberFormats import formatIntText
from BitTornado.Application.PeerID import createPeerID

PROFILER = False


class HeadlessDisplayer:
    def __init__(self):
        self.done = False
        self.file = ''
        self.percentDone = ''
        self.timeEst = ''
        self.downloadTo = ''
        self.downRate = ''
        self.upRate = ''
        self.shareRating = ''
        self.seedStatus = ''
        self.peerStatus = ''
        self.errors = []
        self.last_update_time = -1

    def finished(self):
        self.done = True
        self.percentDone = '100'
        self.timeEst = 'Download Succeeded!'
        self.downRate = ''
        self.display()

    def failed(self):
        self.done = True
        self.percentDone = '0'
        self.timeEst = 'Download Failed!'
        self.downRate = ''
        self.display()

    def error(self, errormsg):
        self.errors.append(errormsg)
        self.display()

    def display(self, dpflag=threading.Event(), fractionDone=None,
                timeEst=None, downRate=None, upRate=None, activity=None,
                statistics=None, **kws):
        if self.last_update_time + 0.1 > clock() and \
                fractionDone not in (0.0, 1.0) and activity is not None:
            return
        self.last_update_time = clock()
        if fractionDone is not None:
            self.percentDone = str(float(int(fractionDone * 1000)) / 10)
        if timeEst is not None:
            self.timeEst = formatIntText(timeEst)
        if activity is not None and not self.done:
            self.timeEst = activity
        if downRate is not None:
            self.downRate = '%.1f kB/s' % (float(downRate) / (1 << 10))
        if upRate is not None:
            self.upRate = '%.1f kB/s' % (float(upRate) / (1 << 10))
        if statistics is not None:
            self.shareRating = '{}   ({:.1f} MB up / {:.1f} MB down)'.format(
                '{:.3f}'.format(statistics.shareRating)
                if 0 <= statistics.shareRating <= 100 else 'oo',
                float(statistics.upTotal) / (1 << 20),
                float(statistics.downTotal) / (1 << 20))

            if not self.done:
                self.seedStatus = '{:d} seen now, plus {:.3f} distributed ' \
                    'copies'.format(statistics.numSeeds,
                                    statistics.numCopies)
            else:
                self.seedStatus = '{:d} seen recently, plus {:.3f} ' \
                    'distributed copies'.format(statistics.numOldSeeds,
                                                statistics.numCopies)
            self.peerStatus = '{:d} seen now, {:.1%} done at {:.1f} kB/s' \
                ''.format(statistics.numPeers,
                          statistics.percentDone / 100,
                          float(statistics.torrentRate) / (1 << 10))
        print('\n\n\n\n')
        for err in self.errors:
            print('ERROR:\n' + err + '\n')
        print('saving:        ', self.file)
        print('percent done:  ', self.percentDone)
        print('time left:     ', self.timeEst)
        print('download to:   ', self.downloadTo)
        print('download rate: ', self.downRate)
        print('upload rate:   ', self.upRate)
        print('share rating:  ', self.shareRating)
        print('seed status:   ', self.seedStatus)
        print('peer status:   ', self.peerStatus)
        sys.stdout.flush()
        dpflag.set()

    def chooseFile(self, default, size, saveas, dir):
        self.file = '%s (%.1f MB)' % (default, float(size) / (1 << 20))
        if saveas != '':
            default = saveas
        self.downloadTo = os.path.abspath(default)
        return default

    def newpath(self, path):
        self.downloadTo = path


def run(params):
    h = HeadlessDisplayer()
    while 1:
        configdir = ConfigDir('downloadheadless')
        defaultsToIgnore = ['metafile', 'url', 'priority']
        configdir.setDefaults(defaults, defaultsToIgnore)
        configdefaults = configdir.loadConfig()
        defaults.append(
            ('save_options', 0, 'whether to save the current options as the '
             'new default configuration (only for btdownloadheadless.py)'))
        try:
            config = parse_params(params, configdefaults)
        except ValueError as e:
            print('error: {}\n'.format(e),
                  'run with no args for parameter explanations')
            break
        if not config:
            print(get_usage(defaults, 80, configdefaults))
            break
        if config['save_options']:
            configdir.saveConfig(config)
        configdir.deleteOldCacheData(config['expire_cache_data'])

        myid = createPeerID()
        random.seed(myid)

        doneflag = threading.Event()

        def disp_exception(text):
            print(text)
        rawserver = RawServer(
            doneflag, config['timeout_check_interval'], config['timeout'],
            ipv6_enable=config['ipv6_enabled'], failfunc=h.failed,
            errorfunc=disp_exception)
        upnp_type = UPnP_test(config['upnp_nat_access'])
        while True:
            try:
                listen_port = rawserver.find_and_bind(
                    config['minport'], config['maxport'], config['bind'],
                    ipv6_socket_style=config['ipv6_binds_v4'],
                    upnp=upnp_type, randomizer=config['random_port'])
                break
            except socket.error as e:
                if upnp_type and e == UPnP_ERROR:
                    print('WARNING: COULD NOT FORWARD VIA UPnP')
                    upnp_type = 0
                    continue
                print("error: Couldn't listen - ", e)
                h.failed()
                return

        metainfo = get_metainfo(config['metafile'], config['url'], h.error)
        if not metainfo:
            break

        infohash = hashlib.sha1(bencode(metainfo['info'])).digest()

        dow = BT1Download(
            h.display, h.finished, h.error, disp_exception, doneflag, config,
            metainfo, infohash, myid, rawserver, listen_port, configdir)

        if not dow.saveAs(h.chooseFile, h.newpath):
            break

        if not dow.initFiles(old_style=True):
            break
        if not dow.startEngine():
            dow.shutdown()
            break
        dow.startRerequester()
        dow.autoStats()

        if not dow.am_I_finished():
            h.display(activity='connecting to peers')
        rawserver.listen_forever(dow.getPortHandler())
        h.display(activity='shutting down')
        dow.shutdown()
        break
    try:
        rawserver.shutdown()
    except Exception:
        pass
    if not h.done:
        h.failed()

if __name__ == '__main__':
    if sys.argv[1:] == ['--version']:
        print(version)
        sys.exit(0)

    if PROFILER:
        import profile
        import pstats
        p = profile.Profile()
        p.runcall(run, sys.argv[1:])
        log_fname = 'profile_data.' + time.strftime('%y%m%d%H%M%S') + '.txt'
        with open(log_fname, 'a') as log:
            normalstdout, sys.stdout = sys.stdout, log
            pstats.Stats(p).strip_dirs().sort_stats('time').print_stats()
            sys.stdout = normalstdout
    else:
        run(sys.argv[1:])
