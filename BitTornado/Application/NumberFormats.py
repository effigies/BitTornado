"""Number formatting utilities"""


def formatInterval(secs, fmt):
    """Format an interval of length secs seconds according to format string
    fmt.

    fmt may contain labeled references {h}, {m} and {s} for hours, minutes
    and seconds. e.g. fmt = '{h:d}:{m:02d}:{s:02d}'"""
    try:
        secs = int(secs)
    except TypeError, ValueError:
        return None
    if secs == 0:
        return None
    if not 0 < secs < 5184000:        # 60 days
        return '<unknown>'
    mins, secs = divmod(secs, 60)
    hours, mins = divmod(mins, 60)
    return fmt.format(h=hours, m=mins, s=secs)


def formatIntText(secs):
    """Format an interval of length secs seconds with a textual representation

    e.g. formatIntText(9861) = '2 hours 44 min 21 sec'"""
    if secs >= 7200:
        fmt = '{h:d} hours {m:02d} min {s:02d} sec'
    elif secs >= 3600:
        fmt = '{h:d} hour {m:02d} min {s:02d} sec'
    else:
        fmt = '{m:d} min {s:02d} sec'
    return formatInterval(secs, fmt)


def formatIntClock(secs):
    """Format an interval of length secs seconds in h:mm:ss notation"""
    return formatInterval(secs, '{h:d}:{m:02d}:{s:02d}')


def formatSize(size, std='IEC'):
    """Format number of bytes according to IEC or SI prefixes.

    IEC prefixes:
        1024  B = 1 KiB
        1024KiB = 1 MiB
        ...

    SI prefixes:
        1000 B = 1 KB
        1000KB = 1 MB
        ...

    This function moves to the next unit at 1000, even for IEC units. So
    1000KiB will be shown as 0.98MiB.
    """
    if size < 1000:
        order = 0
        fmtstring = '{:.0f} B'
    elif std == 'IEC':
        for order, prefix in enumerate("KMGTPEZY", 1):
            if size < 1000 * 2.0 ** (10 * order):
                fmtstring = '{:.2f}' + prefix + 'iB'
                size /= 2.0 ** (10 * order)
                break
    elif std.lower() == 'SI':
        for order, prefix in enumerate("KMGTPEZY", 1):
            if size < 1000 ** (order + 1):
                fmtstring = '{:.2f}' + prefix + 'B'
                size /= 1000.0 ** order
                break

    return fmtstring.format(size)
