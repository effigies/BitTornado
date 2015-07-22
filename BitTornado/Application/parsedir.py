"""Tools for reading a directory of torrent files
"""

import os
import hashlib
from BitTornado.Meta.bencode import bencode
from BitTornado.Meta.Info import check_info, MetaInfo


def _errfunc(msg):
    print(":: ", msg)


def parsedir(directory, parsed, files, blocked, exts=('.torrent',),
             return_metainfo=False, errfunc=_errfunc):
    """Parse bencoded files in a directory structure.

    Parameters
        str     - path of directory
        {str: {str: *}}
                - dictionary, keyed by sha hash of encoded info dict, of
                    torrent file metadata
        {str: [(float, int), str]}
                - dictionary, keyed by file path, of (mtime, length) pairs and
                    a hash value (corresponds to keys of parsed)
        {str}   - set of previously blocked file paths
        (str,)  - tuple of valid file extensions
        bool    - parsed metadata to include full torrent data
        f(str)  - function to process error messages

    Returns
        {str: {str: *}}
                - dictionary, keyed by sha hash of encoded info dict, of
                    torrent file metadata
        {str: [(float, int), str]}
                - dictionary, keyed by file path, of (mtime, length) pairs and
                    parsed hash value (0 if unable to parse)
        {str}   - set of file paths of unparseable or duplicate torrents
        {str: {str: *}}
                - dictionary, keyed by sha hash of encoded info dict, of
                    metadata of torrent files added during directory parse
        {str: {str: *}}
                - dictionary, keyed by sha hash of encoded info dict, of
                    metadata of torrent files removed during directory parse
    """
    new_files, torrent_type = get_files(directory, exts)

    # removed_files = (files \ new_files) U changed_files
    removed_files = {path: files[path] for path in files
                     if path not in new_files
                     or files[path][0] != new_files[path][0]}

    # Missing files are removed
    removed = {filehash: parsed[filehash]
               for _, filehash in removed_files.values()}

    # unchanged_files = files \ removed_files
    unchanged_files = {path: files[path] for path in files
                       if path not in removed_files}

    # Parse new files and those whose mtime or length has change
    # Block those that are unmodified but unparsed (indicates error)
    new_blocked = set()
    to_parse = []
    for path in new_files:
        if path not in unchanged_files:
            to_parse.append(path)
        elif unchanged_files[path][1] == 0:
            new_blocked.add(path)

    new_files.update(unchanged_files)

    # Keep old parsed files
    new_parsed = {infohash: parsed[infohash]
                  for _, infohash in unchanged_files.values()}

    # Attempt to parse new files
    added = {}
    for path in sorted(to_parse):
        try:
            torrentinfo, infohash = parse_torrent(path, return_metainfo)
            torrentinfo['type'] = torrent_type[path]
            if infohash not in new_parsed:
                new_parsed[infohash] = torrentinfo
                added[infohash] = torrentinfo
                new_files[path][1] = infohash
            else:
                # Don't warn if we've blocked before
                if path not in blocked:
                    errfunc('**warning** {} is a duplicate torrent for {}'
                            ''.format(path, new_parsed[infohash]['path']))
                new_blocked.add(path)
        except (IOError, ValueError):
            errfunc('**warning** {} has errors'.format(path))
            new_blocked.add(path)

    return (new_parsed, new_files, new_blocked, added, removed)


def get_files(directory, exts=('.torrent',)):
    """Get the shallowest set of files with valid extensions in a directory
    structure.

    If no valid files are found in a directory, search all subdirectories. If
    a valid file is found in a directory, no subdirectories will be searched.

    Parameters
        str     - path of directory
        (str,)  - tuple of valid file extensions

    Returns
        {str: [(float, int), 0]}
                - dictionary, keyed by file path, of (mtime, length) pairs and
                    an uninitialized hash value
        {str: str}
                - dictionary, keyed by file path, of file extension
    """
    files = {}
    file_type = {}

    # Ignore '.' files and directories
    subs = (candidate for candidate in os.listdir(directory)
            if candidate[0] != '.')

    # Find valid files
    subdirs = []
    for sub in subs:
        loc = os.path.join(directory, sub)
        if os.path.isdir(loc):
            subdirs.append(loc)
            continue

        extmatches = [ext[1:] for ext in exts if sub.endswith(ext)]
        if extmatches:
            files[loc] = [(os.path.getmtime(loc), os.path.getsize(loc)), 0]
            file_type[loc] = extmatches[0]

    # Recurse if no valid files found
    if not files and subdirs:
        for subdir in subdirs:
            subfiles, subfile_type = get_files(subdir, exts)
            files.update(subfiles)
            file_type.update(subfile_type)

    return files, file_type


def parse_torrent(path, return_metainfo=False):
    """Load and derive metadata from torrent file

    Parameters
        str     - path of file to parse
        bool    - parsed metadata to include full torrent data

    Returns
        {str: *}
                - torrent file metadata
        str     - sha hash of encoded info dict
    """
    fname = os.path.basename(path)

    data = MetaInfo.read(path)

    # Validate and hash info dict
    info = data['info']
    check_info(info)
    infohash = hashlib.sha1(bencode(info)).digest()

    single = 'length' in info

    torrentinfo = {
        'path':     path,
        'file':     fname,
        'name':     info.get('name', fname),
        'numfiles': 1 if single else len(info['files']),
        'length':   info['length'] if single else sum(
            li['length'] for li in info['files'] if 'length' in li)
    }

    for key in ('failure reason', 'warning message', 'announce-list'):
        if key in data:
            torrentinfo[key] = data[key]

    if return_metainfo:
        torrentinfo['metainfo'] = data

    return torrentinfo, infohash
