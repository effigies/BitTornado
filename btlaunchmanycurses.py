#!/usr/bin/env python

# Written by John Hoffman
# see LICENSE.txt for license information

DOWNLOAD_SCROLL_RATE = 1

from BitTornado import PSYCO
if PSYCO.psyco:
    try:
        import psyco
        assert psyco.__version__ >= 0x010100f0
        psyco.full()
    except:
        pass

from BitTornado.launchmanycore import LaunchMany
from BitTornado.download_bt1 import defaults, get_usage
from BitTornado.parseargs import parseargs
from threading import Event
from sys import argv, exit
from time import time, localtime, strftime
import sys, os
from BitTornado import version, report_email
from BitTornado.ConfigDir import ConfigDir

try:
    import curses
    import curses.panel
    from curses.wrapper import wrapper as curses_wrapper
    from signal import signal, SIGWINCH 
except:
    print 'Textmode GUI initialization failed, cannot proceed.'
    print
    print 'This download interface requires the standard Python module ' \
       '"curses", which is unfortunately not available for the native ' \
       'Windows port of Python. It is however available for the Cygwin ' \
       'port of Python, running on all Win32 systems (www.cygwin.com).'
    print
    print 'You may still use "btdownloadheadless.py" to download.'
    sys.exit(1)

assert sys.version >= '2', "Install Python 2.0 or greater"
try:
    True
except:
    True = 1
    False = 0

Exceptions = []


def fmttime(n):
    if n <= 0:
        return None
    try:
        n = int(n)
        assert n < 5184000  # 60 days
    except:
        return 'connecting to peers'
    m, s = divmod(n, 60)
    h, m = divmod(m, 60)
    return 'ETA in %d:%02d:%02d' % (h, m, s)

def fmtsize(n):
    n = long(n)
    unit = [' B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']
    i = 0
    if (n > 999):
        i = 1
        while i + 1 < len(unit) and (n >> 10) >= 999:
            i += 1
            n >>= 10
        n = float(n) / (1 << 10)
    if i > 0:
        size = '%.1f' % n + '%s' % unit[i]
    else:
        size = '%.0f' % n + '%s' % unit[i]
    return size

def ljust(s, size):
    s = s[:size]
    return s + (' '*(size-len(s)))

def rjust(s, size):
    s = s[:size]
    return (' '*(size-len(s)))+s


class CursesDisplayer:
    def __init__(self, scrwin):
        self.messages = []
        self.scroll_pos = 0
        self.scroll_time = 0
        
        self.scrwin = scrwin
        signal(SIGWINCH, self.winch_handler)
        self.changeflag = Event()
        self._remake_window()

    def winch_handler(self, signum, stackframe):
        self.changeflag.set()
        curses.endwin()
        self.scrwin.refresh()
        self.scrwin = curses.newwin(0, 0, 0, 0)
        self._remake_window()
        self._display_messages()

    def _remake_window(self):
        self.scrh, self.scrw = self.scrwin.getmaxyx()
        self.scrpan = curses.panel.new_panel(self.scrwin)
        self.mainwinh = int(2*(self.scrh)/3)
        self.mainwinw = self.scrw - 4  # - 2 (bars) - 2 (spaces)
        self.mainwiny = 2         # + 1 (bar) + 1 (titles)
        self.mainwinx = 2         # + 1 (bar) + 1 (space)
        # + 1 to all windows so we can write at mainwinw

        self.mainwin = curses.newwin(self.mainwinh, self.mainwinw+1,
                                     self.mainwiny, self.mainwinx)
        self.mainpan = curses.panel.new_panel(self.mainwin)
        self.mainwin.scrollok(0)
        self.mainwin.nodelay(1)

        self.headerwin = curses.newwin(1, self.mainwinw+1,
                                       1, self.mainwinx)
        self.headerpan = curses.panel.new_panel(self.headerwin)
        self.headerwin.scrollok(0)

        self.totalwin = curses.newwin(1, self.mainwinw+1,
                                      self.mainwinh+1, self.mainwinx)
        self.totalpan = curses.panel.new_panel(self.totalwin)
        self.totalwin.scrollok(0)

        self.statuswinh = self.scrh-4-self.mainwinh
        self.statuswin = curses.newwin(self.statuswinh, self.mainwinw+1,
                                       self.mainwinh+3, self.mainwinx)
        self.statuspan = curses.panel.new_panel(self.statuswin)
        self.statuswin.scrollok(0)

        try:
            self.scrwin.border(ord('|'),ord('|'),ord('-'),ord('-'),ord(' '),ord(' '),ord(' '),ord(' '))
        except:
            pass
        self.headerwin.addnstr(0, 2, '#', self.mainwinw - 25, curses.A_BOLD)
        self.headerwin.addnstr(0, 4, 'Filename', self.mainwinw - 25, curses.A_BOLD)
        self.headerwin.addnstr(0, self.mainwinw - 24, 'Size', 4, curses.A_BOLD)
        self.headerwin.addnstr(0, self.mainwinw - 18, 'Download', 8, curses.A_BOLD)
        self.headerwin.addnstr(0, self.mainwinw -  6, 'Upload', 6, curses.A_BOLD)
        self.totalwin.addnstr(0, self.mainwinw - 27, 'Totals:', 7, curses.A_BOLD)

        self._display_messages()
        
        curses.panel.update_panels()
        curses.doupdate()
        self.changeflag.clear()


    def _display_line(self, s, bold = False):
        if self.disp_end:
            return True
        line = self.disp_line
        self.disp_line += 1
        if line < 0:
            return False
        if bold:
            self.mainwin.addnstr(line, 0, s, self.mainwinw, curses.A_BOLD)
        else:
            self.mainwin.addnstr(line, 0, s, self.mainwinw)
        if self.disp_line >= self.mainwinh:
            self.disp_end = True
        return self.disp_end

    def _display_data(self, data):    
        if 3*len(data) <= self.mainwinh:
            self.scroll_pos = 0
            self.scrolling = False
        elif self.scroll_time + DOWNLOAD_SCROLL_RATE < time():
            self.scroll_time = time()
            self.scroll_pos += 1
            self.scrolling = True
            if self.scroll_pos >= 3*len(data)+2:
                self.scroll_pos = 0

        i = int(self.scroll_pos/3)
        self.disp_line = (3*i)-self.scroll_pos
        self.disp_end = False

        while not self.disp_end:
            ii = i % len(data)
            if i and not ii:
                if not self.scrolling:
                    break
                self._display_line('')
                if self._display_line(''):
                    break
            ( name, status, progress, peers, seeds, seedsmsg, dist,
              uprate, dnrate, upamt, dnamt, size, t, msg ) = data[ii]
            t = fmttime(t)
            if t:
                status = t
            name = ljust(name,self.mainwinw-32)
            size = rjust(fmtsize(size),8)
            uprate = rjust('%s/s' % fmtsize(uprate),10)
            dnrate = rjust('%s/s' % fmtsize(dnrate),10)
            line = "%3d %s%s%s%s" % (ii+1, name, size, dnrate, uprate)
            self._display_line(line, True)
            if peers + seeds:
                datastr = '    (%s) %s - %s up %s dn - %s peers %s seeds %.3f dist copies' % (
                                progress, status,
                                fmtsize(upamt), fmtsize(dnamt),
                                peers, seeds, dist )
            else:
                datastr = '    (%s) %s - %s up %s dn' % (
                                progress, status,
                                fmtsize(upamt), fmtsize(dnamt) )
            self._display_line(datastr)
            self._display_line('    '+ljust(msg,self.mainwinw-4))
            i += 1

    def display(self, data):
        if self.changeflag.isSet():
            return

        inchar = self.mainwin.getch()
        if inchar == 12: # ^L
            self._remake_window()

        self.mainwin.erase()
        if data:
            self._display_data(data)
        else:
            self.mainwin.addnstr( 1, int(self.mainwinw/2)-5,
                                  'no torrents', 12, curses.A_BOLD )
        totalup = 0
        totaldn = 0
        for ( name, status, progress, peers, seeds, seedsmsg, dist,
              uprate, dnrate, upamt, dnamt, size, t, msg ) in data:
            totalup += uprate
            totaldn += dnrate
        
        totalup = '%s/s' % fmtsize(totalup)
        totaldn = '%s/s' % fmtsize(totaldn)
        
        self.totalwin.erase()
        self.totalwin.addnstr(0, self.mainwinw-27, 'Totals:', 7, curses.A_BOLD)
        self.totalwin.addnstr(0, self.mainwinw-20 + (10-len(totaldn)),
                              totaldn, 10, curses.A_BOLD)
        self.totalwin.addnstr(0, self.mainwinw-10 + (10-len(totalup)),
                              totalup, 10, curses.A_BOLD)

        curses.panel.update_panels()
        curses.doupdate()

        return inchar in (ord('q'),ord('Q'))

    def message(self, s):
        self.messages.append(strftime('%x %X - ',localtime(time()))+s)
        self._display_messages()

    def _display_messages(self):
        self.statuswin.erase()
        winpos = 0
        for s in self.messages[-self.statuswinh:]:
            self.statuswin.addnstr(winpos, 0, s, self.mainwinw)
            winpos += 1
        curses.panel.update_panels()
        curses.doupdate()

    def exception(self, s):
        Exceptions.append(s)
        self.message('SYSTEM ERROR - EXCEPTION GENERATED')



def LaunchManyWrapper(scrwin, config):
    LaunchMany(config, CursesDisplayer(scrwin))


if __name__ == '__main__':
    if argv[1:] == ['--version']:
        print version
        exit(0)
    defaults.extend( [
        ( 'parse_dir_interval', 60,
          "how often to rescan the torrent directory, in seconds" ),
        ( 'saveas_style', 2,
          "How to name torrent downloads (1 = rename to torrent name, " +
          "2 = save under name in torrent, 3 = save in directory under torrent name)" ),
        ( 'display_path', 0,
          "whether to display the full path or the torrent contents for each torrent" ),
    ] )
    try:
        configdir = ConfigDir('launchmanycurses')
        defaultsToIgnore = ['responsefile', 'url', 'priority']
        configdir.setDefaults(defaults,defaultsToIgnore)
        configdefaults = configdir.loadConfig()
        defaults.append(('save_options',0,
         "whether to save the current options as the new default configuration " +
         "(only for btlaunchmanycurses.py)"))
        if len(argv) < 2:
            print "Usage: btlaunchmanycurses.py <directory> <global options>\n"
            print "<directory> - directory to look for .torrent files (semi-recursive)"
            print get_usage(defaults, 80, configdefaults)
            exit(1)
        config, args = parseargs(argv[1:], defaults, 1, 1, configdefaults)
        if config['save_options']:
            configdir.saveConfig(config)
        configdir.deleteOldCacheData(config['expire_cache_data'])
        if not os.path.isdir(args[0]):
            raise ValueError("Warning: "+args[0]+" is not a directory")
        config['torrent_dir'] = args[0]
    except ValueError, e:
        print 'error: ' + str(e) + '\nrun with no args for parameter explanations'
        exit(1)

    curses_wrapper(LaunchManyWrapper, config)
    if Exceptions:
        print '\nEXCEPTION:'
        print Exceptions[0]
        print 'please report this to '+report_email
