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
    from wxPython import wx
except ImportError:
    print 'wxPython is not installed or has not been installed properly.'
    sys.exit(1)

wxEVT_INVOKE = wx.wxNewEventType()


def EVT_INVOKE(win, func):
    win.Connect(-1, -1, wxEVT_INVOKE, func)


class InvokeEvent(wx.wxPyEvent):
    def __init__(self, func, args, kwargs):
        super(InvokeEvent, self).__init__()
        self.SetEventType(wxEVT_INVOKE)
        self.func = func
        self.args = args
        self.kwargs = kwargs


class DownloadInfo:
    def __init__(self):
        frame = wx.wxFrame(None, -1, 'BitTorrent Torrent File Maker',
                           size=wx.wxSize(550, 410))
        self.frame = frame

        panel = wx.wxPanel(frame, -1)

        gridSizer = wx.wxFlexGridSizer(cols=2, rows=2, vgap=0, hgap=8)

        gridSizer.Add(wx.wxStaticText(panel, -1, 'make torrent of:'))

        b = wx.wxBoxSizer(wx.wxHORIZONTAL)
        self.dirCtl = wx.wxTextCtrl(panel, -1, '')
        b.Add(self.dirCtl, 1, wx.wxEXPAND)
#        b.Add(10, 10, 0, wxEXPAND)

        button = wx.wxButton(panel, -1, 'dir', size=(30, 20))
        wx.EVT_BUTTON(frame, button.GetId(), self.selectdir)
        b.Add(button, 0)

        button2 = wx.wxButton(panel, -1, 'file', size=(30, 20))
        wx.EVT_BUTTON(frame, button2.GetId(), self.selectfile)
        b.Add(button2, 0)

        gridSizer.Add(b, 0, wx.wxEXPAND)
        gridSizer.Add(wx.wxStaticText(panel, -1, ''))
        gridSizer.Add(wx.wxStaticText(panel, -1, ''))

        gridSizer.Add(wx.wxStaticText(panel, -1, 'announce url:'))
        self.annCtl = wx.wxTextCtrl(panel, -1,
                                    'http://my.tracker:6969/announce')
        gridSizer.Add(self.annCtl, 0, wx.wxEXPAND)
        gridSizer.Add(wx.wxStaticText(panel, -1, ''))
        gridSizer.Add(wx.wxStaticText(panel, -1, ''))

        a = wx.wxFlexGridSizer(cols=1)
        a.Add(wx.wxStaticText(panel, -1, 'announce list:'))
        a.Add(wx.wxStaticText(panel, -1, ''))
        abutton = wx.wxButton(panel, -1, 'copy\nannounces\nfrom\ntorrent',
                              size=(50, 70))
        wx.EVT_BUTTON(frame, abutton.GetId(), self.announcecopy)
        a.Add(abutton, 0, wx.wxEXPAND)
        gridSizer.Add(a, 0, wx.wxEXPAND)

        self.annListCtl = wx.wxTextCtrl(
            panel, -1, '\n\n\n\n\n', wx.wxPoint(-1, -1), (400, 120),
            wx.wxTE_MULTILINE | wx.wxHSCROLL | wx.wxTE_DONTWRAP)
        gridSizer.Add(self.annListCtl, -1, wx.wxEXPAND)

        gridSizer.Add(wx.wxStaticText(panel, -1, ''))
        exptext = wx.wxStaticText(
            panel, -1, 'a list of announces separated by commas or whitespace '
            'and on several lines -\ntrackers on the same line will be tried '
            'randomly, and all the trackers on one line\nwill be tried before '
            'the trackers on the next line.')
        exptext.SetFont(wx.wxFont(6, wx.wxDEFAULT, wx.wxNORMAL, wx.wxNORMAL,
                                  False))
        gridSizer.Add(exptext)

        gridSizer.Add(wx.wxStaticText(panel, -1, ''))
        gridSizer.Add(wx.wxStaticText(panel, -1, ''))

        gridSizer.Add(wx.wxStaticText(panel, -1, 'piece size:'))
        self.piece_length = wx.wxChoice(
            panel, -1, choices=['automatic', '2MiB', '1MiB', '512KiB',
                                '256KiB', '128KiB', '64KiB', '32KiB'])
        self.piece_length_list = [0, 21, 20, 19, 18, 17, 16, 15]
        self.piece_length.SetSelection(0)
        gridSizer.Add(self.piece_length)

        gridSizer.Add(wx.wxStaticText(panel, -1, ''))
        gridSizer.Add(wx.wxStaticText(panel, -1, ''))

        gridSizer.Add(wx.wxStaticText(panel, -1, 'comment:'))
        self.commentCtl = wx.wxTextCtrl(panel, -1, '')
        gridSizer.Add(self.commentCtl, 0, wx.wxEXPAND)

        gridSizer.AddGrowableCol(1)

        border = wx.wxBoxSizer(wx.wxVERTICAL)
        border.Add(gridSizer, 0,
                   wx.wxEXPAND | wx.wxNORTH | wx.wxEAST | wx.wxWEST, 25)
        b2 = wx.wxButton(panel, -1, 'make')
#        border.Add(10, 10, 1, wxEXPAND)
        border.Add(b2, 0, wx.wxALIGN_CENTER | wx.wxSOUTH, 20)
        wx.EVT_BUTTON(frame, b2.GetId(), self.complete)
        panel.SetSizer(border)
        panel.SetAutoLayout(True)

#        panel.DragAcceptFiles(True)
#        EVT_DROP_FILES(panel, self.selectdrop)

    def selectdir(self, x):
        dl = wx.wxDirDialog(
            self.frame, style=wx.wxDD_DEFAULT_STYLE | wx.wxDD_NEW_DIR_BUTTON)
        if dl.ShowModal() == wx.wxID_OK:
            self.dirCtl.SetValue(dl.GetPath())

    def selectfile(self, x):
        dl = wx.wxFileDialog(self.frame, 'Choose file or directory to use', '',
                             '', '', wx.wxOPEN)
        if dl.ShowModal() == wx.wxID_OK:
            self.dirCtl.SetValue(dl.GetPath())

    def selectdrop(self, x):
        print x

        # list = x.m_files
        self.dirCtl.SetValue(x[0])

    def announcecopy(self, x):
        dl = wx.wxFileDialog(self.frame, 'Choose .torrent file to use', '', '',
                             '*.torrent', wx.wxOPEN)
        if dl.ShowModal() == wx.wxID_OK:
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
            dlg = wx.wxMessageDialog(
                self.frame, message='You must select a\n file or directory',
                caption='Error', style=wx.wxOK | wx.wxICON_ERROR)
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
    def __init__(self, d, a, params):
        self.d = d
        self.a = a
        self.params = params
        self.flag = threading.Event()
        self.separatetorrents = False

        if os.path.isdir(d):
            self.choicemade = threading.Event()
            frame = wx.wxFrame(None, -1, 'BitTorrent make torrent',
                               size=(1, 1))
            self.frame = frame
            panel = wx.wxPanel(frame, -1)
            gridSizer = wx.wxFlexGridSizer(cols=1, vgap=8, hgap=8)
            gridSizer.AddGrowableRow(1)
            gridSizer.Add(wx.wxStaticText(
                panel, -1, 'Do you want to make a separate .torrent'), 0,
                wx.wxALIGN_CENTER)
            gridSizer.Add(wx.wxStaticText(
                panel, -1, 'for every item in this directory?'), 0,
                wx.wxALIGN_CENTER)
            gridSizer.Add(wx.wxStaticText(panel, -1, ''))

            b = wx.wxFlexGridSizer(cols=3, hgap=10)
            yesbut = wx.wxButton(panel, -1, 'Yes')

            def saidyes(e, self=self):
                self.frame.Destroy()
                self.separatetorrents = True
                self.begin()
            wx.EVT_BUTTON(frame, yesbut.GetId(), saidyes)
            b.Add(yesbut, 0)

            nobut = wx.wxButton(panel, -1, 'No')

            def saidno(e, self=self):
                self.frame.Destroy()
                self.begin()
            wx.EVT_BUTTON(frame, nobut.GetId(), saidno)
            b.Add(nobut, 0)

            cancelbut = wx.wxButton(panel, -1, 'Cancel')

            def canceled(e, self=self):
                self.frame.Destroy()
            wx.EVT_BUTTON(frame, cancelbut.GetId(), canceled)
            b.Add(cancelbut, 0)
            gridSizer.Add(b, 0, wx.wxALIGN_CENTER)
            border = wx.wxBoxSizer(wx.wxHORIZONTAL)
            border.Add(gridSizer, 1, wx.wxEXPAND | wx.wxALL, 4)

            panel.SetSizer(border)
            panel.SetAutoLayout(True)
            frame.Show()
            border.Fit(panel)
            frame.Fit()

        else:
            self.begin()

    def begin(self):
        if self.separatetorrents:
            frame = wx.wxFrame(None, -1, 'BitTorrent make directory',
                               size=wx.wxSize(550, 250))
        else:
            frame = wx.wxFrame(None, -1, 'BitTorrent make torrent',
                               size=wx.wxSize(550, 250))
        self.frame = frame

        panel = wx.wxPanel(frame, -1)
        gridSizer = wx.wxFlexGridSizer(cols=1, vgap=15, hgap=8)

        if self.separatetorrents:
            self.currentLabel = wx.wxStaticText(panel, -1,
                                                'checking file sizes')
        else:
            self.currentLabel = wx.wxStaticText(
                panel, -1, 'building ' + self.d + '.torrent')
        gridSizer.Add(self.currentLabel, 0, wx.wxEXPAND)
        self.gauge = wx.wxGauge(panel, -1, range=1000, style=wx.wxGA_SMOOTH)
        gridSizer.Add(self.gauge, 0, wx.wxEXPAND)
        gridSizer.Add((10, 10), 1, wx.wxEXPAND)
        self.button = wx.wxButton(panel, -1, 'cancel')
        gridSizer.Add(self.button, 0, wx.wxALIGN_CENTER)
        gridSizer.AddGrowableRow(2)
        gridSizer.AddGrowableCol(0)

        g2 = wx.wxFlexGridSizer(cols=1, vgap=15, hgap=8)
        g2.Add(gridSizer, 1, wx.wxEXPAND | wx.wxALL, 25)
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
                completedir(self.d, self.a, self.params, self.flag,
                            self.valcallback, self.filecallback)
            else:
                make_meta_file(self.d, self.a, self.params, self.flag,
                               self.valcallback, progress_percent=1)
            if not self.flag.isSet():
                self.currentLabel.SetLabel('Done!')
                self.gauge.SetValue(1000)
                self.button.SetLabel('Close')
                self.frame.Refresh()
        except (OSError, IOError) as e:
            self.currentLabel.SetLabel('Error!')
            self.button.SetLabel('Close')
            dlg = wx.wxMessageDialog(
                self.frame, message='Error - ' + str(e), caption='Error',
                style=wx.wxOK | wx.wxICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()

    def valcallback(self, amount):
        self.invokeLater(self.onval, [amount])

    def onval(self, amount):
        self.gauge.SetValue(int(amount * 1000))

    def filecallback(self, f):
        self.invokeLater(self.onfile, [f])

    def onfile(self, f):
        self.currentLabel.SetLabel(
            'building ' + os.path.join(self.d, f) + '.torrent')

    def onInvoke(self, event):
        if not self.flag.isSet():
            event.func(*event.args, **event.kwargs)

    def invokeLater(self, func, args=[], kwargs={}):
        if not self.flag.isSet():
            wx.wxPostEvent(self.frame, InvokeEvent(func, args, kwargs))

    def done(self, event):
        self.flag.set()
        self.frame.Destroy()


class btWxApp(wx.wxApp):
    def OnInit(self):
        d = DownloadInfo()
        d.frame.Show(True)
        self.SetTopWindow(d.frame)
        return True

if __name__ == '__main__':
    btWxApp().MainLoop()
