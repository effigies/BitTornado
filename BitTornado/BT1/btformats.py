"""Functions to verify assumptions about BitTorrent data structures"""
import re

REG = re.compile(r'^[^/\\.~][^/\\]*$')
INTS = (long, int)


def check_types(obj, types, errmsg='', pred=lambda x: False):
    """Raise value error if obj does not match types or triggers predicate"""
    if type(obj) not in types or pred(obj):
        raise ValueError(errmsg)


def check_type(obj, typ, errmsg='', pred=lambda x: False):
    """Raise value error if obj does not match type or triggers predicate"""
    if type(obj) is not typ or pred(obj):
        raise ValueError(errmsg)


def check_info(info):
    """Validate torrent metainfo dictionary"""
    berr = 'bad metainfo - '
    check_type(info, dict, berr + 'not a dictionary')

    check_type(info.get('pieces'), str, berr + 'bad pieces key',
               lambda x: x % 20 != 0)

    check_types(info.get('piece length'), INTS, berr + 'illegal piece length',
                lambda x: x <= 0)

    name = info.get('name')
    check_type(name, str, berr + 'bad name')
    if not REG.match(name):
        raise ValueError('name %s disallowed for security reasons' % name)

    if ('files' in info) == ('length' in info):
        raise ValueError('single/multiple file mix')

    if 'length' in info:
        check_types(info['length'], INTS, berr + 'bad length',
                    lambda x: x < 0)
    else:
        files = info.get('files')
        check_type(files, list)

        paths = {}
        for finfo in files:
            check_type(finfo, dict, berr + 'bad file value')

            check_types(finfo.get('length'), INTS, berr + 'bad length',
                        lambda x: x < 0)

            path = finfo.get('path')
            check_type(path, list, berr + 'bad path', lambda x: x == [])

            for directory in path:
                check_type(directory, str, berr + 'bad path dir')
                if not REG.match(directory):
                    raise ValueError('path {} disallowed for security reasons'
                                     ''.format(directory))

            tpath = tuple(path)
            if tpath in paths:
                raise ValueError('bad metainfo - duplicate path')
            paths[tpath] = True


def check_message(message):
    """Validate a dictionary with an announce string and info dictionary"""
    check_type(message, dict)
    check_info(message.get('info'))
    check_type(message.get('announce'), str)


def check_peers(message):
    """Validate a dictionary with a list of peers"""
    check_type(message, dict)
    if 'failure reason' in message:
        check_type(message['failure reason'], str)
        return

    peers = message.get('peers')
    if type(peers) is list:
        for peer in peers:
            check_type(peer, dict)
            check_type(peer.get('ip'), str)
            check_types(peer.get('port'), INTS, pred=lambda x: x <= 0)
            if 'peer id' in peer:
                check_type(peer.get('peer id'), str,
                           pred=lambda x: len(x) != 20)

    elif type(peers) is not str or len(peers) % 6 != 0:
        raise ValueError

    check_types(message.get('interval', 1), INTS, pred=lambda x: x <= 0)
    check_types(message.get('min interval', 1), INTS, pred=lambda x: x <= 0)
    check_type(message.get('tracker id', ''), str)
    check_types(message.get('num peers', 0), INTS, pred=lambda x: x < 0)
    check_types(message.get('done peers', 0), INTS, pred=lambda x: x < 0)
    check_types(message.get('last', 0), INTS, pred=lambda x: x < 0)
