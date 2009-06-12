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

from sys import argv, platform, version
assert version >= '2', "Install Python 2.0 or greater"
from BitTornado.BT1.makemetafile import make_meta_file
from threading import Event, Thread, Lock
from BitTornado.bencode import bencode,bdecode
import sys, os, shutil
from os import getcwd, listdir
from os.path import join, isdir
from traceback import print_exc
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

basepath=os.path.abspath(os.path.dirname(sys.argv[0]))

if platform == 'win32':
    DROP_HERE = '(drop here)'
else:
    DROP_HERE = ''


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


class BasicDownloadInfo:
    def __init__(self, config, calls):
        self.config = config
        self.calls = calls
        
        self.uiflag = Event()
        self.cancelflag = Event()
        self.switchlock = Lock()
        self.working = False
        self.queue = []
        wxInitAllImageHandlers()
        self.thostselection = self.calls['getCurrentTHost']()
        self.thostselectnum = 0
        self.choices = None
        self.choices1 = None
        self.announce = ''
        self.announce_list = None

        self.windowStyle = wxSYSTEM_MENU|wxCAPTION|wxMINIMIZE_BOX
        if self.config['stayontop']:
            self.windowStyle |= wxSTAY_ON_TOP
        frame = wxFrame(None, -1, 'T-Make',
                        size = wxSize(-1, -1),
                        style = self.windowStyle)
        self.frame = frame
        panel = wxPanel(frame, -1)
        mainSizer = wxBoxSizer(wxVERTICAL)
        groupSizer = wxFlexGridSizer(cols = 1, vgap = 0, hgap = 0)
#        self.dropTarget = self.calls['newDropTarget']((200,200))
        self.dropTarget = self.calls['newDropTarget']()
        self.dropTargetPtr = wxStaticBitmap(panel, -1, self.dropTarget)
        self.calls['setDropTargetRefresh'](self.dropTargetPtr.Refresh)
        self.dropTargetWidth = self.dropTarget.GetWidth()
        EVT_LEFT_DOWN(self.dropTargetPtr,self.dropTargetClick)
        EVT_ENTER_WINDOW(self.dropTargetPtr,self.calls['dropTargetHovered'])
        EVT_LEAVE_WINDOW(self.dropTargetPtr,self.calls['dropTargetUnhovered'])
        groupSizer.Add(self.dropTargetPtr,0,wxALIGN_CENTER)        
        lowerSizer1 = wxGridSizer(cols = 6)
        dirlink = wxStaticText(panel, -1, 'dir')
        dirlink.SetFont(wxFont(7, wxDEFAULT, wxNORMAL, wxNORMAL, True))
        dirlink.SetForegroundColour('blue')
        EVT_LEFT_UP(dirlink,self.selectdir)
        lowerSizer1.Add(dirlink, -1, wxALIGN_LEFT)
        lowerSizer1.Add(wxStaticText(panel, -1, ''), -1, wxALIGN_CENTER)
        lowerSizer1.Add(wxStaticText(panel, -1, ''), -1, wxALIGN_CENTER)
        lowerSizer1.Add(wxStaticText(panel, -1, ''), -1, wxALIGN_CENTER)
        lowerSizer1.Add(wxStaticText(panel, -1, ''), -1, wxALIGN_CENTER)
        filelink = wxStaticText(panel, -1, 'file')
        filelink.SetFont(wxFont(7, wxDEFAULT, wxNORMAL, wxNORMAL, True))
        filelink.SetForegroundColour('blue')
        EVT_LEFT_UP(filelink,self.selectfile)
        lowerSizer1.Add(filelink, -1, wxALIGN_RIGHT)
        
        groupSizer.Add(lowerSizer1, -1, wxALIGN_CENTER)

        self.gauge = wxGauge(panel, -1, range = 1000,
                             style = wxGA_HORIZONTAL, size = (-1,15))
        groupSizer.Add(self.gauge, 0, wxEXPAND)
        self.statustext = wxStaticText(panel, -1, 'ready',
                            style = wxALIGN_CENTER|wxST_NO_AUTORESIZE)
        self.statustext.SetFont(wxFont(7, wxDEFAULT, wxNORMAL, wxBOLD, False))
        groupSizer.Add(self.statustext, -1, wxEXPAND)
        self.choices = wxChoice(panel, -1, (-1, -1), (self.dropTargetWidth, -1),
                                    choices = [])
        self.choices.SetFont(wxFont(7, wxDEFAULT, wxNORMAL, wxNORMAL, False))
        EVT_CHOICE(self.choices, -1, self.set_thost)
        groupSizer.Add(self.choices, 0, wxEXPAND)
        cancellink = wxStaticText(panel, -1, 'cancel')
        cancellink.SetFont(wxFont(7, wxDEFAULT, wxNORMAL, wxNORMAL, True))
        cancellink.SetForegroundColour('red')
        EVT_LEFT_UP(cancellink,self.cancel)
        groupSizer.Add(cancellink, -1, wxALIGN_CENTER)
        advlink = wxStaticText(panel, -1, 'advanced')
        advlink.SetFont(wxFont(7, wxDEFAULT, wxNORMAL, wxNORMAL, True))
        advlink.SetForegroundColour('blue')
        EVT_LEFT_UP(advlink,self.calls['switchToAdvanced'])
        groupSizer.Add(advlink, -1, wxALIGN_CENTER)
        mainSizer.Add(groupSizer, 0, wxALIGN_CENTER)

        self.refresh_thostlist()
        self._set_thost()

        if platform == 'win32':
            self.dropTargetPtr.DragAcceptFiles(True)
            EVT_DROP_FILES(self.dropTargetPtr, self.selectdrop)
 
#        border = wxBoxSizer(wxHORIZONTAL)
#        border.Add(mainSizer, 1, wxEXPAND | wxALL, 0)
        panel.SetSizer(mainSizer)
        panel.SetAutoLayout(True)
#        border.Fit(panel)
        mainSizer.Fit(panel)
        frame.Fit()
        frame.Show(True)

        EVT_INVOKE(frame, self.onInvoke)
        EVT_CLOSE(frame, self._close)


    def selectdir(self, x = None):
        self.calls['dropTargetHovered']()
        dl = wxDirDialog(self.frame, style = wxDD_DEFAULT_STYLE | wxDD_NEW_DIR_BUTTON)
        if dl.ShowModal() == wxID_OK:
            self.calls['dropTargetDropped']()
            self.complete(dl.GetPath())
        else:
            self.calls['dropTargetUnhovered']()

    def selectfile(self, x = None):
        self.calls['dropTargetHovered']()
        dl = wxFileDialog (self.frame, 'Choose file to use', '', '', '', wxOPEN)
        if dl.ShowModal() == wxID_OK:
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
            h = open(f, 'rb')
            metainfo = bdecode(h.read())
            h.close()
            self.announce = metainfo['announce']
            if metainfo.has_key('announce-list'):
                self.announce_list = metainfo['announce-list']
            else:
                self.announce_list = None
        except:
            return

    def complete(self, x):
        params = {'piece_size_pow2': 0}
        if self.announce_list:
            params['real_announce_list'] = self.announce_list
        self.queue.append((x, self.announce, params))
        self.go_queue()

    def go_queue(self):
        self.switchlock.acquire()
        if self.queue and not self.working:
            self.working = True
            self.statustext.SetLabel('working')
            q = self.queue.pop(0)
            MakeMetafile(q[0], q[1], q[2], self)
        self.switchlock.release()

    def cancel(self, x):
        self.switchlock.acquire()
        if self.working:
            self.working = False
            self.cancelflag.set()
            self.cancelflag = Event()
            self.queue = []
            self.statustext.SetLabel('CANCELED')
            self.calls['dropTargetError']()
        self.switchlock.release()

    def dropTargetClick(self, x):
        if x.GetPosition()[0] < int(self.dropTargetWidth*0.4):
            self.selectdir()
        elif x.GetPosition()[0] > int(self.dropTargetWidth*0.6):
            self.selectfile()

    def refresh_thostlist(self):
        l = []
        d = 0
        for f in listdir(join(basepath,'thosts')):
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
        self.thostselectnum = d-1
        self.thostlist = l
        self.choices.SetSelection(d-1)
        return

    def set_thost(self, x):
        n = self.choices.GetSelection()
        if n != self.thostselectnum:
            self.thostselectnum = n
            if n:
                self.thostselection = self.thostlist[n-1]

    def _set_thost(self):
        self._announcecopy(join(join(basepath,'thosts'),self.thostselection))
        self.calls['setCurrentTHost'](self.thostselection)

    def onInvoke(self, event):
        if not self.uiflag.isSet():
            apply(event.func, event.args, event.kwargs)

    def invokeLater(self, func, args = [], kwargs = {}):
        if not self.uiflag.isSet():
            wxPostEvent(self.frame, InvokeEvent(func, args, kwargs))

    def build_setgauge(self, x):
        self.invokeLater(self.on_setgauge, [x])

    def on_setgauge(self, x):
        self.gauge.SetValue(int(x*1000))

    def build_done(self):
        self.invokeLater(self.on_builddone)

    def on_builddone(self):
        self.gauge.SetValue(0)
        self.statustext.SetLabel('done!')
        self.calls['dropTargetSuccess']()
        self.working = False
        self.go_queue()

    def build_failed(self, e):
        self.invokeLater(self.on_buildfailed, [e])

    def on_buildfailed(self, e):        
        self.gauge.SetValue(0)
        self.statustext.SetLabel('ERROR')
        self.calls['dropTargetError']()
        self.working = False
        self.go_queue()

    def close(self):
        self.cancelflag = None   # this is a planned switch, don't cancel
        self.uiflag.set()
        self.frame.Close()

    def _close(self, x = None):
        self.uiflag.set()
        try:
            self.cancelflag.set()
        except:
            pass
        self.frame.Destroy()



class AdvancedDownloadInfo:
    def __init__(self, config, calls):
        self.config = config
        self.calls = calls
        
        self.uiflag = Event()
        self.cancelflag = Event()
        self.switchlock = Lock()
        self.working = False
        self.queue = []
        wxInitAllImageHandlers()
        self.thostselection = self.calls['getCurrentTHost']()
        self.thostselectnum = 0
        self.choices = None
        self.choices1 = None

        self.windowStyle = wxSYSTEM_MENU|wxCAPTION|wxMINIMIZE_BOX
        if self.config['stayontop']:
            self.windowStyle |= wxSTAY_ON_TOP
        frame = wxFrame(None, -1, 'T-Make',
                        size = wxSize(-1, -1),
                        style = self.windowStyle)
        self.frame = frame
        panel = wxPanel(frame, -1)

        fullSizer = wxFlexGridSizer(cols = 1, vgap = 0, hgap = 8)
        
        colSizer = wxFlexGridSizer(cols = 2, vgap = 0, hgap = 8)
        leftSizer = wxFlexGridSizer(cols = 1, vgap = 3)

        self.stayontop_checkbox = wxCheckBox(panel, -1, "stay on top")
        self.stayontop_checkbox.SetValue(self.config['stayontop'])
        EVT_CHECKBOX(frame, self.stayontop_checkbox.GetId(), self.setstayontop)
        leftSizer.Add(self.stayontop_checkbox, -1, wxALIGN_CENTER)
        leftSizer.Add(wxStaticText(panel, -1, ''))

        button = wxButton(panel, -1, 'use image...')
        EVT_BUTTON(frame, button.GetId(), self.selectDropTarget)
        leftSizer.Add(button, -1, wxALIGN_CENTER)
        
        self.groupSizer1Box = wxStaticBox(panel, -1, '')
        groupSizer1 = wxStaticBoxSizer(self.groupSizer1Box, wxHORIZONTAL)
        groupSizer = wxFlexGridSizer(cols = 1, vgap = 0)
        self.dropTarget = self.calls['newDropTarget']((200,200))
#        self.dropTarget = self.calls['newDropTarget']()
        self.dropTargetPtr = wxStaticBitmap(panel, -1, self.dropTarget)
        self.calls['setDropTargetRefresh'](self.dropTargetPtr.Refresh)
        self.dropTargetWidth = self.dropTarget.GetWidth()
        EVT_LEFT_DOWN(self.dropTargetPtr,self.dropTargetClick)
        EVT_ENTER_WINDOW(self.dropTargetPtr,self.calls['dropTargetHovered'])
        EVT_LEAVE_WINDOW(self.dropTargetPtr,self.calls['dropTargetUnhovered'])
        groupSizer.Add(self.dropTargetPtr,0,wxALIGN_CENTER)        
        lowerSizer1 = wxGridSizer(cols = 3)
        dirlink = wxStaticText(panel, -1, 'dir')
        dirlink.SetFont(wxFont(7, wxDEFAULT, wxNORMAL, wxNORMAL, True))
        dirlink.SetForegroundColour('blue')
        EVT_LEFT_UP(dirlink,self.selectdir)
        lowerSizer1.Add(dirlink, -1, wxALIGN_LEFT)
        lowerSizer1.Add(wxStaticText(panel, -1, ''), -1, wxALIGN_CENTER)
        filelink = wxStaticText(panel, -1, 'file')
        filelink.SetFont(wxFont(7, wxDEFAULT, wxNORMAL, wxNORMAL, True))
        filelink.SetForegroundColour('blue')
        EVT_LEFT_UP(filelink,self.selectfile)
        lowerSizer1.Add(filelink, -1, wxALIGN_RIGHT)
        
        groupSizer.Add(lowerSizer1, -1, wxALIGN_CENTER)

        self.gauge = wxGauge(panel, -1, range = 1000,
                             style = wxGA_HORIZONTAL, size = (-1,15))
        groupSizer.Add(self.gauge, 0, wxEXPAND)
        self.statustext = wxStaticText(panel, -1, 'ready',
                            style = wxALIGN_CENTER|wxST_NO_AUTORESIZE)
        self.statustext.SetFont(wxFont(7, wxDEFAULT, wxNORMAL, wxBOLD, False))
        groupSizer.Add(self.statustext, -1, wxEXPAND)
        self.choices = wxChoice(panel, -1, (-1, -1), (self.dropTargetWidth, -1),
                                    choices = [])
        self.choices.SetFont(wxFont(7, wxDEFAULT, wxNORMAL, wxNORMAL, False))
        EVT_CHOICE(self.choices, -1, self.set_thost)
        groupSizer.Add(self.choices, 0, wxEXPAND)
        cancellink = wxStaticText(panel, -1, 'cancel')
        cancellink.SetFont(wxFont(7, wxDEFAULT, wxNORMAL, wxNORMAL, True))
        cancellink.SetForegroundColour('red')
        EVT_LEFT_UP(cancellink,self.cancel)
        groupSizer.Add(cancellink, -1, wxALIGN_CENTER)
        dummyadvlink = wxStaticText(panel, -1, 'advanced')
        dummyadvlink.SetFont(wxFont(7, wxDEFAULT, wxNORMAL, wxNORMAL, False))
        dummyadvlink.SetForegroundColour('blue')
        EVT_LEFT_UP(dirlink,self.selectdir)
        groupSizer.Add(dummyadvlink, -1, wxALIGN_CENTER)
        groupSizer1.Add(groupSizer)
        leftSizer.Add(groupSizer1, -1, wxALIGN_CENTER)

        leftSizer.Add(wxStaticText(panel, -1, 'make torrent of:'),0,wxALIGN_CENTER)

        self.dirCtl = wxTextCtrl(panel, -1, '', size = (250,-1))
        leftSizer.Add(self.dirCtl, 1, wxEXPAND)
        
        b = wxBoxSizer(wxHORIZONTAL)
        button = wxButton(panel, -1, 'dir')
        EVT_BUTTON(frame, button.GetId(), self.selectdir)
        b.Add(button, 0)

        button2 = wxButton(panel, -1, 'file')
        EVT_BUTTON(frame, button2.GetId(), self.selectfile)
        b.Add(button2, 0)

        leftSizer.Add(b, 0, wxALIGN_CENTER)

        leftSizer.Add(wxStaticText(panel, -1, ''))

        simple_link = wxStaticText(panel, -1, 'back to basic mode')
        simple_link.SetFont(wxFont(-1, wxDEFAULT, wxNORMAL, wxNORMAL, True))
        simple_link.SetForegroundColour('blue')
        EVT_LEFT_UP(simple_link,self.calls['switchToBasic'])
        leftSizer.Add(simple_link, -1, wxALIGN_CENTER)

        colSizer.Add(leftSizer, -1, wxALIGN_CENTER_VERTICAL)

        gridSizer = wxFlexGridSizer(cols = 2, vgap = 6, hgap = 8)

        gridSizer.Add(wxStaticText(panel, -1, 'Torrent host:'), -1,
                      wxALIGN_RIGHT|wxALIGN_CENTER_VERTICAL)

        self.choices1 = wxChoice(panel, -1, (-1, -1), (-1, -1),
                                    choices = [])
        EVT_CHOICE(self.choices1, -1, self.set_thost1)
        gridSizer.Add(self.choices1, 0, wxEXPAND)

        b = wxBoxSizer(wxHORIZONTAL)
        button1 = wxButton(panel, -1, 'set default')
        EVT_BUTTON(frame, button1.GetId(), self.set_default_thost)
        b.Add(button1, 0)
        b.Add(wxStaticText(panel, -1, '       '))
        button2 = wxButton(panel, -1, 'delete')
        EVT_BUTTON(frame, button2.GetId(), self.delete_thost)
        b.Add(button2, 0)
        b.Add(wxStaticText(panel, -1, '       '))
        button3 = wxButton(panel, -1, 'save as...')
        EVT_BUTTON(frame, button3.GetId(), self.save_thost)
        b.Add(button3, 0)

        gridSizer.Add(wxStaticText(panel, -1, ''))
        gridSizer.Add(b, 0, wxALIGN_CENTER)

        gridSizer.Add(wxStaticText(panel, -1, ''))
        gridSizer.Add(wxStaticText(panel, -1, ''))

        gridSizer.Add(wxStaticText(panel, -1, 'single tracker url:'),0,
                      wxALIGN_RIGHT|wxALIGN_CENTER_VERTICAL)
        self.annCtl = wxTextCtrl(panel, -1, 'http://my.tracker:6969/announce')
        gridSizer.Add(self.annCtl, 0, wxEXPAND)

        a = wxFlexGridSizer(cols = 1, vgap = 3)
        a.Add(wxStaticText(panel, -1, 'tracker list:'),0,wxALIGN_RIGHT)
        a.Add(wxStaticText(panel, -1, ''))
        abutton = wxButton(panel, -1, 'copy\nannounces\nfrom\ntorrent', size = (70,70))
        EVT_BUTTON(frame, abutton.GetId(), self.announcecopy)
        a.Add(abutton, -1, wxALIGN_CENTER)
        a.Add(wxStaticText(panel, -1, DROP_HERE), -1, wxALIGN_CENTER)
        gridSizer.Add(a, -1, wxALIGN_RIGHT|wxALIGN_CENTER_VERTICAL)


        self.annListCtl = wxTextCtrl(panel, -1, '\n\n\n\n\n', wxPoint(-1,-1), (300,120),
                                            wxTE_MULTILINE|wxHSCROLL|wxTE_DONTWRAP)
        gridSizer.Add(self.annListCtl, -1, wxEXPAND)

        gridSizer.Add(wxStaticText(panel, -1, ''))
        exptext = wxStaticText(panel, -1,
                "a list of tracker urls separated by commas or whitespace\n" +
                "and on several lines -trackers on the same line will be\n" +
                "tried randomly, and all the trackers on one line\n" +
                "will be tried before the trackers on the next line.")
        exptext.SetFont(wxFont(6, wxDEFAULT, wxNORMAL, wxNORMAL, False))
        gridSizer.Add(exptext, -1, wxALIGN_CENTER)

        self.refresh_thostlist()
        self._set_thost()

        if platform == 'win32':
            self.dropTargetPtr.DragAcceptFiles(True)
            EVT_DROP_FILES(self.dropTargetPtr, self.selectdrop)
            self.groupSizer1Box.DragAcceptFiles(True)
            EVT_DROP_FILES(self.groupSizer1Box, self.selectdrop)
            abutton.DragAcceptFiles(True)
            EVT_DROP_FILES(abutton, self.announcedrop)
            self.annCtl.DragAcceptFiles(True)
            EVT_DROP_FILES(self.annCtl, self.announcedrop)
            self.annListCtl.DragAcceptFiles(True)
            EVT_DROP_FILES(self.annListCtl, self.announcedrop)

        gridSizer.Add(wxStaticText(panel, -1, ''))
        gridSizer.Add(wxStaticText(panel, -1, ''))

        gridSizer.Add(wxStaticText(panel, -1, 'piece size:'),0,
                      wxALIGN_RIGHT|wxALIGN_CENTER_VERTICAL)
        self.piece_length = wxChoice(panel, -1,
                 choices = ['automatic', '2MiB', '1MiB', '512KiB', '256KiB', '128KiB', '64KiB', '32KiB'])
        self.piece_length_list = [0,       21,     20,      19,       18,       17,      16,      15]
        self.piece_length.SetSelection(0)
        gridSizer.Add(self.piece_length)

        gridSizer.Add(wxStaticText(panel, -1, 'comment:'),0,
                      wxALIGN_RIGHT|wxALIGN_CENTER_VERTICAL)
        self.commentCtl = wxTextCtrl(panel, -1, '')
        gridSizer.Add(self.commentCtl, 0, wxEXPAND)

        gridSizer.Add(wxStaticText(panel, -1, ''))
        gridSizer.Add(wxStaticText(panel, -1, ''))

        b1 = wxButton(panel, -1, 'Cancel', size = (-1, 30))
        EVT_BUTTON(frame, b1.GetId(), self.cancel)
        gridSizer.Add(b1, 0, wxEXPAND)
        b2 = wxButton(panel, -1, 'MAKE TORRENT', size = (-1, 30))
        EVT_BUTTON(frame, b2.GetId(), self.complete)
        gridSizer.Add(b2, 0, wxEXPAND)

        gridSizer.AddGrowableCol(1)
        colSizer.Add(gridSizer, -1, wxALIGN_CENTER_VERTICAL)
        fullSizer.Add(colSizer)

 
        border = wxBoxSizer(wxHORIZONTAL)
        border.Add(fullSizer, 1, wxEXPAND | wxALL, 15)
        panel.SetSizer(border)
        panel.SetAutoLayout(True)
        border.Fit(panel)
        frame.Fit()
        frame.Show(True)

        EVT_INVOKE(frame, self.onInvoke)
        EVT_CLOSE(frame, self._close)

    def setstayontop(self, x):
        if self.stayontop_checkbox.GetValue():
            self.windowStyle |= wxSTAY_ON_TOP
        else:
            self.windowStyle &= ~wxSTAY_ON_TOP
        self.frame.SetWindowStyle(self.windowStyle)
        self.config['stayontop'] = self.stayontop_checkbox.GetValue()

    def selectdir(self, x = None):
        self.calls['dropTargetHovered']()
        dl = wxDirDialog(self.frame, style = wxDD_DEFAULT_STYLE | wxDD_NEW_DIR_BUTTON)
        if dl.ShowModal() == wxID_OK:
            self.dirCtl.SetValue(dl.GetPath())
            self.calls['dropTargetDropped']()
        else:
            self.calls['dropTargetUnhovered']()

    def selectfile(self, x = None):
        self.calls['dropTargetHovered']()
        dl = wxFileDialog (self.frame, 'Choose file to use', '', '', '', wxOPEN)
        if dl.ShowModal() == wxID_OK:
            self.dirCtl.SetValue(dl.GetPath())
            self.calls['dropTargetDropped']()
        else:
            self.calls['dropTargetUnhovered']()

    def selectdrop(self, dat):
        self.calls['dropTargetDropped']()
        for f in dat.GetFiles():
            self.complete(f)

    def announcecopy(self, x):
        dl = wxFileDialog (self.frame, 'Choose .torrent file to use', '', '', '*.torrent', wxOPEN)
        if dl.ShowModal() == wxID_OK:
            self._announcecopy(dl.GetPath(), True)

    def announcedrop(self, dat):
        self._announcecopy(dat.GetFiles()[0], True)

    def _announcecopy(self, f, external = False):
        try:
            h = open(f, 'rb')
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
            if external:
                self.choices.SetSelection(0)
                self.choices1.SetSelection(0)
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
        if not self.dirCtl.GetValue():
            dlg = wxMessageDialog(self.frame, message = 'You must select a\nfile or directory', 
                caption = 'Error', style = wxOK | wxICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return
        if not self.annCtl.GetValue():
            dlg = wxMessageDialog(self.frame, message = 'You must specify a\nsingle tracker url', 
                caption = 'Error', style = wxOK | wxICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return
        params = {'piece_size_pow2': self.piece_length_list[self.piece_length.GetSelection()]}
        annlist = self.getannouncelist()
        if len(annlist)>0:
            warnings = ''
            for tier in annlist:
                if len(tier) > 1:
                    warnings += (
                        'WARNING: You should not specify multiple trackers\n' +
                        '     on the same line of the tracker list unless\n' +
                        '     you are certain they share peer data.\n')
                    break
            if not self.annCtl.GetValue() in annlist[0]:
                    warnings += (
                        'WARNING: The single tracker url is not present in\n' +
                        '     the first line of the tracker list.  This\n' +
                        '     may produce a dysfunctional torrent.\n')
            if warnings:
                warnings += ('Are you sure you wish to produce a .torrent\n' +
                             'with these parameters?')
                dlg = wxMessageDialog(self.frame,
                        message = warnings,
                        caption = 'Warning', style = wxYES_NO | wxICON_QUESTION)
                if dlg.ShowModal() != wxID_YES:
                    dlg.Destroy()
                    return
            params['real_announce_list'] = annlist
        comment = self.commentCtl.GetValue()
        if comment != '':
            params['comment'] = comment
        self.statustext.SetLabel('working')
        self.queue.append((self.dirCtl.GetValue(), self.annCtl.GetValue(), params))
        self.go_queue()

    def go_queue(self):
        self.switchlock.acquire()
        if self.queue and not self.working:
            self.working = True
            self.statustext.SetLabel('working')
            q = self.queue.pop(0)
            MakeMetafile(q[0], q[1], q[2], self)
        self.switchlock.release()

    def cancel(self, x):
        self.switchlock.acquire()
        if self.working:
            self.working = False
            self.cancelflag.set()
            self.cancelflag = Event()
            self.queue = []
            self.statustext.SetLabel('CANCELED')
            self.calls['dropTargetError']()
        self.switchlock.release()

    def selectDropTarget(self, x):
        dl = wxFileDialog (self.frame, 'Choose image to use', join(basepath,'targets'),
                        join(join(basepath,'targets'), self.config['target']),
                        'Supported images (*.bmp,*.gif)|*.*', wxOPEN|wxHIDE_READONLY)
        if dl.ShowModal() == wxID_OK:
            try:
                self.calls['changeDropTarget'](dl.GetPath())
                self.config['target'] = dl.GetPath()
            except:
                pass

    def dropTargetClick(self, x):
        if x.GetPosition()[0] < int(self.dropTargetWidth*0.4):
            self.selectdir()
        elif x.GetPosition()[0] > int(self.dropTargetWidth*0.6):
            self.selectfile()

    def refresh_thostlist(self):
        l = []
        d = 0
        for f in listdir(join(basepath,'thosts')):
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
                self.thostselection = self.thostlist[n-1]
                self._set_thost()

    def set_thost1(self, x):
        n = self.choices1.GetSelection()
        if n != self.thostselectnum:
            self.thostselectnum = n
            self.choices.SetSelection(n)
            if n:
                self.thostselection = self.thostlist[n-1]
                self._set_thost()

    def _set_thost(self):
        self._announcecopy(join(join(basepath,'thosts'),self.thostselection))
        self.calls['setCurrentTHost'](self.thostselection)

    def set_default_thost(self, x):
        if self.thostlist:
            self.config['thost'] = self.thostselection
            self.refresh_thostlist()

    def save_thost(self, x):
        if not self.annCtl.GetValue():
            dlg = wxMessageDialog(self.frame, message = 'You must specify a\nsingle tracker url', 
                caption = 'Error', style = wxOK | wxICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return
        try:
            metainfo = {}
            metainfo['announce'] = self.annCtl.GetValue()
            annlist = self.getannouncelist()
            if len(annlist)>0:
                warnings = ''
                for tier in annlist:
                    if len(tier) > 1:
                        warnings += (
                            'WARNING: You should not specify multiple trackers\n' +
                            '     on the same line of the tracker list unless\n' +
                            '     you are certain they share peer data.\n')
                        break
                if not self.annCtl.GetValue() in annlist[0]:
                        warnings += (
                            'WARNING: The single tracker url is not present in\n' +
                            '     the first line of the tracker list.  This\n' +
                            '     may produce a dysfunctional torrent.\n')
                if warnings:
                    warnings += ('Are you sure you wish to save a torrent host\n' +
                                 'with these parameters?')
                    dlg = wxMessageDialog(self.frame,
                            message = warnings,
                            caption = 'Warning', style = wxYES_NO | wxICON_QUESTION)
                    if dlg.ShowModal() != wxID_YES:
                        dlg.Destroy()
                        return
                metainfo['announce-list'] = annlist
            metainfo = bencode(metainfo)
        except:
            return
        
        if self.thostselectnum:
            d = self.thostselection
        else:
            d = '.thost'
        dl = wxFileDialog (self.frame, 'Save tracker data as',
                           join(basepath,'thosts'), d, '*.thost',
                           wxSAVE|wxOVERWRITE_PROMPT)
        if dl.ShowModal() != wxID_OK:
            return
        d = dl.GetPath()

        try:
            f = open(d,'wb')
            f.write(metainfo)
            f.close()
            garbage, self.thostselection = os.path.split(d)
        except:
            pass
        self.refresh_thostlist()

    def delete_thost(self, x):
        dlg = wxMessageDialog(self.frame,
                message = 'Are you sure you want to delete\n'+self.thostselection[:-6]+'?', 
                caption = 'Warning', style = wxYES_NO | wxICON_EXCLAMATION)
        if dlg.ShowModal() != wxID_YES:
            dlg.Destroy()
            return
        dlg.Destroy()
        os.remove(join(join(basepath,'thosts'),self.thostselection))
        self.thostselection = None
        self.refresh_thostlist()

    def onInvoke(self, event):
        if not self.uiflag.isSet():
            apply(event.func, event.args, event.kwargs)

    def invokeLater(self, func, args = [], kwargs = {}):
        if not self.uiflag.isSet():
            wxPostEvent(self.frame, InvokeEvent(func, args, kwargs))

    def build_setgauge(self, x):
        self.invokeLater(self.on_setgauge, [x])

    def on_setgauge(self, x):
        self.gauge.SetValue(int(x*1000))

    def build_done(self):
        self.invokeLater(self.on_builddone)

    def on_builddone(self):
        self.gauge.SetValue(0)
        self.statustext.SetLabel('done!')
        self.calls['dropTargetSuccess']()
        self.working = False
        self.go_queue()

    def build_failed(self, e):
        self.invokeLater(self.on_buildfailed, [e])

    def on_buildfailed(self, e):        
        self.gauge.SetValue(0)
        self.statustext.SetLabel('ERROR')
        self.calls['dropTargetError']()
        self.working = False
        self.go_queue()

    def close(self):
        self.cancelflag = None   # this is a planned switch, don't cancel
        self.uiflag.set()
        self.frame.Close()

    def _close(self, x = None):
        self.uiflag.set()
        try:
            self.cancelflag.set()
        except:
            pass
        self.calls['saveConfig']()
        self.frame.Destroy()

        
class MakeMetafile:
    def __init__(self, d, a, params, external = None):
        self.d = d
        self.a = a
        self.params = params

        self.call = external
#        self.uiflag = external.uiflag
        self.uiflag = external.cancelflag
        Thread(target = self.complete).start()

    def complete(self):
        try:
            make_meta_file(self.d, self.a, self.params, self.uiflag,
                            self.call.build_setgauge, progress_percent = 1)
            if not self.uiflag.isSet():
                self.call.build_done()
        except (OSError, IOError), e:
            self.failed(e)
        except Exception, e:
            print_exc()
            self.failed(e)

    def failed(self, e):
        e = str(e)
        self.call.build_failed(e)
        dlg = wxMessageDialog(self.frame, message = 'Error - ' + e, 
            caption = 'Error', style = wxOK | wxICON_ERROR)
        dlg.ShowModal()
        dlg.Destroy()


class T_make:
    def __init__(self):
        self.configobj = wxConfig('BitTorrent_T-make',style=wxCONFIG_USE_LOCAL_FILE)
        self.getConfig()
        self.currentTHost = self.config['thost']
#        self.d = AdvancedDownloadInfo(self.config, self.getCalls())
        self.d = BasicDownloadInfo(self.config, self.getCalls())

    def getConfig(self):
        config = {}
        try:
            config['stayontop'] = self.configobj.ReadInt('stayontop',True)
        except:
            config['stayontop'] = True
            self.configobj.WriteInt('stayontop',True)
        try:
            config['target'] = self.configobj.Read('target','default.gif')
        except:
            config['target'] = 'default.gif'
            self.configobj.Write('target','default.gif')
        try:
            config['thost'] = self.configobj.Read('thost','')
        except:
            config['thost'] = ''
            self.configobj.Write('thost','')
        self.configobj.Flush()
        self.config = config

    def saveConfig(self):
        self.configobj.WriteInt('stayontop',self.config['stayontop'])
        self.configobj.Write('target',self.config['target'])
        self.configobj.Write('thost',self.config['thost'])
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

    def newDropTarget(self, wh = None):
        if wh:
            self.dropTarget = wxEmptyBitmap(wh[0],wh[1])
            try:
                self.changeDropTarget(self.config['target'])
            except:
                pass
        else:
            try:
                self.dropTarget = self._dropTargetRead(self.config['target'])
            except:
                try:
                    self.dropTarget = self._dropTargetRead('default.gif')
                    self.config['target'] = 'default.gif'
                    self.saveConfig()
                except:
                    self.dropTarget = wxEmptyBitmap(100,100)
        return self.dropTarget

    def setDropTargetRefresh(self, refreshfunc):
        self.dropTargetRefresh = refreshfunc

    def changeDropTarget(self, new):
        bmp = self._dropTargetRead(new)
        w1,h1 = self.dropTarget.GetWidth(),self.dropTarget.GetHeight()
        w,h = bmp.GetWidth(),bmp.GetHeight()
        x1,y1 = int((w1-w)/2.0),int((h1-h)/2.0)
        bbdata = wxMemoryDC()
        bbdata.SelectObject(self.dropTarget)
        bbdata.SetPen(wxTRANSPARENT_PEN)
        bbdata.SetBrush(wxBrush(wx.wxSystemSettings_GetColour(wxSYS_COLOUR_MENU),wxSOLID))
        bbdata.DrawRectangle(0,0,w1,h1)
        bbdata.SetPen(wxBLACK_PEN)
        bbdata.SetBrush(wxTRANSPARENT_BRUSH)
        bbdata.DrawRectangle(x1-1,y1-1,w+2,h+2)
        bbdata.DrawBitmap(bmp,x1,y1,True)
        try:
            self.dropTargetRefresh()
        except:
            pass

    def _dropTargetRead(self, new):
        a,b = os.path.split(new)
        if a and a != join(basepath,'targets'):
            if a != join(basepath,'targets'):
                b1,b2 = os.path.splitext(b)
                z = 0
                while os.path.isfile(join(join(basepath,'targets'),b)):
                    z += 1
                    b = b1+'('+str(z)+')'+b2
                shutil.copyfile(newname,join(join(basepath,'targets'),b))
            new = b
        name = join(join(basepath,'targets'),new)
        garbage, e = os.path.splitext(new.lower())
        if e == '.gif':
            bmp = wxBitmap(name, wxBITMAP_TYPE_GIF)
        elif e == '.bmp':
            bmp = wxBitmap(name, wxBITMAP_TYPE_BMP)
        else:
            assert False
        return bmp

    def dropTargetHovered(self, x = None):
        pass

    def dropTargetUnhovered(self, x = None):
        pass

    def dropTargetDropped(self, x = None):
        pass

    def dropTargetSuccess(self, x = None):
        pass

    def dropTargetError(self, x = None):
        pass

    def switchToBasic(self, x = None):
        self.d.close()
        self.d = BasicDownloadInfo(self.config, self.getCalls())
        
    def switchToAdvanced(self, x = None):
        self.d.close()
        self.d = AdvancedDownloadInfo(self.config, self.getCalls())
        


class btWxApp(wxApp):
    def OnInit(self):
        self.APP = T_make()
        return True

if __name__ == '__main__':
    btWxApp().MainLoop()
