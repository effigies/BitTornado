from bencode import bencode, bdecode

def reannounce(fname, announce, announce_list = None, verbose = False):
    with open(fname, 'rb') as metainfo_file:
        metainfo = bdecode(metainfo_file.read())

    if verbose:
        print 'old announce for %s: %s' % (fname, metainfo['announce'])
    
    metainfo['announce'] = announce
    
    if 'announce-list' in metainfo:
        if verbose:
            print 'old announce-list for %s: %s' % (fname,
                '|'.join(','.join(tier) for tier in metainfo['announce-list']))
        if announce_list is not None:
            metainfo['announce-list'] = announce_list
        else:
            try:
                del metainfo['announce-list']
            except:
                pass
            
    with open(fname, 'wb') as metainfo_file:
        metainfo_file.write(bencode(metainfo))
