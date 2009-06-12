#!/usr/bin/env python

# Written by Bram Cohen
# see LICENSE.txt for license information

import sys
assert sys.version >= '2', "Install Python 2.0 or greater"
from distutils.core import setup, Extension
import BitTornado

setup(
    name = "BitTornado",
    version = BitTornado.version,
    author = "Bram Cohen, John Hoffman, Uoti Arpala et. al.",
    author_email = "<theshadow@degreez.net>",
    url = "http://www.bittornado.com",
    license = "MIT",
    
    packages = ["BitTornado","BitTornado.BT1"],

    scripts = ["btdownloadgui.py", "btdownloadheadless.py", 
        "bttrack.py", "btmakemetafile.py", "btlaunchmany.py", "btcompletedir.py",
        "btdownloadcurses.py", "btcompletedirgui.py", "btlaunchmanycurses.py", 
        "btmakemetafile.py", "btreannounce.py", "btrename.py", "btshowmetainfo.py",
        'btmaketorrentgui.py', 'btcopyannounce.py', 'btsethttpseeds.py',
        'bt-t-make.py',
        ]
    )
