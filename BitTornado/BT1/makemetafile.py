# Written by Bram Cohen
# multitracker extensions by John Hoffman
# refactoring by Chris Johnson
# see LICENSE.txt for license information

import os
import threading
from traceback import print_exc
from BitTornado.BTTree import Info, BTTree

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

ignore = ['core', 'CVS']

announcelist_details = """announce_list = optional list of redundant/backup tracker URLs, in the format:
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
    
def make_meta_file(loc, url, params = {}, flag = threading.Event(),
                   progress = lambda x: None, progress_percent = True):
    tree = BTTree(loc, [])

    # Extract target from parameters
    if 'target' not in params or params['target'] == '':
        a, b = os.path.split(loc)
        if b == '':
            target = a + '.torrent'
        else:
            target = os.path.join(a, b + '.torrent')
        params['target'] = target

    info = tree.makeInfo(   flag = flag,
                            progress = progress,
                            progress_percent = progress_percent,
                            **params)

    if flag is not None and flag.isSet():
        return

    info.write(tracker = url, **params)

def completedir(dir, url, params = {}, flag = threading.Event(),
                vc = lambda x: None, fc = lambda x: None):
    files = os.listdir(dir)
    files.sort()
    ext = '.torrent'
    target = params.get('target','')

    togen = []
    for f in files:
        if f[-len(ext):] != ext and (f + ext) not in files:
            togen.append(os.path.join(dir, f))

    trees = [BTTree(loc,[]) for loc in togen]
    total = sum(tree.size for tree in trees)
        
    subtotal = [0]
    def callback(x, subtotal = subtotal, total = total, vc = vc):
        subtotal[0] += x
        vc(float(subtotal[0]) / total)
    for i in togen:
        fc(i)
        try:
            t = os.path.split(i)[-1]
            if t not in ignore and t[0] != '.':
                subparams = params.copy()
                if target != '':
                    subparams['target'] = os.path.join(target,t+ext)
                make_meta_file(i, url, subparams, flag,
                    progress = callback, progress_percent = False)
        except ValueError:
            print_exc()
