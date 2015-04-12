"""Wrapper on character arrays that avoids garbage-collection/reallocation.

Example:

from PieceBuffer import PieceBuffer
x = PieceBuffer()
...
x.release()
"""

import threading
import array
import types


class Pool(list):
    """Thread-safe stack of objects not currently in use, generates new object
    when empty.

    Use as a decorator. Decorated classes must have init() method to
    prepare them for reuse."""
    def __init__(self, klass):
        super(Pool, self).__init__()

        self.lock = threading.Lock()
        klass.release = types.MethodType(self.append, None, klass)
        self.klass = klass

    def __call__(self):
        "Get object from pool, generating a new one if empty"
        with self.lock:
            obj = self.pop() if self else self.klass()
        obj.init()
        return obj


@Pool
class PieceBuffer(object):
    """Non-shrinking array"""
    def __init__(self):
        self.buf = array.array('c')
        self.length = 0

    def init(self):
        """Prepare buffer for use."""
        self.length = 0

    def append(self, string):
        """Extend buffer with characters in string"""
        length = self.length + len(string)
        self.buf[self.length:length] = array.array('c', string)
        self.length = length

    def __len__(self):
        return self.length

    def __getslice__(self, i, j):
        if j > self.length:
            j = self.length
        if j < 0:
            j += self.length
        if i == 0 and j == self.length == len(self.buf):
            return self.buf  # optimization
        return self.buf[i:j]

    def getarray(self):
        """Get array containing contents of buffer"""
        return self.buf[:self.length]
