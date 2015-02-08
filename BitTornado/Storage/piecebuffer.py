import threading
from array import array


class SingleBuffer(object):
    """Non-shrinking array"""
    def __init__(self, pool):
        self.pool = pool
        self.buf = array('c')

    def init(self):
        self.length = 0

    def append(self, s):
        l = self.length + len(s)
        self.buf[self.length:l] = array('c', s)
        self.length = l

    def __len__(self):
        return self.length

    def __getslice__(self, a, b):
        if b > self.length:
            b = self.length
        if b < 0:
            b += self.length
        if a == 0 and b == self.length == len(self.buf):
            return self.buf  # optimization
        return self.buf[a:b]

    def getarray(self):
        return self.buf[:self.length]

    def release(self):
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
