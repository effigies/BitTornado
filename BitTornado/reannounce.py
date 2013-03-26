from Info import MetaInfo


def reannounce(fname, announce, announce_list=None, verbose=False):
    """Replace announce and announce-list in info file"""
    metainfo = MetaInfo.read(fname)

    if verbose:
        print 'old announce for %s: %s' % (fname, metainfo['announce'])

    metainfo['announce'] = announce

    if 'announce-list' in metainfo:
        if verbose:
            print 'old announce-list for {}: {}'.format(
                fname, '|'.join(','.join(tier)
                                for tier in metainfo['announce-list']))
        if announce_list is not None:
            metainfo['announce-list'] = announce_list
        else:
            metainfo.pop('announce-list', None)

    metainfo.write(fname)
