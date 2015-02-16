#pylint: disable=W0102,C0103
import os
import threading
from traceback import print_exc
from BitTornado.Meta.BTTree import BTTree
from BitTornado.Meta.Info import MetaInfo

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

announcelist_details = \
    """announce_list = optional list of redundant/backup tracker URLs, in the
format:
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


def make_meta_file(loc, url, params=None, flag=None,
                   progress=lambda x: None, progress_percent=True):
    """Make a single .torrent file for a given location"""
    if params is None:
        params = {}
    if flag is None:
        flag = threading.Event()

    tree = BTTree(loc, [])

    # Extract target from parameters
    if 'target' not in params or params['target'] == '':
        fname, ext = os.path.split(loc)
        if ext == '':
            target = fname + '.torrent'
        else:
            target = os.path.join(fname, ext + '.torrent')
        params['target'] = target

    info = tree.makeInfo(flag=flag, progress=progress,
                         progress_percent=progress_percent, **params)

    if flag is not None and flag.isSet():
        return

    metainfo = MetaInfo(announce=url, info=info, **params)
    metainfo.write(params['target'])


def completedir(directory, url, params=None, flag=None,
                progress=lambda x: None, filestat=lambda x: None):
    """Make a .torrent file for each entry in a directory"""
    if params is None:
        params = {}
    if flag is None:
        flag = threading.Event()

    files = sorted(os.listdir(directory))
    ext = '.torrent'

    togen = [os.path.join(directory, fname) for fname in files
             if (fname + ext) not in files and not fname.endswith(ext)]

    trees = [BTTree(loc, []) for loc in togen]

    def subprog(update, subtotal=[0], total=sum(tree.size for tree in trees),
                progress=progress):
        """Aggregate progress callback
        Uses static subtotal to track across files"""
        subtotal[0] += update
        progress(float(subtotal[0]) / total)

    for fname in togen:
        filestat(fname)
        try:
            base = os.path.basename(fname)
            if base not in ignore and base[0] != '.':
                subparams = params.copy()
                if 'target' in params and params['target'] != '':
                    subparams['target'] = os.path.join(params['target'],
                                                       base + ext)
                make_meta_file(fname, url, subparams, flag,
                               progress=subprog, progress_percent=False)
        except ValueError:
            print_exc()
