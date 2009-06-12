#!/usr/bin/env python

# Written by Bram Cohen
# see LICENSE.txt for license information

from BitTornado import PSYCO
if PSYCO.psyco:
    try:
        import psyco
        assert psyco.__version__ >= 0x010100f0
        psyco.full()
    except:
        pass

from sys import argv, version
assert version >= '2', "Install Python 2.0 or greater"
from BitTornado.BT1.makemetafile import completedir
from threading import Event, Thread
import sys
from os import getcwd
from os.path import join
try:
    from wxPython.wx import *
except:
    print 'wxPython is either not installed or has not been installed properly.'
    sys.exit(1)

try:
    True
except:
    True = 1
    False = 0

wxEVT_INVOKE = wxNewEventType()

def EVT_INVOKE(win, func):
    win.Connect(-1, -1, wxEVT_INVOKE, func)

class InvokeEvent(wxPyEvent):
    def __init__(self, func, args, kwargs):
        wxPyEvent.__init__(self)
        self.SetEventType(wxEVT_INVOKE)
        self.func = func
        self.args = args
        self.kwargs = kwargs

class DownloadInfo:
    def __init__(self):
        frame = wxFrame(None, -1, 'BitTorrent complete dir 1.0.1', size = wxSize(550, 250))
        self.frame = frame

        panel = wxPanel(frame, -1)

        gridSizer = wxFlexGridSizer(cols = 2, rows = 2, vgap = 15, hgap = 8)
        
        gridSizer.Add(wxStaticText(panel, -1, 'directory to build:'))
        self.dirCtl = wxTextCtrl(panel, -1, '')

        b = wxBoxSizer(wxHORIZONTAL)
        b.Add(self.dirCtl, 1, wxEXPAND)
#        b.Add(10, 10, 0, wxEXPAND)
        button = wxButton(panel, -1, 'select')
        b.Add(button, 0, wxEXPAND)
        EVT_BUTTON(frame, button.GetId(), self.select)

        gridSizer.Add(b, 0, wxEXPAND)

        gridSizer.Add(wxStaticText(panel, -1, 'announce url:'))
        self.annCtl = wxTextCtrl(panel, -1, 'http://my.tracker:6969/announce')
        gridSizer.Add(self.annCtl, 0, wxEXPAND)

        gridSizer.Add(wxStaticText(panel, -1, 'piece size:'))
        self.piece_length = wxChoice(panel, -1, choices = ['2 ** 21', '2 ** 20', '2 ** 19', 
            '2 ** 18', '2 ** 17', '2 ** 16', '2 ** 15'])
        self.piece_length.SetSelection(3)
        gridSizer.Add(self.piece_length)

        gridSizer.AddGrowableCol(1)
 
        border = wxBoxSizer(wxVERTICAL)
        border.Add(gridSizer, 0, wxEXPAND | wxNORTH | wxEAST | wxWEST, 25)
        b2 = wxButton(panel, -1, 'make')
#        border.Add(10, 10, 1, wxEXPAND)
        border.Add(b2, 0, wxALIGN_CENTER | wxSOUTH, 20)
        EVT_BUTTON(frame, b2.GetId(), self.complete)
        panel.SetSizer(border)
        panel.SetAutoLayout(True)

    def select(self, x):
        dl = wxDirDialog(self.frame, style = wxDD_DEFAULT_STYLE | wxDD_NEW_DIR_BUTTON)
        if dl.ShowModal() == wxID_OK:
            self.dirCtl.SetValue(dl.GetPath())

    def complete(self, x):
        if self.dirCtl.GetValue() == '':
            dlg = wxMessageDialog(self.frame, message = 'You must select a directory', 
                caption = 'Error', style = wxOK | wxICON_ERROR)
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
        self.flag = Event()
        frame = wxFrame(None, -1, 'BitTorrent make directory', size = wxSize(550, 250))
        self.frame = frame

        panel = wxPanel(frame, -1)

        gridSizer = wxFlexGridSizer(cols = 1, vgap = 15, hgap = 8)

        self.currentLabel = wxStaticText(panel, -1, 'checking file sizes')
        gridSizer.Add(self.currentLabel, 0, wxEXPAND)
        self.gauge = wxGauge(panel, -1, range = 1000, style = wxGA_SMOOTH)
        gridSizer.Add(self.gauge, 0, wxEXPAND)
        gridSizer.Add(10, 10, 1, wxEXPAND)
        self.button = wxButton(panel, -1, 'cancel')
        gridSizer.Add(self.button, 0, wxALIGN_CENTER)
        gridSizer.AddGrowableRow(2)
        gridSizer.AddGrowableCol(0)

        g2 = wxFlexGridSizer(cols = 1, vgap = 15, hgap = 8)
        g2.Add(gridSizer, 1, wxEXPAND | wxALL, 25)
        g2.AddGrowableRow(0)
        g2.AddGrowableCol(0)
        panel.SetSizer(g2)
        panel.SetAutoLayout(True)
        EVT_BUTTON(frame, self.button.GetId(), self.done)
        EVT_CLOSE(frame, self.done)
        EVT_INVOKE(frame, self.onInvoke)
        frame.Show(True)
        Thread(target = self.complete).start()

    def complete(self):
        params = {'piece_size_pow2': self.pl}
        try:
            completedir(self.d, self.a, params, self.flag, self.valcallback, self.filecallback)
            if not self.flag.isSet():
                self.currentLabel.SetLabel('Done!')
                self.gauge.SetValue(1000)
                self.button.SetLabel('Close')
        except (OSError, IOError), e:
            self.currentLabel.SetLabel('Error!')
            self.button.SetLabel('Close')
            dlg = wxMessageDialog(self.frame, message = 'Error - ' + str(e), 
                caption = 'Error', style = wxOK | wxICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()

    def valcallback(self, amount):
        self.invokeLater(self.onval, [amount])

    def onval(self, amount):
        self.gauge.SetValue(int(amount * 1000))

    def filecallback(self, f):
        self.invokeLater(self.onfile, [f])

    def onfile(self, f):
        self.currentLabel.SetLabel('building ' + join(self.d, f) + '.torrent')

    def onInvoke(self, event):
        if not self.flag.isSet():
            apply(event.func, event.args, event.kwargs)

    def invokeLater(self, func, args = [], kwargs = {}):
        if not self.flag.isSet():
            wxPostEvent(self.frame, InvokeEvent(func, args, kwargs))

    def done(self, event):
        self.flag.set()
        self.frame.Destroy()

class btWxApp(wxApp):
    def OnInit(self):
        d = DownloadInfo()
        d.frame.Show(True)
        self.SetTopWindow(d.frame)
        return True

if __name__ == '__main__':
    btWxApp().MainLoop()
