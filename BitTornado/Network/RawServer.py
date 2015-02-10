import sys
import bisect
import socket
import select
import threading
from cStringIO import StringIO
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
        self.timeout_check_interval = timeout_check_interval
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
        self.add_task(self.scan_for_timeouts, timeout_check_interval)

    def get_exception_flag(self):
        return self.excflag

    def _add_task(self, func, delay, id=None):
        assert float(delay) >= 0
        bisect.insort(self.funcs, (clock() + delay, func, id))

    def add_task(self, func, delay=0, id=None):
        assert float(delay) >= 0
        self.externally_added.append((func, delay, id))

    def scan_for_timeouts(self):
        self.add_task(self.scan_for_timeouts, self.timeout_check_interval)
        self.sockethandler.scan_for_timeouts()

    def bind(self, port, bind='', reuse=False, ipv6_socket_style=1,
             upnp=False):
        self.sockethandler.bind(port, bind, reuse, ipv6_socket_style, upnp)

    def find_and_bind(self, minport, maxport, bind='', reuse=False,
                      ipv6_socket_style=1, upnp=0, randomizer=False):
        return self.sockethandler.find_and_bind(
            minport, maxport, bind, reuse, ipv6_socket_style, upnp, randomizer)

    def start_connection_raw(self, dns, socktype, handler=None):
        return self.sockethandler.start_connection_raw(dns, socktype, handler)

    def start_connection(self, dns, handler=None, randomize=False):
        return self.sockethandler.start_connection(dns, handler, randomize)

    def get_stats(self):
        return self.sockethandler.get_stats()

    def pop_external(self):
        while self.externally_added:
            (a, b, c) = self.externally_added.pop(0)
            self._add_task(a, b, c)

    def listen_forever(self, handler):
        self.sockethandler.set_handler(handler)
        try:
            while not self.doneflag.isSet():
                try:
                    self.pop_external()
                    self._kill_tasks()
                    if self.funcs:
                        period = self.funcs[0][0] + 0.001 - clock()
                    else:
                        period = 2 ** 30
                    if period < 0:
                        period = 0
                    events = self.sockethandler.do_poll(period)
                    if self.doneflag.isSet():
                        return
                    while self.funcs and self.funcs[0][0] <= clock():
                        _, func, id = self.funcs.pop(0)
                        if id in self.tasks_to_kill:
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
                    if self.doneflag.isSet():
                        return
                    self.sockethandler.close_dead()
                except (SystemError, MemoryError) as e:
                    self.failfunc(str(e))
                    return
                except select.error:
                    if self.doneflag.isSet():
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
        return self.finished.isSet()

    def wait_until_finished(self):
        self.finished.wait()

    def _kill_tasks(self):
        if self.tasks_to_kill:
            self.funcs = [(t, func, tid) for (t, func, tid) in self.funcs
                          if tid not in self.tasks_to_kill]
            self.tasks_to_kill = set()

    def kill_tasks(self, id):
        self.tasks_to_kill.add(id)

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
