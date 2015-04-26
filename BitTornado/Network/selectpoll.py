import select
import time
import bisect

POLLIN = 1
POLLOUT = 2
POLLERR = 8
POLLHUP = 16


class poll(object):
    def __init__(self):
        self.rlist = []
        self.wlist = []

    def register(self, f, t):
        if not isinstance(f, int):
            f = f.fileno()
        if t & POLLIN:
            insert(self.rlist, f)
        else:
            remove(self.rlist, f)
        if t & POLLOUT:
            insert(self.wlist, f)
        else:
            remove(self.wlist, f)

    def unregister(self, f):
        if not isinstance(f, int):
            f = f.fileno()
        remove(self.rlist, f)
        remove(self.wlist, f)

    def poll(self, timeout=None):
        if self.rlist or self.wlist:
            try:
                r, w, _ = select.select(self.rlist, self.wlist, [], timeout)
            except ValueError:
                return None
        else:
            if timeout:
                time.sleep(timeout / 1000)
            return []
        return [(s, POLLIN) for s in r] + [(s, POLLOUT) for s in w]


def remove(list, item):
    i = bisect.bisect(list, item)
    if i > 0 and list[i - 1] == item:
        del list[i - 1]


def insert(list, item):
    i = bisect.bisect(list, item)
    if i == 0 or list[i - 1] != item:
        list.insert(i, item)
