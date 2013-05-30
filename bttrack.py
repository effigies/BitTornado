#!/usr/bin/env python3

# Written by Bram Cohen
# see LICENSE.txt for license information

PROFILE = 0

import sys
from BitTornado.Tracker.track import track

if __name__ == '__main__':
    if PROFILE:
        import profile
        import pstats
        from time import strftime
        p = profile.Profile()
        p.runcall(track, sys.argv[1:])
        log_fname = 'profile_data.' + strftime('%y%m%d%H%M%S') + '.txt'
        with open(log_fname, 'a') as log:
            normalstdout, sys.stdout = sys.stdout, log
            pstats.Stats(p).strip_dirs().sort_stats('time').print_stats()
            sys.stdout = normalstdout
    else:
        track(sys.argv[1:])
