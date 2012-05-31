# Written by Bram Cohen
# multitracker extensions by John Hoffman
# see LICENSE.txt for license information

from os.path import getsize, split, join, abspath, isdir
from os import listdir
from sha import sha
from copy import copy
from string import strip
from BitTornado.bencode import bencode
from btformats import check_info
from threading import Event
from time import time
from traceback import print_exc
from BTTree import Info, BTTree, uniconvertl, uniconvert

defaults = [
    ('announce_list', '',
        'a list of announce URLs - explained below'),
    ('httpseeds', '',
        'a list of http seed URLs - explained below'),
    ('piece_size_pow2', 0,
        "which power of 2 to set the piece size to (0 = automatic)"),
    ('comment', '',
        "optional human-readable comment to put in .torrent"),
    ('filesystem_encoding', '',
        "optional specification for filesystem encoding " +
        "(set automatically in recent Python versions)"),
    ('target', '',
        "optional target file for the torrent")
    ]

default_piece_len_exp = 18

ignore = ['core', 'CVS']

def print_announcelist_details():
    print """    announce_list = optional list of redundant/backup tracker URLs, in the format:
           url[,url...][|url[,url...]...]
                where URLs separated by commas are all tried first
                before the next group of URLs separated by the pipe is checked.
                If none is given, it is assumed you don't want one in the metafile.
                If announce_list is given, clients which support it
                will ignore the <announce> value.
           Examples:
                http://tracker1.com|http://tracker2.com|http://tracker3.com
                     (tries trackers 1-3 in order)
                http://tracker1.com,http://tracker2.com,http://tracker3.com
                     (tries trackers 1-3 in a randomly selected order)
                http://tracker1.com|http://backup1.com,http://backup2.com
                     (tries tracker 1 first, then tries between the 2 backups randomly)

    httpseeds = optional list of http-seed URLs, in the format:
            url[|url...]"""
    
def make_meta_file(loc, url, params = {}, flag = Event(),
                   progress = lambda x: None, progress_percent = 1):
    tree = BTTree(loc, [])

    # Extract target from parameters
    if 'target' not in params or params['target'] == '':
        a, b = split(loc)
        if b == '':
            target = a + '.torrent'
        else:
            target = join(a, b + '.torrent')
        params['target'] = target

    info = tree.makeInfo(**params)
    info.write(tracker = url, **params)

def makeinfo(file, piece_length, encoding, flag, progress, progress_percent=1):
    file = abspath(file)
    if isdir(file):
        subs = subfiles(file)
        subs.sort()
        pieces = []
        sh = sha()
        done = 0L
        fs = []
        totalsize = 0.0
        totalhashed = 0L
        for p, f in subs:
            totalsize += getsize(f)

        for p, f in subs:
            pos = 0L
            size = getsize(f)
            fs.append({'length': size, 'path': uniconvertl(p, encoding)})
            h = open(f, 'rb')
            while pos < size:
                a = min(size - pos, piece_length - done)
                sh.update(h.read(a))
                if flag.isSet():
                    return
                done += a
                pos += a
                totalhashed += a
                
                if done == piece_length:
                    pieces.append(sh.digest())
                    done = 0
                    sh = sha()
                if progress_percent:
                    progress(totalhashed / totalsize)
                else:
                    progress(a)
            h.close()
        if done > 0:
            pieces.append(sh.digest())
        return {'pieces': ''.join(pieces),
            'piece length': piece_length, 'files': fs, 
            'name': uniconvert(split(file)[1], encoding) }
    else:
        size = getsize(file)
        pieces = []
        p = 0L
        h = open(file, 'rb')
        while p < size:
            x = h.read(min(piece_length, size - p))
            if flag.isSet():
                return
            pieces.append(sha(x).digest())
            p += piece_length
            if p > size:
                p = size
            if progress_percent:
                progress(float(p) / size)
            else:
                progress(min(piece_length, size - p))
        h.close()
        return {'pieces': ''.join(pieces), 
            'piece length': piece_length, 'length': size, 
            'name': uniconvert(split(file)[1], encoding) }

def calcsize(file):
    if not isdir(file):
        return getsize(file)
    total = 0L
    for s in subfiles(abspath(file)):
        total += getsize(s[1])
    return total

def subfiles(d):
    r = []
    stack = [([], d)]
    while len(stack) > 0:
        p, n = stack.pop()
        if isdir(n):
            for s in listdir(n):
                if s not in ignore and s[:1] != '.':
                    stack.append((copy(p) + [s], join(n, s)))
        else:
            r.append((p, n))
    return r


def completedir(dir, url, params = {}, flag = Event(),
                vc = lambda x: None, fc = lambda x: None):
    files = listdir(dir)
    files.sort()
    ext = '.torrent'
    if params.has_key('target'):
        target = params['target']
    else:
        target = ''

    togen = []
    for f in files:
        if f[-len(ext):] != ext and (f + ext) not in files:
            togen.append(join(dir, f))
        
    total = 0
    for i in togen:
        total += calcsize(i)

    subtotal = [0]
    def callback(x, subtotal = subtotal, total = total, vc = vc):
        subtotal[0] += x
        vc(float(subtotal[0]) / total)
    for i in togen:
        fc(i)
        try:
            t = split(i)[-1]
            if t not in ignore and t[0] != '.':
                if target != '':
                    params['target'] = join(target,t+ext)
                make_meta_file(i, url, params, flag, progress = callback, progress_percent = 0)
        except ValueError:
            print_exc()
