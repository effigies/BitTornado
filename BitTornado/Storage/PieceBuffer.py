"""Wrapper on character arrays that avoids garbage-collection/reallocation.

Example:

from PieceBuffer import PieceBuffer
x = PieceBuffer()
...
x.release()
"""

import threading
import array


class SingleBuffer(object):
    """Non-shrinking array"""
    def __init__(self, pool):
        self.pool = pool
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

    def release(self):
        """Return buffer to pool for reallocation"""
        self.pool.release(self)


class BufferPool(list):
    """Thread-safe stack of buffers not currently in use, generates new buffer
    when empty"""
    release = list.append

    def __init__(self):
        self.lock = threading.Lock()
        super(BufferPool, self).__init__()

    def new(self):
        "Get buffer from pool, generating a new one if empty"
        with self.lock:
            if self:
                buf = self.pop()
            else:
                buf = SingleBuffer(self)
            buf.init()
        return buf

_pool = BufferPool()
PieceBuffer = _pool.new
