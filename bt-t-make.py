#!/usr/bin/env python

# Written by Bram Cohen
# modified for multitracker by John Hoffman
# see LICENSE.txt for license information

import sys
import os
import shutil
import threading
import traceback
from BitTornado.Application.makemetafile import make_meta_file
from BitTornado.Meta.Info import MetaInfo

try:
    import wx
except ImportError:
    print 'wxPython is not installed or has not been installed properly.'
    sys.exit(1)
from BitTornado.Application.GUI import DelayedEvents, callback

basepath = os.path.abspath(os.path.dirname(sys.argv[0]))

if sys.platform == 'win32':
    DROP_HERE = '(drop here)'
else:
    DROP_HERE = ''


class BasicDownloadInfo(DelayedEvents):
    def __init__(self, config, calls):
        self.config = config
        self.calls = calls

        self.cancelflag = threading.Event()
        self.switchlock = threading.Lock()
        self.working = False
        self.queue = []
        wx.InitAllImageHandlers()
        self.thostselection = self.calls['getCurrentTHost']()
        self.thostselectnum = 0
        self.choices = None
        self.choices1 = None
        self.announce = ''
        self.announce_list = None

        self.windowStyle = wx.SYSTEM_MENU | wx.CAPTION | wx.MINIMIZE_BOX
        if self.config['stayontop']:
            self.windowStyle |= wx.STAY_ON_TOP
        frame = wx.Frame(None, -1, 'T-Make', size=wx.Size(-1, -1),
                         style=self.windowStyle)
        self.frame = frame
        panel = wx.Panel(frame, -1)
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        groupSizer = wx.FlexGridSizer(cols=1, vgap=0, hgap=0)
#        self.dropTarget = self.calls['newDropTarget']((200, 200))
        self.dropTarget = self.calls['newDropTarget']()
        self.dropTargetPtr = wx.StaticBitmap(panel, -1, self.dropTarget)
        self.calls['setDropTargetRefresh'](self.dropTargetPtr.Refresh)
        self.dropTargetWidth = self.dropTarget.GetWidth()
        wx.EVT_LEFT_DOWN(self.dropTargetPtr, self.dropTargetClick)
        wx.EVT_ENTER_WINDOW(self.dropTargetPtr,
                            self.calls['dropTargetHovered'])
        wx.EVT_LEAVE_WINDOW(self.dropTargetPtr,
                            self.calls['dropTargetUnhovered'])
        groupSizer.Add(self.dropTargetPtr, 0, wx.ALIGN_CENTER)
        lowerSizer1 = wx.GridSizer(cols=6)
        dirlink = wx.StaticText(panel, -1, 'dir')
        dirlink.SetFont(wx.Font(7, wx.DEFAULT, wx.NORMAL, wx.NORMAL, True))
        dirlink.SetForegroundColour('blue')
        wx.EVT_LEFT_UP(dirlink, self.selectdir)
        lowerSizer1.Add(dirlink, -1, wx.ALIGN_LEFT)
        lowerSizer1.Add(wx.StaticText(panel, -1, ''), -1, wx.ALIGN_CENTER)
        lowerSizer1.Add(wx.StaticText(panel, -1, ''), -1, wx.ALIGN_CENTER)
        lowerSizer1.Add(wx.StaticText(panel, -1, ''), -1, wx.ALIGN_CENTER)
        lowerSizer1.Add(wx.StaticText(panel, -1, ''), -1, wx.ALIGN_CENTER)
        filelink = wx.StaticText(panel, -1, 'file')
        filelink.SetFont(wx.Font(7, wx.DEFAULT, wx.NORMAL, wx.NORMAL, True))
        filelink.SetForegroundColour('blue')
        wx.EVT_LEFT_UP(filelink, self.selectfile)
        lowerSizer1.Add(filelink, -1, wx.ALIGN_RIGHT)

        groupSizer.Add(lowerSizer1, -1, wx.ALIGN_CENTER)

        self.gauge = wx.Gauge(panel, -1, range=1000, style=wx.GA_HORIZONTAL,
                              size=(-1, 15))
        groupSizer.Add(self.gauge, 0, wx.EXPAND)
        self.statustext = wx.StaticText(panel, -1, 'ready',
                                        style=wx.ALIGN_CENTER |
                                        wx.ST_NO_AUTORESIZE)
        self.statustext.SetFont(wx.Font(7, wx.DEFAULT, wx.NORMAL, wx.BOLD,
                                        False))
        groupSizer.Add(self.statustext, -1, wx.EXPAND)
        self.choices = wx.Choice(panel, -1, (-1, -1),
                                 (self.dropTargetWidth, -1), choices=[])
        self.choices.SetFont(wx.Font(7, wx.DEFAULT, wx.NORMAL, wx.NORMAL,
                                     False))
        wx.EVT_CHOICE(self.choices, -1, self.set_thost)
        groupSizer.Add(self.choices, 0, wx.EXPAND)
        cancellink = wx.StaticText(panel, -1, 'cancel')
        cancellink.SetFont(wx.Font(7, wx.DEFAULT, wx.NORMAL, wx.NORMAL, True))
        cancellink.SetForegroundColour('red')
        wx.EVT_LEFT_UP(cancellink, self.cancel)
        groupSizer.Add(cancellink, -1, wx.ALIGN_CENTER)
        advlink = wx.StaticText(panel, -1, 'advanced')
        advlink.SetFont(wx.Font(7, wx.DEFAULT, wx.NORMAL, wx.NORMAL, True))
        advlink.SetForegroundColour('blue')
        wx.EVT_LEFT_UP(advlink, self.calls['switchToAdvanced'])
        groupSizer.Add(advlink, -1, wx.ALIGN_CENTER)
        mainSizer.Add(groupSizer, 0, wx.ALIGN_CENTER)

        self.refresh_thostlist()
        self._set_thost()

        if sys.platform == 'win32':
            self.dropTargetPtr.DragAcceptFiles(True)
            wx.EVT_DROP_FILES(self.dropTargetPtr, self.selectdrop)

#        border = wxBoxSizer(wxHORIZONTAL)
#        border.Add(mainSizer, 1, wxEXPAND | wxALL, 0)
        panel.SetSizer(mainSizer)
        panel.SetAutoLayout(True)
#        border.Fit(panel)
        mainSizer.Fit(panel)
        frame.Fit()
        frame.Show(True)

        super(BasicDownloadInfo, self).__init__(frame)
        wx.EVT_CLOSE(frame, self._close)

    def selectdir(self, x=None):
        self.calls['dropTargetHovered']()
        dl = wx.DirDialog(
            self.frame, style=wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        if dl.ShowModal() == wx.ID_OK:
            self.calls['dropTargetDropped']()
            self.complete(dl.GetPath())
        else:
            self.calls['dropTargetUnhovered']()

    def selectfile(self, x=None):
        self.calls['dropTargetHovered']()
        dl = wx.FileDialog(self.frame, 'Choose file to use', style=wx.OPEN)
        if dl.ShowModal() == wx.ID_OK:
            self.calls['dropTargetDropped']()
            self.complete(dl.GetPath())
        else:
            self.calls['dropTargetUnhovered']()

    def selectdrop(self, dat):
        self.calls['dropTargetDropped']()
        for f in dat.GetFiles():
            self.complete(f)

    def _announcecopy(self, f):
        try:
            metainfo = MetaInfo.read(f)
            self.announce = metainfo['announce']
            self.announce_list = metainfo.get('announce-list')
        except (IOError, ValueError):
            return

    def complete(self, x):
        params = {'piece_size_pow2': 0}
        if self.announce_list:
            params['real_announce_list'] = self.announce_list
        self.queue.append((x, self.announce, params))
        self.go_queue()

    def go_queue(self):
        with self.switchlock:
            if self.queue and not self.working:
                self.working = True
                self.statustext.SetLabel('working')
                q = self.queue.pop(0)
                MakeMetafile(q[0], q[1], q[2], self)

    def cancel(self, x):
        with self.switchlock:
            if self.working:
                self.working = False
                self.cancelflag.set()
                self.cancelflag = threading.Event()
                self.queue = []
                self.statustext.SetLabel('CANCELED')
                self.calls['dropTargetError']()

    def dropTargetClick(self, x):
        if x.GetPosition()[0] < int(self.dropTargetWidth * 0.4):
            self.selectdir()
        elif x.GetPosition()[0] > int(self.dropTargetWidth * 0.6):
            self.selectfile()

    def refresh_thostlist(self):
        l = []
        d = 0
        for f in os.listdir(os.path.join(basepath, 'thosts')):
            if f[-6:].lower() == '.thost':
                l.append(f)
                if f == self.thostselection:
                    d = len(l)
        self.choices.Clear()
        if not d:
            if l:
                self.thostselection = l[0]
                d = 1
            else:
                self.thostselection = ''
                d = 1
            self.config['thost'] = self.thostselection
            self.calls['saveConfig']()
        for f in l:
            self.choices.Append(f[:-6])
        self.thostselectnum = d - 1
        self.thostlist = l
        self.choices.SetSelection(d - 1)
        return

    def set_thost(self, x):
        n = self.choices.GetSelection()
        if n != self.thostselectnum:
            self.thostselectnum = n
            if n:
                self.thostselection = self.thostlist[n - 1]

    def _set_thost(self):
        self._announcecopy(os.path.join(basepath, 'thosts',
                                        self.thostselection))
        self.calls['setCurrentTHost'](self.thostselection)

    @callback
    def build_setgauge(self, x):
        self.gauge.SetValue(int(x * 1000))

    @callback
    def build_done(self):
        self.gauge.SetValue(0)
        self.statustext.SetLabel('done!')
        self.calls['dropTargetSuccess']()
        self.working = False
        self.go_queue()

    @callback
    def build_failed(self, e):
        dlg = wx.MessageDialog(self.frame, message='Error - ' + e,
                               caption='Error', style=wx.OK | wx.ICON_ERROR)
        dlg.ShowModal()
        dlg.Destroy()
        self.gauge.SetValue(0)
        self.statustext.SetLabel('ERROR')
        self.calls['dropTargetError']()
        self.working = False
        self.go_queue()

    def close(self):
        self.cancelflag = None   # this is a planned switch, don't cancel
        self.uiflag.set()
        self.frame.Close()

    def _close(self, x=None):
        self.uiflag.set()
        try:
            self.cancelflag.set()
        except AttributeError:
            pass
        self.frame.Destroy()


class AdvancedDownloadInfo(DelayedEvents):
    def __init__(self, config, calls):
        self.config = config
        self.calls = calls

        self.cancelflag = threading.Event()
        self.switchlock = threading.Lock()
        self.working = False
        self.queue = []
        wx.InitAllImageHandlers()
        self.thostselection = self.calls['getCurrentTHost']()
        self.thostselectnum = 0
        self.choices = None
        self.choices1 = None

        self.windowStyle = wx.SYSTEM_MENU | wx.CAPTION | wx.MINIMIZE_BOX
        if self.config['stayontop']:
            self.windowStyle |= wx.STAY_ON_TOP
        frame = wx.Frame(None, -1, 'T-Make', size=wx.Size(-1, -1),
                         style=self.windowStyle)
        self.frame = frame
        panel = wx.Panel(frame, -1)

        fullSizer = wx.FlexGridSizer(cols=1, vgap=0, hgap=8)

        colSizer = wx.FlexGridSizer(cols=2, vgap=0, hgap=8)
        leftSizer = wx.FlexGridSizer(cols=1, vgap=3)

        self.stayontop_checkbox = wx.CheckBox(panel, -1, "stay on top")
        self.stayontop_checkbox.SetValue(self.config['stayontop'])
        wx.EVT_CHECKBOX(frame, self.stayontop_checkbox.GetId(),
                        self.setstayontop)
        leftSizer.Add(self.stayontop_checkbox, -1, wx.ALIGN_CENTER)
        leftSizer.Add(wx.StaticText(panel, -1, ''))

        button = wx.Button(panel, -1, 'use image...')
        wx.EVT_BUTTON(frame, button.GetId(), self.selectDropTarget)
        leftSizer.Add(button, -1, wx.ALIGN_CENTER)

        self.groupSizer1Box = wx.StaticBox(panel, -1, '')
        groupSizer1 = wx.StaticBoxSizer(self.groupSizer1Box, wx.HORIZONTAL)
        groupSizer = wx.FlexGridSizer(cols=1, vgap=0)
        self.dropTarget = self.calls['newDropTarget']((200, 200))
#        self.dropTarget = self.calls['newDropTarget']()
        self.dropTargetPtr = wx.StaticBitmap(panel, -1, self.dropTarget)
        self.calls['setDropTargetRefresh'](self.dropTargetPtr.Refresh)
        self.dropTargetWidth = self.dropTarget.GetWidth()
        wx.EVT_LEFT_DOWN(self.dropTargetPtr, self.dropTargetClick)
        wx.EVT_ENTER_WINDOW(self.dropTargetPtr,
                            self.calls['dropTargetHovered'])
        wx.EVT_LEAVE_WINDOW(self.dropTargetPtr,
                            self.calls['dropTargetUnhovered'])
        groupSizer.Add(self.dropTargetPtr, 0, wx.ALIGN_CENTER)
        lowerSizer1 = wx.GridSizer(cols=3)
        dirlink = wx.StaticText(panel, -1, 'dir')
        dirlink.SetFont(wx.Font(7, wx.DEFAULT, wx.NORMAL, wx.NORMAL, True))
        dirlink.SetForegroundColour('blue')
        wx.EVT_LEFT_UP(dirlink, self.selectdir)
        lowerSizer1.Add(dirlink, -1, wx.ALIGN_LEFT)
        lowerSizer1.Add(wx.StaticText(panel, -1, ''), -1, wx.ALIGN_CENTER)
        filelink = wx.StaticText(panel, -1, 'file')
        filelink.SetFont(wx.Font(7, wx.DEFAULT, wx.NORMAL, wx.NORMAL, True))
        filelink.SetForegroundColour('blue')
        wx.EVT_LEFT_UP(filelink, self.selectfile)
        lowerSizer1.Add(filelink, -1, wx.ALIGN_RIGHT)

        groupSizer.Add(lowerSizer1, -1, wx.ALIGN_CENTER)

        self.gauge = wx.Gauge(panel, -1, range=1000, style=wx.GA_HORIZONTAL,
                              size=(-1, 15))
        groupSizer.Add(self.gauge, 0, wx.EXPAND)
        self.statustext = wx.StaticText(panel, -1, 'ready',
                                        style=wx.ALIGN_CENTER |
                                        wx.ST_NO_AUTORESIZE)
        self.statustext.SetFont(wx.Font(7, wx.DEFAULT, wx.NORMAL, wx.BOLD,
                                        False))
        groupSizer.Add(self.statustext, -1, wx.EXPAND)
        self.choices = wx.Choice(panel, -1, (-1, -1),
                                 (self.dropTargetWidth, -1), choices=[])
        self.choices.SetFont(wx.Font(7, wx.DEFAULT, wx.NORMAL, wx.NORMAL,
                                     False))
        wx.EVT_CHOICE(self.choices, -1, self.set_thost)
        groupSizer.Add(self.choices, 0, wx.EXPAND)
        cancellink = wx.StaticText(panel, -1, 'cancel')
        cancellink.SetFont(wx.Font(7, wx.DEFAULT, wx.NORMAL, wx.NORMAL, True))
        cancellink.SetForegroundColour('red')
        wx.EVT_LEFT_UP(cancellink, self.cancel)
        groupSizer.Add(cancellink, -1, wx.ALIGN_CENTER)
        dummyadvlink = wx.StaticText(panel, -1, 'advanced')
        dummyadvlink.SetFont(wx.Font(7, wx.DEFAULT, wx.NORMAL, wx.NORMAL,
                                     False))
        dummyadvlink.SetForegroundColour('blue')
        wx.EVT_LEFT_UP(dirlink, self.selectdir)
        groupSizer.Add(dummyadvlink, -1, wx.ALIGN_CENTER)
        groupSizer1.Add(groupSizer)
        leftSizer.Add(groupSizer1, -1, wx.ALIGN_CENTER)

        leftSizer.Add(wx.StaticText(panel, -1, 'make torrent of:'), 0,
                      wx.ALIGN_CENTER)

        self.dirCtl = wx.TextCtrl(panel, -1, '', size=(250, -1))
        leftSizer.Add(self.dirCtl, 1, wx.EXPAND)

        b = wx.BoxSizer(wx.HORIZONTAL)
        button = wx.Button(panel, -1, 'dir')
        wx.EVT_BUTTON(frame, button.GetId(), self.selectdir)
        b.Add(button, 0)

        button2 = wx.Button(panel, -1, 'file')
        wx.EVT_BUTTON(frame, button2.GetId(), self.selectfile)
        b.Add(button2, 0)

        leftSizer.Add(b, 0, wx.ALIGN_CENTER)

        leftSizer.Add(wx.StaticText(panel, -1, ''))

        simple_link = wx.StaticText(panel, -1, 'back to basic mode')
        simple_link.SetFont(wx.Font(-1, wx.DEFAULT, wx.NORMAL, wx.NORMAL,
                                    True))
        simple_link.SetForegroundColour('blue')
        wx.EVT_LEFT_UP(simple_link, self.calls['switchToBasic'])
        leftSizer.Add(simple_link, -1, wx.ALIGN_CENTER)

        colSizer.Add(leftSizer, -1, wx.ALIGN_CENTER_VERTICAL)

        gridSizer = wx.FlexGridSizer(cols=2, vgap=6, hgap=8)

        gridSizer.Add(wx.StaticText(panel, -1, 'Torrent host:'), -1,
                      wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)

        self.choices1 = wx.Choice(panel, -1, (-1, -1), (-1, -1), choices=[])
        wx.EVT_CHOICE(self.choices1, -1, self.set_thost1)
        gridSizer.Add(self.choices1, 0, wx.EXPAND)

        b = wx.BoxSizer(wx.HORIZONTAL)
        button1 = wx.Button(panel, -1, 'set default')
        wx.EVT_BUTTON(frame, button1.GetId(), self.set_default_thost)
        b.Add(button1, 0)
        b.Add(wx.StaticText(panel, -1, '       '))
        button2 = wx.Button(panel, -1, 'delete')
        wx.EVT_BUTTON(frame, button2.GetId(), self.delete_thost)
        b.Add(button2, 0)
        b.Add(wx.StaticText(panel, -1, '       '))
        button3 = wx.Button(panel, -1, 'save as...')
        wx.EVT_BUTTON(frame, button3.GetId(), self.save_thost)
        b.Add(button3, 0)

        gridSizer.Add(wx.StaticText(panel, -1, ''))
        gridSizer.Add(b, 0, wx.ALIGN_CENTER)

        gridSizer.Add(wx.StaticText(panel, -1, ''))
        gridSizer.Add(wx.StaticText(panel, -1, ''))

        gridSizer.Add(wx.StaticText(panel, -1, 'single tracker url:'), 0,
                      wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        self.annCtl = wx.TextCtrl(panel, -1, 'http://my.tracker:6969/announce')
        gridSizer.Add(self.annCtl, 0, wx.EXPAND)

        a = wx.FlexGridSizer(cols=1, vgap=3)
        a.Add(wx.StaticText(panel, -1, 'tracker list:'), 0, wx.ALIGN_RIGHT)
        a.Add(wx.StaticText(panel, -1, ''))
        abutton = wx.Button(panel, -1, 'copy\nannounces\nfrom\ntorrent',
                            size=(70, 70))
        wx.EVT_BUTTON(frame, abutton.GetId(), self.announcecopy)
        a.Add(abutton, -1, wx.ALIGN_CENTER)
        a.Add(wx.StaticText(panel, -1, DROP_HERE), -1, wx.ALIGN_CENTER)
        gridSizer.Add(a, -1, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)

        self.annListCtl = wx.TextCtrl(panel, -1, '\n', wx.Point(-1, -1),
                                      (300, 120), wx.TE_MULTILINE |
                                      wx.HSCROLL | wx.TE_DONTWRAP)
        gridSizer.Add(self.annListCtl, -1, wx.EXPAND)

        gridSizer.Add(wx.StaticText(panel, -1, ''))
        exptext = wx.StaticText(panel, -1, 'a list of tracker urls separated '
                                'by commas or whitespace\nand on several '
                                'lines -trackers on the same line will be\n'
                                'tried randomly, and all the trackers on one '
                                'line\nwill be tried before the trackers on '
                                'the next line.')
        exptext.SetFont(wx.Font(6, wx.DEFAULT, wx.NORMAL, wx.NORMAL, False))
        gridSizer.Add(exptext, -1, wx.ALIGN_CENTER)

        self.refresh_thostlist()
        self._set_thost()

        if sys.platform == 'win32':
            self.dropTargetPtr.DragAcceptFiles(True)
            wx.EVT_DROP_FILES(self.dropTargetPtr, self.selectdrop)
            self.groupSizer1Box.DragAcceptFiles(True)
            wx.EVT_DROP_FILES(self.groupSizer1Box, self.selectdrop)
            abutton.DragAcceptFiles(True)
            wx.EVT_DROP_FILES(abutton, self.announcedrop)
            self.annCtl.DragAcceptFiles(True)
            wx.EVT_DROP_FILES(self.annCtl, self.announcedrop)
            self.annListCtl.DragAcceptFiles(True)
            wx.EVT_DROP_FILES(self.annListCtl, self.announcedrop)

        gridSizer.Add(wx.StaticText(panel, -1, ''))
        gridSizer.Add(wx.StaticText(panel, -1, ''))

        gridSizer.Add(wx.StaticText(panel, -1, 'piece size:'), 0,
                      wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        self.piece_length = wx.Choice(panel, -1,
                                      choices=['automatic', '2MiB', '1MiB',
                                               '512KiB', '256KiB', '128KiB',
                                               '64KiB', '32KiB'])
        self.piece_length_list = [0, 21, 20, 19, 18, 17, 16, 15]
        self.piece_length.SetSelection(0)
        gridSizer.Add(self.piece_length)

        gridSizer.Add(wx.StaticText(panel, -1, 'comment:'), 0,
                      wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        self.commentCtl = wx.TextCtrl(panel, -1, '')
        gridSizer.Add(self.commentCtl, 0, wx.EXPAND)

        gridSizer.Add(wx.StaticText(panel, -1, ''))
        gridSizer.Add(wx.StaticText(panel, -1, ''))

        b1 = wx.Button(panel, -1, 'Cancel', size=(-1, 30))
        wx.EVT_BUTTON(frame, b1.GetId(), self.cancel)
        gridSizer.Add(b1, 0, wx.EXPAND)
        b2 = wx.Button(panel, -1, 'MAKE TORRENT', size=(-1, 30))
        wx.EVT_BUTTON(frame, b2.GetId(), self.complete)
        gridSizer.Add(b2, 0, wx.EXPAND)

        gridSizer.AddGrowableCol(1)
        colSizer.Add(gridSizer, -1, wx.ALIGN_CENTER_VERTICAL)
        fullSizer.Add(colSizer)

        border = wx.BoxSizer(wx.HORIZONTAL)
        border.Add(fullSizer, 1, wx.EXPAND | wx.ALL, 15)
        panel.SetSizer(border)
        panel.SetAutoLayout(True)
        border.Fit(panel)
        frame.Fit()
        frame.Show(True)

        super(AdvancedDownloadInfo, self).__init__(frame)
        wx.EVT_CLOSE(frame, self._close)

    def setstayontop(self, x):
        if self.stayontop_checkbox.GetValue():
            self.windowStyle |= wx.STAY_ON_TOP
        else:
            self.windowStyle &= ~wx.STAY_ON_TOP
        self.frame.SetWindowStyle(self.windowStyle)
        self.config['stayontop'] = self.stayontop_checkbox.GetValue()

    def selectdir(self, x=None):
        self.calls['dropTargetHovered']()
        dl = wx.DirDialog(self.frame,
                          style=wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        if dl.ShowModal() == wx.ID_OK:
            self.dirCtl.SetValue(dl.GetPath())
            self.calls['dropTargetDropped']()
        else:
            self.calls['dropTargetUnhovered']()

    def selectfile(self, x=None):
        self.calls['dropTargetHovered']()
        dl = wx.FileDialog(self.frame, 'Choose file to use', style=wx.OPEN)
        if dl.ShowModal() == wx.ID_OK:
            self.dirCtl.SetValue(dl.GetPath())
            self.calls['dropTargetDropped']()
        else:
            self.calls['dropTargetUnhovered']()

    def selectdrop(self, dat):
        self.calls['dropTargetDropped']()
        for f in dat.GetFiles():
            self.complete(f)

    def announcecopy(self, x):
        dl = wx.FileDialog(self.frame, 'Choose .torrent file to use',
                           wildcard='*.torrent', style=wx.OPEN)
        if dl.ShowModal() == wx.ID_OK:
            self._announcecopy(dl.GetPath(), True)

    def announcedrop(self, dat):
        self._announcecopy(dat.GetFiles()[0], True)

    def _announcecopy(self, f, external=False):
        try:
            metainfo = MetaInfo.read(f)
            self.annCtl.SetValue(metainfo['announce'])
            if 'announce-list' in metainfo:
                self.annListCtl.SetValue('\n'.join(', '.join(tier)
                                         for tier in metainfo['announce-list'])
                                         )
            else:
                self.annListCtl.SetValue('')
            if external:
                self.choices.SetSelection(0)
                self.choices1.SetSelection(0)
        except (IOError, ValueError):
            return

    def getannouncelist(self):
        annList = filter(bool, self.annListCtl.GetValue().split('\n'))
        return [filter(bool, tier.replace(', ', ' ').split())
                for tier in annList]

    def complete(self, x):
        if not self.dirCtl.GetValue():
            dlg = wx.MessageDialog(
                self.frame, message='You must select a\nfile or directory',
                caption='Error', style=wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return
        if not self.annCtl.GetValue():
            dlg = wx.MessageDialog(
                self.frame, message='You must specify a\nsingle tracker url',
                caption='Error', style=wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return
        params = {'piece_size_pow2':
                  self.piece_length_list[self.piece_length.GetSelection()]}
        annlist = self.getannouncelist()
        if len(annlist) > 0:
            warnings = ''
            for tier in annlist:
                if len(tier) > 1:
                    warnings += (
                        'WARNING: You should not specify multiple trackers\n'
                        '     on the same line of the tracker list unless\n'
                        '     you are certain they share peer data.\n')
                    break
            if not self.annCtl.GetValue() in annlist[0]:
                    warnings += (
                        'WARNING: The single tracker url is not present in\n'
                        '     the first line of the tracker list.  This\n'
                        '     may produce a dysfunctional torrent.\n')
            if warnings:
                warnings += ('Are you sure you wish to produce a .torrent\n'
                             'with these parameters?')
                dlg = wx.MessageDialog(self.frame, message=warnings,
                                       caption='Warning',
                                       style=wx.YES_NO | wx.ICON_QUESTION)
                if dlg.ShowModal() != wx.ID_YES:
                    dlg.Destroy()
                    return
            params['real_announce_list'] = annlist
        comment = self.commentCtl.GetValue()
        if comment != '':
            params['comment'] = comment
        self.statustext.SetLabel('working')
        self.queue.append((self.dirCtl.GetValue(), self.annCtl.GetValue(),
                           params))
        self.go_queue()

    def go_queue(self):
        with self.switchlock:
            if self.queue and not self.working:
                self.working = True
                self.statustext.SetLabel('working')
                q = self.queue.pop(0)
                MakeMetafile(q[0], q[1], q[2], self)

    def cancel(self, x):
        with self.switchlock:
            if self.working:
                self.working = False
                self.cancelflag.set()
                self.cancelflag = threading.Event()
                self.queue = []
                self.statustext.SetLabel('CANCELED')
                self.calls['dropTargetError']()

    def selectDropTarget(self, x):
        dl = wx.FileDialog(self.frame, 'Choose image to use',
                           os.path.join(basepath, 'targets'),
                           os.path.join(basepath, 'targets',
                                        self.config['target']),
                           'Supported images (*.bmp, *.gif)|*.*',
                           style=wx.OPEN | wx.HIDE_READONLY)
        if dl.ShowModal() == wx.ID_OK:
            try:
                self.calls['changeDropTarget'](dl.GetPath())
                self.config['target'] = dl.GetPath()
            except Exception:
                pass

    def dropTargetClick(self, x):
        if x.GetPosition()[0] < int(self.dropTargetWidth * 0.4):
            self.selectdir()
        elif x.GetPosition()[0] > int(self.dropTargetWidth * 0.6):
            self.selectfile()

    def refresh_thostlist(self):
        l = []
        d = 0
        for f in os.listdir(os.path.join(basepath, 'thosts')):
            if f[-6:].lower() == '.thost':
                l.append(f)
                if f == self.thostselection:
                    d = len(l)
        self.choices.Clear()
        self.choices.Append(' ')
        self.choices1.Clear()
        self.choices1.Append('---')
        if not d:
            if l:
                self.thostselection = l[0]
                d = 1
            else:
                self.thostselection = ''
                d = 0
            self.config['thost'] = self.thostselection
        for f in l:
            f1 = f[:-6]
            self.choices.Append(f1)
            if f == self.config['thost']:
                f1 += ' (default)'
            self.choices1.Append(f1)
        self.thostselectnum = d
        self.thostlist = l
        self.choices.SetSelection(d)
        self.choices1.SetSelection(d)

    def set_thost(self, x):
        n = self.choices.GetSelection()
        if n != self.thostselectnum:
            self.thostselectnum = n
            self.choices1.SetSelection(n)
            if n:
                self.thostselection = self.thostlist[n - 1]
                self._set_thost()

    def set_thost1(self, x):
        n = self.choices1.GetSelection()
        if n != self.thostselectnum:
            self.thostselectnum = n
            self.choices.SetSelection(n)
            if n:
                self.thostselection = self.thostlist[n - 1]
                self._set_thost()

    def _set_thost(self):
        self._announcecopy(os.path.join(basepath, 'thosts',
                                        self.thostselection))
        self.calls['setCurrentTHost'](self.thostselection)

    def set_default_thost(self, x):
        if self.thostlist:
            self.config['thost'] = self.thostselection
            self.refresh_thostlist()

    def save_thost(self, x):
        if not self.annCtl.GetValue():
            dlg = wx.MessageDialog(
                self.frame, message='You must specify a\nsingle tracker url',
                caption='Error', style=wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return
        try:
            metainfo = {}
            metainfo['announce'] = self.annCtl.GetValue()
            annlist = self.getannouncelist()
            if len(annlist) > 0:
                warnings = ''
                for tier in annlist:
                    if len(tier) > 1:
                        warnings += 'WARNING: You should not specify ' \
                            'multiple trackers\n     on the same line of ' \
                            'the tracker list unless\n     you are certain ' \
                            'they share peer data.\n'
                        break
                if not self.annCtl.GetValue() in annlist[0]:
                        warnings += 'WARNING: The single tracker url is not ' \
                            'present in\n     the first line of the tracker ' \
                            'list.  This\n     may produce a dysfunctional ' \
                            'torrent.\n'
                if warnings:
                    warnings += 'Are you sure you wish to save a torrent ' \
                        'host\nwith these parameters?'
                    dlg = wx.MessageDialog(
                        self.frame, message=warnings, caption='Warning',
                        style=wx.YES_NO | wx.ICON_QUESTION)
                    if dlg.ShowModal() != wx.ID_YES:
                        dlg.Destroy()
                        return
                metainfo['announce-list'] = annlist
        except Exception:
            return

        if self.thostselectnum:
            d = self.thostselection
        else:
            d = '.thost'
        dl = wx.FileDialog(self.frame, 'Save tracker data as',
                           os.path.join(basepath, 'thosts'), d, '*.thost',
                           wx.SAVE | wx.OVERWRITE_PROMPT)
        if dl.ShowModal() != wx.ID_OK:
            return
        d = dl.GetPath()

        try:
            metainfo.write(d)
            self.thostselection = os.path.basename(d)
        except IOError:
            pass
        self.refresh_thostlist()

    def delete_thost(self, x):
        dlg = wx.MessageDialog(
            self.frame, message='Are you sure you want to delete\n' +
            self.thostselection[:-6] + '?', caption='Warning',
            style=wx.YES_NO | wx.ICON_EXCLAMATION)
        if dlg.ShowModal() != wx.ID_YES:
            dlg.Destroy()
            return
        dlg.Destroy()
        os.remove(os.path.join(basepath, 'thosts', self.thostselection))
        self.thostselection = None
        self.refresh_thostlist()

    @callback
    def build_setgauge(self, x):
        self.gauge.SetValue(int(x * 1000))

    @callback
    def build_done(self):
        self.gauge.SetValue(0)
        self.statustext.SetLabel('done!')
        self.calls['dropTargetSuccess']()
        self.working = False
        self.go_queue()

    @callback
    def build_failed(self, e):
        self.gauge.SetValue(0)
        self.statustext.SetLabel('ERROR')
        self.calls['dropTargetError']()
        self.working = False
        self.go_queue()

    def close(self):
        self.cancelflag = None   # this is a planned switch, don't cancel
        self.uiflag.set()
        self.frame.Close()

    def _close(self, x=None):
        self.uiflag.set()
        try:
            self.cancelflag.set()
        except AttributeError:
            pass
        self.calls['saveConfig']()
        self.frame.Destroy()


class MakeMetafile:
    def __init__(self, d, a, params, external=None):
        self.d = d
        self.a = a
        self.params = params

        self.call = external
#        self.uiflag = external.uiflag
        self.uiflag = external.cancelflag
        threading.Thread(target=self.complete).start()

    def complete(self):
        try:
            make_meta_file(self.d, self.a, self.params, self.uiflag,
                           self.call.build_setgauge, progress_percent=1)
            if not self.uiflag.isSet():
                self.call.build_done()
        except (OSError, IOError) as e:
            self.failed(e)
        except Exception as e:
            traceback.print_exc()
            self.failed(e)

    def failed(self, e):
        e = str(e)
        self.call.build_failed(e)


class T_make:
    def __init__(self):
        self.configobj = wx.Config('BitTorrent_T-make',
                                   style=wx.CONFIG_USE_LOCAL_FILE)
        self.getConfig()
        self.currentTHost = self.config['thost']
#        self.d = AdvancedDownloadInfo(self.config, self.getCalls())
        self.d = BasicDownloadInfo(self.config, self.getCalls())

    def getConfig(self):
        config = {}
        try:
            config['stayontop'] = self.configobj.ReadInt('stayontop', True)
        except Exception:
            config['stayontop'] = True
            self.configobj.WriteInt('stayontop', True)
        try:
            config['target'] = self.configobj.Read('target', 'default.gif')
        except Exception:
            config['target'] = 'default.gif'
            self.configobj.Write('target', 'default.gif')
        try:
            config['thost'] = self.configobj.Read('thost', '')
        except Exception:
            config['thost'] = ''
            self.configobj.Write('thost', '')
        self.configobj.Flush()
        self.config = config

    def saveConfig(self):
        self.configobj.WriteInt('stayontop', self.config['stayontop'])
        self.configobj.Write('target', self.config['target'])
        self.configobj.Write('thost', self.config['thost'])
        self.configobj.Flush()

    def getCalls(self):
        calls = {}
        calls['saveConfig'] = self.saveConfig
        calls['newDropTarget'] = self.newDropTarget
        calls['setDropTargetRefresh'] = self.setDropTargetRefresh
        calls['changeDropTarget'] = self.changeDropTarget
        calls['setCurrentTHost'] = self.setCurrentTHost
        calls['getCurrentTHost'] = self.getCurrentTHost
        calls['dropTargetHovered'] = self.dropTargetHovered
        calls['dropTargetUnhovered'] = self.dropTargetUnhovered
        calls['dropTargetDropped'] = self.dropTargetDropped
        calls['dropTargetSuccess'] = self.dropTargetSuccess
        calls['dropTargetError'] = self.dropTargetError
        calls['switchToBasic'] = self.switchToBasic
        calls['switchToAdvanced'] = self.switchToAdvanced
        return calls

    def setCurrentTHost(self, x):
        self.currentTHost = x

    def getCurrentTHost(self):
        return self.currentTHost

    def newDropTarget(self, wh=None):
        if wh:
            self.dropTarget = wx.EmptyBitmap(wh[0], wh[1])
            try:
                self.changeDropTarget(self.config['target'])
            except Exception:
                pass
        else:
            try:
                self.dropTarget = self._dropTargetRead(self.config['target'])
            except Exception:
                try:
                    self.dropTarget = self._dropTargetRead('default.gif')
                    self.config['target'] = 'default.gif'
                    self.saveConfig()
                except Exception:
                    self.dropTarget = wx.EmptyBitmap(100, 100)
        return self.dropTarget

    def setDropTargetRefresh(self, refreshfunc):
        self.dropTargetRefresh = refreshfunc

    def changeDropTarget(self, new):
        bmp = self._dropTargetRead(new)
        w1, h1 = self.dropTarget.GetWidth(), self.dropTarget.GetHeight()
        w, h = bmp.GetWidth(), bmp.GetHeight()
        x1, y1 = int((w1 - w) / 2.0), int((h1 - h) / 2.0)
        bbdata = wx.MemoryDC()
        bbdata.SelectObject(self.dropTarget)
        bbdata.SetPen(wx.TRANSPARENT_PEN)
        bbdata.SetBrush(wx.Brush(wx.SystemSettings_GetColour(
            wx.SYS_COLOUR_MENU), wx.SOLID))
        bbdata.DrawRectangle(0, 0, w1, h1)
        bbdata.SetPen(wx.BLACK_PEN)
        bbdata.SetBrush(wx.TRANSPARENT_BRUSH)
        bbdata.DrawRectangle(x1 - 1, y1 - 1, w + 2, h + 2)
        bbdata.DrawBitmap(bmp, x1, y1, True)
        try:
            self.dropTargetRefresh()
        except Exception:
            pass

    def _dropTargetRead(self, new):
        a, b = os.path.split(new)
        if a and a != os.path.join(basepath, 'targets'):
            if a != os.path.join(basepath, 'targets'):
                b1, b2 = os.path.splitext(b)
                z = 0
                while os.path.isfile(os.path.join(basepath, 'targets', b)):
                    z += 1
                    b = b1 + '(' + str(z) + ')' + b2
                # 2013.02.28 CJJ Changed unknown variable newname to new
                shutil.copyfile(new, os.path.join(basepath, 'targets', b))
            new = b
        name = os.path.join(basepath, 'targets', new)
        e = os.path.splitext(new.lower())[1]
        if e == '.gif':
            bmp = wx.Bitmap(name, wx.BITMAP_TYPE_GIF)
        elif e == '.bmp':
            bmp = wx.Bitmap(name, wx.BITMAP_TYPE_BMP)
        else:
            assert False
        return bmp

    def dropTargetHovered(self, x=None):
        pass

    def dropTargetUnhovered(self, x=None):
        pass

    def dropTargetDropped(self, x=None):
        pass

    def dropTargetSuccess(self, x=None):
        pass

    def dropTargetError(self, x=None):
        pass

    def switchToBasic(self, x=None):
        self.d.close()
        self.d = BasicDownloadInfo(self.config, self.getCalls())

    def switchToAdvanced(self, x=None):
        self.d.close()
        self.d = AdvancedDownloadInfo(self.config, self.getCalls())


class btWxApp(wx.App):
    def OnInit(self):
        self.APP = T_make()
        return True

if __name__ == '__main__':
    btWxApp().MainLoop()
