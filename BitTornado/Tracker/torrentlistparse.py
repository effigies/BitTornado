import string
from binascii import unhexlify
from ..Types import DictSet, Infohash

HEX = set(string.hexdigits)


class HashSet(DictSet):
    keytype = Infohash


def test_valid(line):
    """Test for 40 character hex strings

    Print error on failure"""
    base_error = '*** WARNING *** line in torrent list'
    if len(line) != 40:
        print(base_error, 'incorrect length:', line)
    elif any(char not in HEX for char in line):
        print(base_error, 'has non-hex digits:', line)
    else:
        return True


def parsetorrentlist(filename, parsed):
    """Parse a list of torrent hashes in the form of one hash per line in
    hex format

    Arguments:
        filename    str         File to be parsed
        parsed      {Infohash}  Set of known infohashes

    Returns:
        new_parsed  {Infohash}  Set of infohashes parsed
        added       {Infohash}  Previously unknown infohashes
    """
    with open(filename, 'r') as listfile:
        new_parsed = HashSet(unhexlify(line.strip()) for line in listfile
                             if test_valid(line))
    return new_parsed, new_parsed - parsed
