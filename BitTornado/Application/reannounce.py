from BitTornado.Meta.Info import MetaInfo


def reannounce(fname, announce, announce_list=None, verbose=False):
    """Replace announce and announce-list in info file"""
    metainfo = MetaInfo.read(fname)

    if verbose:
        # Accept torrents with no announce
        if 'announce' in metainfo:
            print('old announce for {}: {}'.format(fname,
                                                   metainfo['announce']))
        else:
            print('No announce found.')

    metainfo['announce'] = announce

    if 'announce-list' in metainfo:
        if verbose:
            print('old announce-list for {}: {}'.format(
                fname, '|'.join(','.join(tier)
                                for tier in metainfo['announce-list'])))
        if announce_list is not None:
            metainfo['announce-list'] = announce_list
        else:
            metainfo.pop('announce-list', None)

    metainfo.write(fname)
