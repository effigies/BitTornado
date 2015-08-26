import sys
import bisect
import socket
import select
import threading
from io import StringIO
from traceback import print_exc
from .SocketHandler import SocketHandler
from BitTornado.clock import clock


def autodetect_ipv6():
    try:
        assert socket.has_ipv6
        socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    except (AssertionError, socket.error):
        return 0
    return 1


def autodetect_socket_style():
    if sys.platform.find('linux') < 0:
        return 1
    else:
        try:
            with open('/proc/sys/net/ipv6/bindv6only', 'r') as f:
                dual_socket_style = int(f.read())
            return int(not dual_socket_style)
        except (IOError, ValueError):
            return 0


READSIZE = 32768


class RawServer(object):
    def __init__(self, doneflag, timeout_check_interval, timeout, noisy=True,
                 ipv6_enable=True, failfunc=lambda x: None, errorfunc=None,
                 sockethandler=None, excflag=threading.Event()):
        self.timeout_check_interval = max(timeout_check_interval, 0)
        self.timeout = timeout
        self.servers = {}
        self.single_sockets = {}
        self.dead_from_write = []
        self.doneflag = doneflag
        self.noisy = noisy
        self.failfunc = failfunc
        self.errorfunc = errorfunc
        self.exccount = 0
        self.funcs = []
        self.externally_added = []
        self.finished = threading.Event()
        self.tasks_to_kill = set()
        self.excflag = excflag

        if sockethandler is None:
            sockethandler = SocketHandler(timeout, ipv6_enable, READSIZE)
        self.sockethandler = sockethandler

        # Transparently pass sockethandler functions through
        self.find_and_bind = sockethandler.find_and_bind
        self.start_connection = sockethandler.start_connection
        self.get_stats = sockethandler.get_stats
        # XXX Following don't appear to be used; consider removing
        self.bind = sockethandler.bind
        self.start_connection_raw = sockethandler.start_connection_raw

        self.add_task(self.scan_for_timeouts, timeout_check_interval)

    def get_exception_flag(self):
        return self.excflag

    def add_task(self, func, delay=0, tid=None):
        assert float(delay) >= 0
        self.externally_added.append((func, delay, tid))

    def pop_external(self):
        """Prepare tasks queued with add_task to be run in the listen_forever
        loop."""
        to_add, self.externally_added = self.externally_added, []
        for (func, delay, tid) in to_add:
            if tid not in self.tasks_to_kill:
                bisect.insort(self.funcs, (clock() + delay, func, tid))

    def scan_for_timeouts(self):
        self.add_task(self.scan_for_timeouts, self.timeout_check_interval)
        self.sockethandler.scan_for_timeouts()

    def listen_forever(self, handler):
        self.sockethandler.set_handler(handler)
        try:
            while not self.doneflag.is_set():
                try:
                    self.pop_external()
                    self._kill_tasks()
                    if self.funcs:
                        period = max(0, self.funcs[0][0] + 0.001 - clock())
                    else:
                        period = 2 ** 30
                    events = self.sockethandler.do_poll(period)
                    if self.doneflag.is_set():
                        return
                    while self.funcs and self.funcs[0][0] <= clock():
                        _, func, tid = self.funcs.pop(0)
                        if tid in self.tasks_to_kill:
                            pass
                        try:
#                            print func.func_name
                            func()
                        except (SystemError, MemoryError) as e:
                            self.failfunc(str(e))
                            return
                        except KeyboardInterrupt:
#                            self.exception(True)
                            return
                        except Exception:
                            if self.noisy:
                                self.exception()
                    self.sockethandler.close_dead()
                    self.sockethandler.handle_events(events)
                    if self.doneflag.is_set():
                        return
                    self.sockethandler.close_dead()
                except (SystemError, MemoryError) as e:
                    self.failfunc(str(e))
                    return
                except select.error:
                    if self.doneflag.is_set():
                        return
                except KeyboardInterrupt:
#                    self.exception(True)
                    return
                except Exception:
                    self.exception()
                if self.exccount > 10:
                    return
        finally:
#            self.sockethandler.shutdown()
            self.finished.set()

    def is_finished(self):
        return self.finished.is_set()

    def wait_until_finished(self):
        self.finished.wait()

    def _kill_tasks(self):
        if self.tasks_to_kill:
            self.funcs = [(t, func, tid) for (t, func, tid) in self.funcs
                          if tid not in self.tasks_to_kill]
            self.tasks_to_kill = set()

    def kill_tasks(self, tid):
        self.tasks_to_kill.add(tid)

    def exception(self, kbint=False):
        if not kbint:
            self.excflag.set()
        self.exccount += 1
        if self.errorfunc is None:
            print_exc()
        else:
            data = StringIO()
            print_exc(file=data)
#            print data.getvalue()   # report exception here too
            # don't report here if it's a keyboard interrupt
            if not kbint:
                self.errorfunc(data.getvalue())

    def shutdown(self):
        self.sockethandler.shutdown()
