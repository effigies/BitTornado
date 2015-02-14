"""Provide a non-decreasing clock() function.

In Windows, time.clock() provides number of seconds from first call, so use
that.

In Unix, time.clock() is CPU time, and time.time() reports system time, which
may not be non-decreasing."""

import time
import sys

_MAXFORWARD = 100
_FUDGE = 1


class RelativeTime(object):     # pylint: disable=R0903
    """Non-decreasing time implementation for Unix"""
    def __init__(self):
        self.time = time.time()
        self.offset = 0

    def get_time(self):
        """Calculate a non-decreasing time representation"""
        systemtime = time.time()

        now = systemtime + self.offset

        if self.time < now < self.time + _MAXFORWARD:
            self.time = now
        else:
            # If time jump is outside acceptable bounds, move ahead one second
            # and note the offset
            self.time += _FUDGE
            self.offset = self.time - systemtime

        return self.time

if sys.platform != 'win32':
    clock = RelativeTime().get_time     # pylint: disable=C0103
else:
    from time import clock
