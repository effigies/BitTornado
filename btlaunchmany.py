#!/usr/bin/env python3

# Written by John Hoffman
# see LICENSE.txt for license information

import sys
import os
from BitTornado.Client.launchmanycore import LaunchMany
from BitTornado.Client.download_bt1 import defaults, get_usage
from BitTornado.Application.parseargs import parseargs
from BitTornado import version, report_url
from BitTornado.Application.ConfigDir import ConfigDir


Exceptions = []


class HeadlessDisplayer:
    def display(self, data):
        print()
        if not data:
            self.message('no torrents')
        for x in data:
            (name, status, progress, peers, seeds, seedsmsg, dist,
             uprate, dnrate, upamt, dnamt, size, t, msg) = x
            print('"{}": "{}" ({}) - {}P{}{}{:.3f}D u{:0.1f}K/s-d{:0.1f}K/s '
                  'u{:d}K-d{:d}K "{}"'.format(
                      name, status, progress, peers, seeds, seedsmsg, dist,
                      uprate // 1000, dnrate // 1000, upamt // 1024,
                      dnamt // 1024, msg))
        return False

    def message(self, s):
        print("### ", s)

    def exception(self, s):
        Exceptions.append(s)
        self.message('SYSTEM ERROR - EXCEPTION GENERATED')


if __name__ == '__main__':
    if sys.argv[1:] == ['--version']:
        print(version)
        sys.exit(0)
    defaults.extend([
        ('parse_dir_interval', 60,
         "how often to rescan the torrent directory, in seconds"),
        ('saveas_style', 1, 'How to name torrent downloads (1 = rename to '
         'torrent name, 2 = save under name in torrent, 3 = save in directory '
         'under torrent name)'),
        ('display_path', 1, 'whether to display the full path or the torrent '
         'contents for each torrent'),
    ])
    try:
        configdir = ConfigDir('launchmany')
        defaultsToIgnore = ['responsefile', 'url', 'priority']
        configdir.setDefaults(defaults, defaultsToIgnore)
        configdefaults = configdir.loadConfig()
        defaults.append(
            ('save_options', 0, 'whether to save the current options as the '
             'new default configuration (only for btlaunchmany.py)'))
        if len(sys.argv) < 2:
            print("Usage: btlaunchmany.py <directory> <global options>\n"
                  "<directory> - directory to look for .torrent files "
                  "(semi-recursive)")
            print(get_usage(defaults, 80, configdefaults))
            sys.exit(1)
        config, args = parseargs(sys.argv[1:], defaults, 1, 1, configdefaults)
        if config['save_options']:
            configdir.saveConfig(config)
        configdir.deleteOldCacheData(config['expire_cache_data'])
        if not os.path.isdir(args[0]):
            raise ValueError("Warning: " + args[0] + " is not a directory")
        config['torrent_dir'] = args[0]
    except ValueError as e:
        print('error: {}\nrun with no args for parameter explanations'
              ''.format(e))
        sys.exit(1)

    LaunchMany(config, HeadlessDisplayer())
    if Exceptions:
        print('\nEXCEPTION:')
        print(Exceptions[0])
        print('please report this to ' + report_url)
