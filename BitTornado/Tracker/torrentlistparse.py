from binascii import unhexlify


def parsetorrentlist(filename, parsed):
    """Parse a list of torrent hashes in the form of one hash per line in
    hex format"""
    base_error = '*** WARNING *** line in torrent list '
    new_parsed = {}
    added = {}
    with open(filename, 'r') as listfile:
        for line in listfile:
            l = line.strip()
            if len(l) != 40:
                print(base_error + 'incorrect length: ' + l)
                continue

            try:
                h = unhexlify(l)
                if h not in parsed:
                    added[h] = True
                new_parsed[h] = True
            except TypeError:
                print(base_error + 'has non-hex digits: ' + l)
    return (new_parsed, added)
