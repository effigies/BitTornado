#!/usr/bin/env python

# Written by Bram Cohen
# modified for multitracker by John Hoffman
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

from BitTornado.BT1.makemetafile import make_meta_file, completedir
from threading import Event, Thread
from BitTornado.bencode import bdecode
import sys
from os import getcwd
from os.path import join, isdir
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
        frame = wxFrame(None, -1, 'BitTorrent Torrent File Maker', size = wxSize(550, 410))
        self.frame = frame

        panel = wxPanel(frame, -1)

        gridSizer = wxFlexGridSizer(cols = 2, rows = 2, vgap = 0, hgap = 8)
        
        gridSizer.Add(wxStaticText(panel, -1, 'make torrent of:'))

        b = wxBoxSizer(wxHORIZONTAL)
        self.dirCtl = wxTextCtrl(panel, -1, '')
        b.Add(self.dirCtl, 1, wxEXPAND)
#        b.Add(10, 10, 0, wxEXPAND)
        
        button = wxButton(panel, -1, 'dir', size = (30,20))
        EVT_BUTTON(frame, button.GetId(), self.selectdir)
        b.Add(button, 0)

        button2 = wxButton(panel, -1, 'file', size = (30,20))
        EVT_BUTTON(frame, button2.GetId(), self.selectfile)
        b.Add(button2, 0)

        gridSizer.Add(b, 0, wxEXPAND)
        gridSizer.Add(wxStaticText(panel, -1, ''))
        gridSizer.Add(wxStaticText(panel, -1, ''))

        gridSizer.Add(wxStaticText(panel, -1, 'announce url:'))
        self.annCtl = wxTextCtrl(panel, -1, 'http://my.tracker:6969/announce')
        gridSizer.Add(self.annCtl, 0, wxEXPAND)
        gridSizer.Add(wxStaticText(panel, -1, ''))
        gridSizer.Add(wxStaticText(panel, -1, ''))

        a = wxFlexGridSizer(cols = 1)
        a.Add(wxStaticText(panel, -1, 'announce list:'))
        a.Add(wxStaticText(panel, -1, ''))
        abutton = wxButton(panel, -1, 'copy\nannounces\nfrom\ntorrent', size = (50,70))
        EVT_BUTTON(frame, abutton.GetId(), self.announcecopy)
        a.Add(abutton, 0, wxEXPAND)
        gridSizer.Add(a, 0, wxEXPAND)
        
        self.annListCtl = wxTextCtrl(panel, -1, '\n\n\n\n\n', wxPoint(-1,-1), (400,120),
                                            wxTE_MULTILINE|wxHSCROLL|wxTE_DONTWRAP)
        gridSizer.Add(self.annListCtl, -1, wxEXPAND)

        gridSizer.Add(wxStaticText(panel, -1, ''))
        exptext = wxStaticText(panel, -1,
                "a list of announces separated by commas " +
                "or whitespace and on several lines -\n" +
                "trackers on the same line will be tried randomly," +
                "and all the trackers on one line\n" +
                "will be tried before the trackers on the next line.")
        exptext.SetFont(wxFont(6, wxDEFAULT, wxNORMAL, wxNORMAL, False))
        gridSizer.Add(exptext)

        gridSizer.Add(wxStaticText(panel, -1, ''))
        gridSizer.Add(wxStaticText(panel, -1, ''))

        gridSizer.Add(wxStaticText(panel, -1, 'piece size:'))
        self.piece_length = wxChoice(panel, -1,
                 choices = ['automatic', '2MiB', '1MiB', '512KiB', '256KiB', '128KiB', '64KiB', '32KiB'])
        self.piece_length_list = [0,       21,     20,      19,       18,       17,      16,      15]
        self.piece_length.SetSelection(0)
        gridSizer.Add(self.piece_length)
        
        gridSizer.Add(wxStaticText(panel, -1, ''))
        gridSizer.Add(wxStaticText(panel, -1, ''))

        gridSizer.Add(wxStaticText(panel, -1, 'comment:'))
        self.commentCtl = wxTextCtrl(panel, -1, '')
        gridSizer.Add(self.commentCtl, 0, wxEXPAND)

        gridSizer.AddGrowableCol(1)
 
        border = wxBoxSizer(wxVERTICAL)
        border.Add(gridSizer, 0, wxEXPAND | wxNORTH | wxEAST | wxWEST, 25)
        b2 = wxButton(panel, -1, 'make')
#        border.Add(10, 10, 1, wxEXPAND)
        border.Add(b2, 0, wxALIGN_CENTER | wxSOUTH, 20)
        EVT_BUTTON(frame, b2.GetId(), self.complete)
        panel.SetSizer(border)
        panel.SetAutoLayout(True)

#        panel.DragAcceptFiles(True)
#        EVT_DROP_FILES(panel, self.selectdrop)

    def selectdir(self, x):
        dl = wxDirDialog(self.frame, style = wxDD_DEFAULT_STYLE | wxDD_NEW_DIR_BUTTON)
        if dl.ShowModal() == wxID_OK:
            self.dirCtl.SetValue(dl.GetPath())

    def selectfile(self, x):
        dl = wxFileDialog (self.frame, 'Choose file or directory to use', '', '', '', wxOPEN)
        if dl.ShowModal() == wxID_OK:
            self.dirCtl.SetValue(dl.GetPath())

    def selectdrop(self, x):
        print x

        list = x.m_files
        self.dirCtl.SetValue(x[0])

    def announcecopy(self, x):
        dl = wxFileDialog (self.frame, 'Choose .torrent file to use', '', '', '*.torrent', wxOPEN)
        if dl.ShowModal() == wxID_OK:
            try:
                h = open(dl.GetPath(), 'rb')
                metainfo = bdecode(h.read())
                h.close()
                self.annCtl.SetValue(metainfo['announce'])
                if metainfo.has_key('announce-list'):
                    list = []
                    for tier in metainfo['announce-list']:
                        for tracker in tier:
                            list += [tracker, ', ']
                        del list[-1]
                        list += ['\n']
                    liststring = ''
                    for i in list:
                        liststring += i
                    self.annListCtl.SetValue(liststring+'\n\n')
                else:
                    self.annListCtl.SetValue('')
            except:
                return

    def getannouncelist(self):
        list = []
        for t in self.annListCtl.GetValue().split('\n'):
            tier = []
            t = t.replace(',',' ')
            for tr in t.split(' '):
                if tr != '':
                    tier += [tr]
            if len(tier)>0:
                list.append(tier)
        return list
    
    def complete(self, x):
        if self.dirCtl.GetValue() == '':
            dlg = wxMessageDialog(self.frame, message = 'You must select a\n file or directory', 
                caption = 'Error', style = wxOK | wxICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return
        params = {'piece_size_pow2': self.piece_length_list[self.piece_length.GetSelection()]}
        annlist = self.getannouncelist()
        if len(annlist)>0:
            params['real_announce_list'] = annlist
        comment = self.commentCtl.GetValue()
        if comment != '':
            params['comment'] = comment
        try:
            CompleteDir(self.dirCtl.GetValue(), self.annCtl.GetValue(), params)
        except:
            print_exc()


from traceback import print_exc

class CompleteDir:
    def __init__(self, d, a, params):
        self.d = d
        self.a = a
        self.params = params
        self.flag = Event()
        self.separatetorrents = False

        if isdir(d):
            self.choicemade = Event()
            frame = wxFrame(None, -1, 'BitTorrent make torrent', size = (1,1))
            self.frame = frame
            panel = wxPanel(frame, -1)
            gridSizer = wxFlexGridSizer(cols = 1, vgap = 8, hgap = 8)
            gridSizer.AddGrowableRow(1)
            gridSizer.Add(wxStaticText(panel, -1,
                    'Do you want to make a separate .torrent'),0,wxALIGN_CENTER)
            gridSizer.Add(wxStaticText(panel, -1,
                    'for every item in this directory?'),0,wxALIGN_CENTER)
            gridSizer.Add(wxStaticText(panel, -1, ''))

            b = wxFlexGridSizer(cols = 3, hgap = 10)
            yesbut = wxButton(panel, -1, 'Yes')
            def saidyes(e, self = self):
                self.frame.Destroy()
                self.separatetorrents = True
                self.begin()
            EVT_BUTTON(frame, yesbut.GetId(), saidyes)
            b.Add(yesbut, 0)

            nobut = wxButton(panel, -1, 'No')
            def saidno(e, self = self):
                self.frame.Destroy()
                self.begin()
            EVT_BUTTON(frame, nobut.GetId(), saidno)
            b.Add(nobut, 0)

            cancelbut = wxButton(panel, -1, 'Cancel')
            def canceled(e, self = self):
                self.frame.Destroy()                
            EVT_BUTTON(frame, cancelbut.GetId(), canceled)
            b.Add(cancelbut, 0)
            gridSizer.Add(b, 0, wxALIGN_CENTER)
            border = wxBoxSizer(wxHORIZONTAL)
            border.Add(gridSizer, 1, wxEXPAND | wxALL, 4)
            
            panel.SetSizer(border)
            panel.SetAutoLayout(True)
            frame.Show()
            border.Fit(panel)
            frame.Fit()
            
        else:
            self.begin()

    def begin(self):
        if self.separatetorrents:
            frame = wxFrame(None, -1, 'BitTorrent make directory', size = wxSize(550, 250))
        else:
            frame = wxFrame(None, -1, 'BitTorrent make torrent', size = wxSize(550, 250))
        self.frame = frame

        panel = wxPanel(frame, -1)
        gridSizer = wxFlexGridSizer(cols = 1, vgap = 15, hgap = 8)

        if self.separatetorrents:
            self.currentLabel = wxStaticText(panel, -1, 'checking file sizes')
        else:
            self.currentLabel = wxStaticText(panel, -1, 'building ' + self.d + '.torrent')
        gridSizer.Add(self.currentLabel, 0, wxEXPAND)
        self.gauge = wxGauge(panel, -1, range = 1000, style = wxGA_SMOOTH)
        gridSizer.Add(self.gauge, 0, wxEXPAND)
        gridSizer.Add((10, 10), 1, wxEXPAND)
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
        try:
            if self.separatetorrents:
                completedir(self.d, self.a, self.params, self.flag,
                            self.valcallback, self.filecallback)
            else:
                make_meta_file(self.d, self.a, self.params, self.flag,
                            self.valcallback, progress_percent = 1)
            if not self.flag.isSet():
                self.currentLabel.SetLabel('Done!')
                self.gauge.SetValue(1000)
                self.button.SetLabel('Close')
                self.frame.Refresh()
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
