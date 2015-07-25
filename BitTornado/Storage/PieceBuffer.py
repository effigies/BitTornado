"""Wrapper on character arrays that avoids garbage-collection/reallocation.

Example:

from PieceBuffer import PieceBuffer
x = PieceBuffer()
...
x.release()
"""

import threading
import array
import warnings


def pool(klass):
    """Thread-safe pool of objects not currently in use, generates new object
    when empty.

    Use as a decorator. Decorated classes must have init() method to
    prepare them for reuse."""
    lock = threading.Lock()
    pool = set()

    orig_new = klass.__new__
    orig_init = klass.__init__

    def __new__(cls, *args, **kwargs):
        "Get object from pool, generating a new one if empty"
        with lock:
            if pool:
                obj = pool.pop()
                obj._used = True
                return obj
        return orig_new(cls, *args, **kwargs)
    klass.__new__ = __new__

    def __init__(self, *args, **kwargs):
        if hasattr(self, '_used'):
            self.init()
            del self._used
            return

        orig_init(self, *args, **kwargs)
    klass.__init__ = __init__

    def release(self):
        """Release for reuse"""
        if self in pool:
            warnings.warn(RuntimeWarning('Attempting double-release of ' +
                                         klass.__name__))
        else:
            pool.add(self)
    klass.release = release

    return klass


@pool
class PieceBuffer(object):
    """Non-shrinking array"""
    def __init__(self):
        self.buf = array.array('B')
        self.length = 0

    def init(self):
        """Prepare buffer for use."""
        self.length = 0

    def append(self, string):
        """Extend buffer with characters in string"""
        length = self.length + len(string)
        self.buf[self.length:length] = array.array('B', string)
        self.length = length

    def __len__(self):
        return self.length

    def __getitem__(self, slc):
        if isinstance(slc, slice):
            start, stop, step = slc.start, slc.stop, slc.step

            forward = step is None or step > 0

            if start is None:
                start = 0 if forward else self.length
            if stop is None:
                stop = self.length if forward else 0

            if stop < 0:
                stop %= self.length
            if start < 0:
                start %= self.length
            if stop > self.length and forward:
                stop = self.length
            if start > self.length and not forward:
                start = self.length

            if start == 0 and stop == self.length == len(self.buf) and \
                    step in (None, 1):
                return self.buf  # optimization
            slc = slice(start, stop, step)
        elif not -self.length <= slc < self.length:
            raise IndexError('SingleBuffer index out of range')
        elif slc < 0:
            slc += self.length
        return self.buf[slc]

    def getarray(self):
        """Get array containing contents of buffer"""
        return self.buf[:self.length]
