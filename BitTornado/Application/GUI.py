"""Common elements for GUI applications"""

import wx
import threading

wxEVT_INVOKE = wx.NewEventType()


class InvokeEvent(wx.PyEvent):
    """Event for passing a function to be run to the main thread"""
    def __init__(self, func, args, kwargs):
        super(InvokeEvent, self).__init__()
        self.SetEventType(wxEVT_INVOKE)
        self.func = func
        self.args = args
        self.kwargs = kwargs


class DelayedEvents(object):
    def __init__(self, win=None, uiflag=None):
        if uiflag is None:
            uiflag = threading.Event()
        self.uiflag = uiflag

        self.win = win
        if win is not None:
            win.Connect(-1, -1, wxEVT_INVOKE, self.onInvoke)

    def setDelayWindow(self, win):
        if self.win is not None:
            self.win.Disconnect(-1, -1, wxEVT_INVOKE, self.onInvoke)

        self.win = win
        win.Connect(-1, -1, wxEVT_INVOKE, self.onInvoke)

    def onInvoke(self, event):
        if not self.uiflag.isSet():
            try:
                event.func(*event.args, **event.kwargs)
            except Exception:
                self.exception()

    def invokeLater(self, func, *args, **kwargs):
        if not self.uiflag.isSet():
            wx.PostEvent(self.win, InvokeEvent(func, args, kwargs))

    def exception(self):
        pass


def callback(func):
    def cback(self, *args, **kwargs):
        self.invokeLater(func, self, *args, **kwargs)
    return cback


def StaticText(panel, text, font, underline=False, color=None,
               style=wx.ALIGN_LEFT):
    stext = wx.StaticText(panel, -1, text, style=style)
    stext.SetFont(wx.Font(font, wx.DEFAULT, wx.NORMAL, wx.NORMAL, underline))
    if color is not None:
        stext.SetForegroundColour(color)
    return stext
