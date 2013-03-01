#!/usr/bin/env python

# Written by Bram Cohen
# see LICENSE.txt for license information

import sys
import os
import threading
from BitTornado.BT1.makemetafile import completedir
try:
    from wxPython import wx
except:
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
        frame = wx.wxFrame(None, -1, 'BitTorrent complete dir 1.0.1',
                           size=wx.wxSize(550, 250))
        self.frame = frame

        panel = wx.wxPanel(frame, -1)

        gridSizer = wx.wxFlexGridSizer(cols=2, rows=2, vgap=15, hgap=8)

        gridSizer.Add(wx.wxStaticText(panel, -1, 'directory to build:'))
        self.dirCtl = wx.wxTextCtrl(panel, -1, '')

        b = wx.wxBoxSizer(wx.wxHORIZONTAL)
        b.Add(self.dirCtl, 1, wx.wxEXPAND)
#        b.Add(10, 10, 0, wxEXPAND)
        button = wx.wxButton(panel, -1, 'select')
        b.Add(button, 0, wx.wxEXPAND)
        wx.EVT_BUTTON(frame, button.GetId(), self.select)

        gridSizer.Add(b, 0, wx.wxEXPAND)

        gridSizer.Add(wx.wxStaticText(panel, -1, 'announce url:'))
        self.annCtl = wx.wxTextCtrl(panel, -1,
                                    'http://my.tracker:6969/announce')
        gridSizer.Add(self.annCtl, 0, wx.wxEXPAND)

        gridSizer.Add(wx.wxStaticText(panel, -1, 'piece size:'))
        self.piece_length = wx.wxChoice(
            panel, -1, choices=['2 ** 21', '2 ** 20', '2 ** 19', '2 ** 18',
                                '2 ** 17', '2 ** 16', '2 ** 15'])
        self.piece_length.SetSelection(3)
        gridSizer.Add(self.piece_length)

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

    def select(self, x):
        dl = wx.wxDirDialog(
            self.frame, style=(wx.wxDD_DEFAULT_STYLE | wx.wxDD_NEW_DIR_BUTTON))
        if dl.ShowModal() == wx.wxID_OK:
            self.dirCtl.SetValue(dl.GetPath())

    def complete(self, x):
        if self.dirCtl.GetValue() == '':
            dlg = wx.wxMessageDialog(
                self.frame, message='You must select a directory',
                caption='Error', style=(wx.wxOK | wx.wxICON_ERROR))
            dlg.ShowModal()
            dlg.Destroy()
            return
        try:
            ps = 2 ** (21 - self.piece_length.GetSelection())
            CompleteDir(self.dirCtl.GetValue(), self.annCtl.GetValue(), ps)
        except:
            print_exc()

from traceback import print_exc


class CompleteDir:
    def __init__(self, d, a, pl):
        self.d = d
        self.a = a
        self.pl = pl
        self.flag = threading.Event()
        frame = wx.wxFrame(None, -1, 'BitTorrent make directory',
                           size=wx.wxSize(550, 250))
        self.frame = frame

        panel = wx.wxPanel(frame, -1)

        gridSizer = wx.wxFlexGridSizer(cols=1, vgap=15, hgap=8)

        self.currentLabel = wx.wxStaticText(panel, -1, 'checking file sizes')
        gridSizer.Add(self.currentLabel, 0, wx.wxEXPAND)
        self.gauge = wx.wxGauge(panel, -1, range=1000, style=wx.wxGA_SMOOTH)
        gridSizer.Add(self.gauge, 0, wx.wxEXPAND)
        gridSizer.Add(10, 10, 1, wx.wxEXPAND)
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
        params = {'piece_size_pow2': self.pl}
        try:
            completedir(self.d, self.a, params, self.flag, self.valcallback,
                        self.filecallback)
            if not self.flag.isSet():
                self.currentLabel.SetLabel('Done!')
                self.gauge.SetValue(1000)
                self.button.SetLabel('Close')
        except (OSError, IOError) as e:
            self.currentLabel.SetLabel('Error!')
            self.button.SetLabel('Close')
            dlg = wx.wxMessageDialog(
                self.frame, message='Error - ' + str(e), caption='Error',
                style=(wx.wxOK | wx.wxICON_ERROR))
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
            'building {}.torrent'.format(os.path.join(self.d, f)))

    def onInvoke(self, event):
        if not self.flag.isSet():
            apply(event.func, event.args, event.kwargs)

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
