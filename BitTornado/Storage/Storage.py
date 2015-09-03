import os
import time
import bisect
import threading
from .PieceBuffer import PieceBuffer

DEBUG = False

if DEBUG:
    import traceback

MAXREADSIZE = 32768
MAXLOCKSIZE = 1000000000
MAXLOCKRANGE = 3999999999   # only lock first 4 gig of file


class Storage:
    def __init__(self, files, piece_length, doneflag, config,
                 disabled_files=None):
        # can raise IOError and ValueError
        self.files = files                      # [(fname, length)]
        self.piece_length = piece_length
        self.doneflag = doneflag
        self.disabled = [False] * len(files)
        self.file_ranges = []
        self.disabled_ranges = []
        self.working_ranges = []
        numfiles = 0
        total = 0
        #so_far = 0
        self.handles = {}       # {fname: fileh}
        self.whandles = set()   # {fname}
        self.tops = {}          # {fname: length}
        self.sizes = {}         # {fname: size}
        self.mtimes = {}        # {fname: mtime}
        if config.get('lock_files', True):
            self.lock_file = self._lock_file
            self.unlock_file = self._unlock_file
        else:
            self.lock_file = self.unlock_file = lambda x1, x2: None
        self.lock_while_reading = config.get('lock_while_reading', False)
        self.lock = threading.Lock()

        if not disabled_files:
            disabled_files = [False] * len(files)

        for (fname, length), disabled in zip(files, disabled_files):
            if doneflag.is_set():   # bail out if doneflag is set
                return
            self.disabled_ranges.append(None)
            if length == 0:
                self.file_ranges.append(None)
                self.working_ranges.append([])
            else:
                frange = (total, total + length, 0, fname)
                self.file_ranges.append(frange)
                self.working_ranges.append([frange])
                numfiles += 1
                total += length
                if disabled:
                    l = 0
                else:
                    if os.path.exists(fname):
                        l = os.path.getsize(fname)
                        if l > length:
                            with open(fname, 'rb+') as h:
                                h.truncate(length)
                                h.flush()
                            l = length
                    else:
                        l = 0
                        with open(fname, 'wb+') as h:
                            h.flush()
                    self.mtimes[fname] = os.path.getmtime(fname)
                self.tops[fname] = l
                self.sizes[fname] = length
                #so_far += l

        self.total_length = total
        self._reset_ranges()

        self.max_files_open = config['max_files_open']
        self.handlebuffer = [] if 0 < self.max_files_open < numfiles else None

    if os.name == 'nt':
        def _lock_file(self, name, fileh):
            import msvcrt
            for p in range(0, min(self.sizes[name], MAXLOCKRANGE),
                           MAXLOCKSIZE):
                fileh.seek(p)
                msvcrt.locking(fileh.fileno(), msvcrt.LK_LOCK,
                               min(MAXLOCKSIZE, self.sizes[name] - p))

        def _unlock_file(self, name, fileh):
            import msvcrt
            for p in range(0, min(self.sizes[name], MAXLOCKRANGE),
                           MAXLOCKSIZE):
                fileh.seek(p)
                msvcrt.locking(fileh.fileno(), msvcrt.LK_UNLCK,
                               min(MAXLOCKSIZE, self.sizes[name] - p))

    elif os.name == 'posix':
        def _lock_file(self, name, fileh):
            import fcntl
            fcntl.flock(fileh.fileno(), fcntl.LOCK_EX)

        def _unlock_file(self, name, fileh):
            import fcntl
            fcntl.flock(fileh.fileno(), fcntl.LOCK_UN)

    else:
        def _lock_file(self, name, fileh):
            pass

        def _unlock_file(self, name, fileh):
            pass

    def was_preallocated(self, pos, length):
        for fname, _, end in self._intervals(pos, length):
            if self.tops.get(fname, 0) < end:
                return False
        return True

    def _sync(self, fname):
        self._close(fname)
        if self.handlebuffer:
            self.handlebuffer.remove(fname)

    def sync(self):
        # may raise IOError or OSError
        for fname in list(self.whandles):
            self._sync(fname)

    def set_readonly(self, fileidx=None):
        if fileidx is None:
            self.sync()
            return
        fname = self.files[fileidx][0]
        if fname in self.whandles:
            self._sync(fname)

    def get_total_length(self):
        return self.total_length

    def _open(self, fname, mode):
        if fname in self.mtimes:
            try:
                if self.handlebuffer is not None:
                    assert os.path.getsize(fname) == self.tops[fname]
                    newmtime = os.path.getmtime(fname)
                    oldmtime = self.mtimes[fname]
                    assert newmtime <= oldmtime + 1
                    assert newmtime >= oldmtime - 1
            except AssertionError:
                if DEBUG:
                    print('{} modified: ({}) != ({}) ?'.format(
                        fname,
                        time.strftime('%x %X',
                                      time.localtime(self.mtimes[fname])),
                        time.strftime('%x %X',
                                      time.localtime(os.path.getmtime(fname)))
                        ))
                raise IOError('modified during download')
        try:
            return open(fname, mode)
        except IOError as e:
            if DEBUG:
                traceback.print_exc()
            raise e

    def _close(self, fname):
        fileh = self.handles[fname]
        del self.handles[fname]
        if fname in self.whandles:
            self.whandles.remove(fname)
            fileh.flush()
            self.unlock_file(fname, fileh)
            fileh.close()
            self.tops[fname] = os.path.getsize(fname)
            self.mtimes[fname] = os.path.getmtime(fname)
        else:
            if self.lock_while_reading:
                self.unlock_file(fname, fileh)
            fileh.close()

    def _close_file(self, fname):
        if fname not in self.handles:
            return
        self._close(fname)
        if self.handlebuffer:
            self.handlebuffer.remove(fname)

    def _get_file_handle(self, fname, for_write):
        if fname in self.handles:
            if for_write and fname not in self.whandles:
                self._close(fname)
                try:
                    fileh = self._open(fname, 'rb+')
                    self.handles[fname] = fileh
                    self.whandles.add(fname)
                    self.lock_file(fname, fileh)
                except (IOError, OSError) as e:
                    if DEBUG:
                        traceback.print_exc()
                    raise IOError('unable to reopen ' + fname + ': ' + str(e))

            if self.handlebuffer:
                if self.handlebuffer[-1] != fname:
                    self.handlebuffer.remove(fname)
                    self.handlebuffer.append(fname)
            elif self.handlebuffer is not None:
                self.handlebuffer.append(fname)
        else:
            try:
                if for_write:
                    fileh = self._open(fname, 'rb+')
                    self.handles[fname] = fileh
                    self.whandles.add(fname)
                    self.lock_file(fname, fileh)
                else:
                    fileh = self._open(fname, 'rb')
                    self.handles[fname] = fileh
                    if self.lock_while_reading:
                        self.lock_file(fname, fileh)
            except (IOError, OSError) as e:
                if DEBUG:
                    traceback.print_exc()
                raise IOError('unable to open ' + fname + ': ' + str(e))

            if self.handlebuffer is not None:
                self.handlebuffer.append(fname)
                if len(self.handlebuffer) > self.max_files_open:
                    self._close(self.handlebuffer.pop(0))

        return self.handles[fname]

    def _reset_ranges(self):
        self.ranges = []
        for l in self.working_ranges:
            self.ranges.extend(l)
            self.begins = [i[0] for i in self.ranges]

    def _intervals(self, pos, amount):
        ints = []
        stop = pos + amount
        p = bisect.bisect(self.begins, pos) - 1
        while p < len(self.ranges):
            begin, end, offset, fname = self.ranges[p]
            if begin >= stop:
                break
            ints.append((fname, offset + max(pos, begin) - begin,
                         offset + min(end, stop) - begin))
            p += 1
        return ints

    def read(self, pos, amount, flush_first=False):
        pbuf = PieceBuffer()
        for fname, pos, end in self._intervals(pos, amount):
            if DEBUG:
                print('reading {} from {} to {}'.format(fname, pos, end))
            with self.lock:
                fileh = self._get_file_handle(fname, False)
                if flush_first and fname in self.whandles:
                    fileh.flush()
                    os.fsync(fileh)
                fileh.seek(pos)
                while pos < end:
                    length = min(end - pos, MAXREADSIZE)
                    data = fileh.read(length)
                    if len(data) != length:
                        raise IOError('error reading data from ' + fname)
                    pbuf.append(data)
                    pos += length
        return pbuf

    def write(self, pos, s):
        # might raise an IOError
        total = 0
        for fname, begin, end in self._intervals(pos, len(s)):
            if DEBUG:
                print('writing {} from {} to {}'.format(fname, pos, end))
            with self.lock:
                fileh = self._get_file_handle(fname, True)
                fileh.seek(begin)
                fileh.write(s[total:total + end - begin])
            total += end - begin

    def top_off(self):
        for begin, end, offset, fname in self.ranges:
            l = offset + end - begin
            if l > self.tops.get(fname, 0):
                with self.lock:
                    fileh = self._get_file_handle(fname, True)
                    fileh.seek(l - 1)
                    fileh.write(chr(0xFF))

    def flush(self):
        # may raise IOError or OSError
        for fname in self.whandles:
            with self.lock:
                self.handles[fname].flush()

    def close(self):
        for fname, fileh in self.handles.items():
            try:
                self.unlock_file(fname, fileh)
            except IOError:
                pass
            try:
                fileh.close()
            except IOError:
                pass
        self.handles = {}
        self.whandles = set()
        self.handlebuffer = None

    def _get_disabled_ranges(self, fileidx):
        if not self.file_ranges[fileidx]:
            return ((), (), ())
        r = self.disabled_ranges[fileidx]
        if r:
            return r
        start, end, offset, fname = self.file_ranges[fileidx]
        if DEBUG:
            print('calculating disabled range for ' + self.files[fileidx][0])
            print('bytes: ' + str(start) + '-' + str(end))
            print('file spans pieces {}-{}'.format(
                int(start / self.piece_length),
                int((end - 1) / self.piece_length) + 1))
        pieces = list(range(int(start / self.piece_length),
                            int((end - 1) / self.piece_length) + 1))
        offset = 0
        disabled_files = []
        if len(pieces) == 1:
            if start % self.piece_length == 0 and \
                    end % self.piece_length == 0:   # happens to be a single,
                                                    # perfect piece
                working_range = [(start, end, offset, fname)]
                update_pieces = []
            else:
                midfile = os.path.join(self.bufferdir, str(fileidx))
                working_range = [(start, end, 0, midfile)]
                disabled_files.append((midfile, start, end))
                length = end - start
                self.sizes[midfile] = length
                piece = pieces[0]
                update_pieces = [(piece, start - (piece * self.piece_length),
                                  length)]
        else:
            update_pieces = []
            # doesn't begin on an even piece boundary
            if start % self.piece_length != 0:
                end_b = pieces[1] * self.piece_length
                startfile = os.path.join(self.bufferdir, str(fileidx) + 'b')
                working_range_b = [(start, end_b, 0, startfile)]
                disabled_files.append((startfile, start, end_b))
                length = end_b - start
                self.sizes[startfile] = length
                offset = length
                piece = pieces.pop(0)
                update_pieces.append((piece,
                                      start - (piece * self.piece_length),
                                      length))
            else:
                working_range_b = []
            if fileidx != len(self.files) - 1 and end % self.piece_length != 0:
                # doesn't end on an even piece boundary
                start_e = pieces[-1] * self.piece_length
                endfile = os.path.join(self.bufferdir, str(fileidx) + 'e')
                working_range_e = [(start_e, end, 0, endfile)]
                disabled_files.append((endfile, start_e, end))
                length = end - start_e
                self.sizes[endfile] = length
                piece = pieces.pop(-1)
                update_pieces.append((piece, 0, length))
            else:
                working_range_e = []
            if pieces:
                working_range_m = [(pieces[0] * self.piece_length,
                                    (pieces[-1] + 1) * self.piece_length,
                                    offset, fname)]
            else:
                working_range_m = []
            working_range = working_range_b + working_range_m + working_range_e

        if DEBUG:
            print(working_range)
            print(update_pieces)
        r = (tuple(working_range), tuple(update_pieces), tuple(disabled_files))
        self.disabled_ranges[fileidx] = r
        return r

    def set_bufferdir(self, directory):
        self.bufferdir = directory

    def enable_file(self, fileidx):
        if not self.disabled[fileidx]:
            return
        self.disabled[fileidx] = False
        r = self.file_ranges[fileidx]
        if not r:
            return
        fname = r[3]
        if not os.path.exists(fname):
            with open(fname, 'wb+') as fileh:
                fileh.flush()
        if fname not in self.tops:
            self.tops[fname] = os.path.getsize(fname)
        if fname not in self.mtimes:
            self.mtimes[fname] = os.path.getmtime(fname)
        self.working_ranges[fileidx] = [r]

    def disable_file(self, fileidx):
        if self.disabled[fileidx]:
            return
        self.disabled[fileidx] = True
        r = self._get_disabled_ranges(fileidx)
        if not r:
            return
        for fname, _, _ in r[2]:
            if not os.path.isdir(self.bufferdir):
                os.makedirs(self.bufferdir)
            if not os.path.exists(fname):
                with open(fname, 'wb+') as fileh:
                    fileh.flush()
            if fname not in self.tops:
                self.tops[fname] = os.path.getsize(fname)
            if fname not in self.mtimes:
                self.mtimes[fname] = os.path.getmtime(fname)
        self.working_ranges[fileidx] = r[0]

    reset_file_status = _reset_ranges

    def get_piece_update_list(self, fileidx):
        return self._get_disabled_ranges(fileidx)[1]

    def delete_file(self, fileidx):
        try:
            os.remove(self.files[fileidx][0])
        except OSError:
            pass

    '''
    Pickled data format:

    d['files'] = [ file #, size, mtime {, file #, size, mtime...} ]
                    file # in torrent, and the size and last modification
                    time for those files.  Missing files are either empty
                    or disabled.
    d['partial files'] = [ name, size, mtime... ]
                    Names, sizes and last modification times of files
                    containing partial piece data.  Filenames go by the
                    following convention:
                    {file #, 0-based}{nothing, "b" or "e"}
                    eg: "0e" "3" "4b" "4e"
                    Where "b" specifies the partial data for the first piece in
                    the file, "e" the last piece, and no letter signifying that
                    the file is disabled but is smaller than one piece, and
                    that all the data is cached inside so adjacent files may be
                    verified.
    '''
    def pickle(self):
        files = []
        pfiles = []
        for i, (fname, size) in enumerate(self.files):
            if not size:
                continue
            if not self.disabled[i]:
                files.extend([i, os.path.getsize(fname),
                              int(os.path.getmtime(fname))])
            else:
                for fname, _, _ in self._get_disabled_ranges(i)[2]:
                    pfiles.extend([os.path.basename(fname),
                                   os.path.getsize(fname),
                                   int(os.path.getmtime(fname))])
        return {'files': files, 'partial files': pfiles}

    def unpickle(self, data):
        # assume all previously-disabled files have already been disabled
        try:
            # Extract file and pfile sequences
            files = {}
            pfiles = {}

            filelist = data['files']
            for i in range(0, len(filelist), 3):
                files[filelist[i]] = (filelist[i + 1], filelist[i + 2])

            pfilelist = data.get('partial files', [])
            for i in range(0, len(pfilelist), 3):
                pfiles[pfilelist[i]] = (pfilelist[i + 1], pfilelist[i + 2])

            # Build set of already potentially existing pieces, excluding
            # disabled files
            valid_pieces = set()
            for frange, disabled in zip(self.file_ranges, self.disabled):
                if disabled or not frange:
                    continue
                start, end, _, fname = frange
                if DEBUG:
                    print('adding ' + fname)
                valid_pieces.update(
                    range(int(start / self.piece_length),
                          int((end - 1) / self.piece_length) + 1))

            if DEBUG:
                print(list(valid_pieces))

            def changed(old, size, mtime):
                oldsize, oldmtime = old
                if size != oldsize:
                    return True
                return not oldmtime - 1 < mtime < oldmtime + 1

            for i, (fname, size) in enumerate(self.files):
                if not size:
                    continue

                # Remove pieces from disabled files unless also containing
                # part of unchanged partial files
                if self.disabled[i]:
                    for fname, start, end in self._get_disabled_ranges(i)[2]:
                        f1 = os.path.basename(fname)
                        if f1 not in pfiles or \
                                changed(pfiles[f1], os.path.getsize(fname),
                                        os.path.getmtime(fname)):
                            if DEBUG:
                                print('removing ' + fname)
                            valid_pieces.difference_update(
                                range(int(start / self.piece_length),
                                      int((end - 1) / self.piece_length) + 1))
                    continue

                # Remove pieces unless part of unchanged completed files
                if i not in files or changed(files[i], os.path.getsize(fname),
                                             os.path.getmtime(fname)):
                    start, end, _, fname = self.file_ranges[i]
                    if DEBUG:
                        print('removing ' + fname)
                    valid_pieces.difference_update(
                        range(int(start / self.piece_length),
                              int((end - 1) / self.piece_length) + 1))
        except Exception:
            if DEBUG:
                traceback.print_exc()
            return []

        if DEBUG:
            print(list(valid_pieces))
        return valid_pieces
