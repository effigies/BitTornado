try:
    import wx
except ImportError:
    raise ImportError('wxPython is not installed or has not been installed properly.')

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
