#!/usr/bin/env python

# Written by Bram Cohen
# modified for multitracker by John Hoffman
# see LICENSE.txt for license information

import sys
import os
import threading
from traceback import print_exc
from BitTornado.Application.makemetafile import make_meta_file, completedir
from BitTornado.Meta.Info import MetaInfo
try:
    import wx
except ImportError:
    print 'wxPython is not installed or has not been installed properly.'
    sys.exit(1)

wxEVT_INVOKE = wx.NewEventType()


def EVT_INVOKE(win, func):
    win.Connect(-1, -1, wxEVT_INVOKE, func)


class InvokeEvent(wx.PyEvent):
    def __init__(self, func, args, kwargs):
        super(InvokeEvent, self).__init__()
        self.SetEventType(wxEVT_INVOKE)
        self.func = func
        self.args = args
        self.kwargs = kwargs


class DownloadInfo:
    def __init__(self):
        frame = wx.Frame(None, -1, 'BitTorrent Torrent File Maker',
                         size=wx.Size(550, 410))
        self.frame = frame

        panel = wx.Panel(frame, -1)

        gridSizer = wx.FlexGridSizer(cols=2, rows=2, vgap=0, hgap=8)

        gridSizer.Add(wx.StaticText(panel, -1, 'make torrent of:'))

        b = wx.BoxSizer(wx.HORIZONTAL)
        self.dirCtl = wx.TextCtrl(panel, -1, '')
        b.Add(self.dirCtl, 1, wx.EXPAND)

        button = wx.Button(panel, -1, 'dir', size=(30, 20))
        wx.EVT_BUTTON(frame, button.GetId(), self.selectdir)
        b.Add(button, 0)

        button2 = wx.Button(panel, -1, 'file', size=(30, 20))
        wx.EVT_BUTTON(frame, button2.GetId(), self.selectfile)
        b.Add(button2, 0)

        gridSizer.Add(b, 0, wx.EXPAND)
        gridSizer.Add(wx.StaticText(panel, -1, ''))
        gridSizer.Add(wx.StaticText(panel, -1, ''))

        gridSizer.Add(wx.StaticText(panel, -1, 'announce url:'))
        self.annCtl = wx.TextCtrl(panel, -1, 'http://my.tracker:6969/announce')
        gridSizer.Add(self.annCtl, 0, wx.EXPAND)
        gridSizer.Add(wx.StaticText(panel, -1, ''))
        gridSizer.Add(wx.StaticText(panel, -1, ''))

        annList = wx.FlexGridSizer(cols=1)
        annList.Add(wx.StaticText(panel, -1, 'announce list:'))
        annList.Add(wx.StaticText(panel, -1, ''))
        abutton = wx.Button(panel, -1, 'copy\nannounces\nfrom\ntorrent',
                            size=(50, 70))
        wx.EVT_BUTTON(frame, abutton.GetId(), self.announcecopy)
        annList.Add(abutton, 0, wx.EXPAND)
        gridSizer.Add(annList, 0, wx.EXPAND)

        self.annListCtl = wx.TextCtrl(panel, -1, '\n\n\n\n\n',
                                      wx.Point(-1, -1), (400, 120),
                                      wx.TE_MULTILINE | wx.HSCROLL |
                                      wx.TE_DONTWRAP)
        gridSizer.Add(self.annListCtl, -1, wx.EXPAND)

        gridSizer.Add(wx.StaticText(panel, -1, ''))
        exptext = wx.StaticText(panel, -1, 'a list of announces separated by '
                                'commas or whitespace and on several lines -\n'
                                'trackers on the same line will be tried '
                                'randomly, and all the trackers on one line\n'
                                'will be tried before the trackers on the '
                                'next line.')
        exptext.SetFont(wx.Font(6, wx.DEFAULT, wx.NORMAL, wx.NORMAL, False))
        gridSizer.Add(exptext)

        gridSizer.Add(wx.StaticText(panel, -1, ''))
        gridSizer.Add(wx.StaticText(panel, -1, ''))

        gridSizer.Add(wx.StaticText(panel, -1, 'piece size:'))
        self.piece_length = wx.Choice(panel, -1,
                                      choices=['automatic', '2MiB', '1MiB',
                                               '512KiB', '256KiB', '128KiB',
                                               '64KiB', '32KiB'])
        self.piece_length_list = [0, 21, 20, 19, 18, 17, 16, 15]
        self.piece_length.SetSelection(0)
        gridSizer.Add(self.piece_length)

        gridSizer.Add(wx.StaticText(panel, -1, ''))
        gridSizer.Add(wx.StaticText(panel, -1, ''))

        gridSizer.Add(wx.StaticText(panel, -1, 'comment:'))
        self.commentCtl = wx.TextCtrl(panel, -1, '')
        gridSizer.Add(self.commentCtl, 0, wx.EXPAND)

        gridSizer.AddGrowableCol(1)

        border = wx.BoxSizer(wx.VERTICAL)
        border.Add(gridSizer, 0, wx.EXPAND | wx.NORTH | wx.EAST | wx.WEST, 25)
        b2 = wx.Button(panel, -1, 'make')
        border.Add(b2, 0, wx.ALIGN_CENTER | wx.SOUTH, 20)
        wx.EVT_BUTTON(frame, b2.GetId(), self.complete)
        panel.SetSizer(border)
        panel.SetAutoLayout(True)

    def selectdir(self, x):
        dl = wx.DirDialog(
            self.frame, style=wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        if dl.ShowModal() == wx.ID_OK:
            self.dirCtl.SetValue(dl.GetPath())

    def selectfile(self, x):
        dl = wx.FileDialog(self.frame, 'Choose file or directory to use', '',
                           '', '', wx.OPEN)
        if dl.ShowModal() == wx.ID_OK:
            self.dirCtl.SetValue(dl.GetPath())

    def selectdrop(self, x):
        print x

        # list = x.m_files
        self.dirCtl.SetValue(x[0])

    def announcecopy(self, x):
        dl = wx.FileDialog(self.frame, 'Choose .torrent file to use', '', '',
                           '*.torrent', wx.OPEN)
        if dl.ShowModal() == wx.ID_OK:
            try:
                metainfo = MetaInfo.read(dl.GetPath())
                self.annCtl.SetValue(metainfo['announce'])
                if 'announce-list' in metainfo:
                    self.annListCtl.SetValue(
                        '\n'.join(', '.join(tier) for tier in
                                  metainfo['announce-list']) + '\n' * 3)
                else:
                    self.annListCtl.SetValue('')
            except (IOError, ValueError):
                return

    def getannouncelist(self):
        annList = filter(bool, self.annListCtl.GetValue().split('\n'))
        return [filter(bool, tier.replace(',', ' ').split())
                for tier in annList]

    def complete(self, x):
        if self.dirCtl.GetValue() == '':
            dlg = wx.MessageDialog(
                self.frame, message='You must select a\n file or directory',
                caption='Error', style=wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return
        params = {
            'piece_size_pow2': self.piece_length_list[
                self.piece_length.GetSelection()]
        }
        annlist = self.getannouncelist()
        if len(annlist) > 0:
            params['real_announce_list'] = annlist
        comment = self.commentCtl.GetValue()
        if comment != '':
            params['comment'] = comment
        try:
            CompleteDir(self.dirCtl.GetValue(), self.annCtl.GetValue(), params)
        except Exception:
            print_exc()


class CompleteDir:
    def __init__(self, dirname, announce, params):
        self.dirname = dirname
        self.announce = announce
        self.params = params
        self.flag = threading.Event()
        self.separatetorrents = False

        if os.path.isdir(dirname):
            self.choicemade = threading.Event()
            frame = wx.Frame(None, -1, 'BitTorrent make torrent', size=(1, 1))
            self.frame = frame
            panel = wx.Panel(frame, -1)
            gridSizer = wx.FlexGridSizer(cols=1, vgap=8, hgap=8)
            gridSizer.AddGrowableRow(1)
            gridSizer.Add(wx.StaticText(
                panel, -1, 'Do you want to make a separate .torrent'), 0,
                wx.ALIGN_CENTER)
            gridSizer.Add(wx.StaticText(
                panel, -1, 'for every item in this directory?'), 0,
                wx.ALIGN_CENTER)
            gridSizer.Add(wx.StaticText(panel, -1, ''))

            b = wx.FlexGridSizer(cols=3, hgap=10)
            yesbut = wx.Button(panel, -1, 'Yes')

            def saidyes(e, self=self):
                self.frame.Destroy()
                self.separatetorrents = True
                self.begin()
            wx.EVT_BUTTON(frame, yesbut.GetId(), saidyes)
            b.Add(yesbut, 0)

            nobut = wx.Button(panel, -1, 'No')

            def saidno(e, self=self):
                self.frame.Destroy()
                self.begin()
            wx.EVT_BUTTON(frame, nobut.GetId(), saidno)
            b.Add(nobut, 0)

            cancelbut = wx.Button(panel, -1, 'Cancel')

            def canceled(e, self=self):
                self.frame.Destroy()
            wx.EVT_BUTTON(frame, cancelbut.GetId(), canceled)
            b.Add(cancelbut, 0)
            gridSizer.Add(b, 0, wx.ALIGN_CENTER)
            border = wx.BoxSizer(wx.HORIZONTAL)
            border.Add(gridSizer, 1, wx.EXPAND | wx.ALL, 4)

            panel.SetSizer(border)
            panel.SetAutoLayout(True)
            frame.Show()
            border.Fit(panel)
            frame.Fit()

        else:
            self.begin()

    def begin(self):
        if self.separatetorrents:
            frame = wx.Frame(None, -1, 'BitTorrent make directory',
                             size=wx.Size(550, 250))
        else:
            frame = wx.Frame(None, -1, 'BitTorrent make torrent',
                             size=wx.Size(550, 250))
        self.frame = frame

        panel = wx.Panel(frame, -1)
        gridSizer = wx.FlexGridSizer(cols=1, vgap=15, hgap=8)

        if self.separatetorrents:
            label = 'checking file sizes'
        else:
            label = 'building {}.torrent'.format(self.dirname)
        self.currentLabel = wx.StaticText(panel, -1, label)

        gridSizer.Add(self.currentLabel, 0, wx.EXPAND)
        self.gauge = wx.Gauge(panel, -1, range=1000, style=wx.GA_SMOOTH)
        gridSizer.Add(self.gauge, 0, wx.EXPAND)
        gridSizer.Add((10, 10), 1, wx.EXPAND)
        self.button = wx.Button(panel, -1, 'cancel')
        gridSizer.Add(self.button, 0, wx.ALIGN_CENTER)
        gridSizer.AddGrowableRow(2)
        gridSizer.AddGrowableCol(0)

        g2 = wx.FlexGridSizer(cols=1, vgap=15, hgap=8)
        g2.Add(gridSizer, 1, wx.EXPAND | wx.ALL, 25)
        g2.AddGrowableRow(0)
        g2.AddGrowableCol(0)
        panel.SetSizer(g2)
        panel.SetAutoLayout(True)
        wx.EVT_BUTTON(frame, self.button.GetId(), self.done)
        wx.EVT_CLOSE(frame, self.done)
        EVT_INVOKE(frame, self.onInvoke)
        frame.Show(True)
        threading.Thread(target=self.complete).start()

    def complete(self):
        try:
            if self.separatetorrents:
                completedir(self.dirname, self.announce, self.params,
                            self.flag, self.valcallback, self.filecallback)
            else:
                make_meta_file(self.dirname, self.announce, self.params,
                               self.flag, self.valcallback)
            if not self.flag.isSet():
                self.currentLabel.SetLabel('Done!')
                self.gauge.SetValue(1000)
                self.button.SetLabel('Close')
                self.frame.Refresh()
        except (OSError, IOError) as e:
            self.currentLabel.SetLabel('Error!')
            self.button.SetLabel('Close')
            dlg = wx.MessageDialog(
                self.frame, message='Error - ' + str(e), caption='Error',
                style=wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()

    def valcallback(self, amount):
        self.invokeLater(self.onval, [amount])

    def onval(self, amount):
        self.gauge.SetValue(int(amount * 1000))

    def filecallback(self, fname):
        self.invokeLater(self.onfile, [fname])

    def onfile(self, fname):
        path = os.path.join(self.dirname, fname)
        self.currentLabel.SetLabel('building {}.torrent'.format(path))

    def onInvoke(self, event):
        if not self.flag.isSet():
            event.func(*event.args, **event.kwargs)

    def invokeLater(self, func, args=[], kwargs={}):
        if not self.flag.isSet():
            wx.PostEvent(self.frame, InvokeEvent(func, args, kwargs))

    def done(self, event):
        self.flag.set()
        self.frame.Destroy()


class btWxApp(wx.App):
    def OnInit(self):
        d = DownloadInfo()
        d.frame.Show(True)
        self.SetTopWindow(d.frame)
        return True

if __name__ == '__main__':
    btWxApp().MainLoop()
