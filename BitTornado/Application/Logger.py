import os
import io
import time
import threading


class Logger(object):
    """Simple, append-only logging manager

    Shares an open log file in a thread-safe way, accepting file paths
    or open file handles.

    Singleton object - need only set log file once before writing.
    """
    _instance = None
    create_lock = threading.Lock()
    file_lock = threading.Lock()
    ref = None
    fobj = None

    def __new__(cls, *args, **kwargs):
        with cls.create_lock:
            if cls._instance is None:
                cls._instance = object.__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, ref=None):
        super().__init__(self)
        if ref is not None:
            self.set_ref(ref)

    def set_ref(self, ref):
        with self.file_lock:
            if isinstance(ref, str):
                ref = os.path.realpath(ref)
                path = True
            elif isinstance(ref, io.TextIOWrapper):
                path = False
            elif ref is not None:
                raise TypeError("Logger ref must be path or file handle")

            if self.ref == ref:
                return
            if self.fobj is not None and self.fobj is not self.ref:
                self.fobj.close()

            self.ref = ref
            self.fobj = open(ref, 'a') if path else ref

    def write(self, text):
        with self.file_lock:
            return self.fobj.write(text)

    def reopen(self, signum, frame):
        if self.ref is self.fobj:
            self.write("** Cannot reopen logfile without known path")
            return
        self.fobj.close()
        self.fobj = open(self.ref, 'a')


class Logging(object):
    """Logging mixin"""
    debugging = False
    logger = Logger()

    def log(self, msg):
        try:
            self.logger.write('{} {}'.format(time.ctime(), msg))
        except AttributeError:
            raise RuntimeError("Logger does not have an open log")

    def debug(self, msg):
        if self.debugging:
            self.log('DEBUG <{}> {}'.format(self.__class__.__name__, msg))
