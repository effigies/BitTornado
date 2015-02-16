BitTornado
==========

BitTornado is a fork of the original Python BitTorrent distribution, made by
John Hoffman to add some experimental features, most (if not all) of which are
now standard in other clients and trackers. The last official release was made
in 2006, and thus many newer features are missing, but BitTornado is also an
accessible Python library, and has several simple tools for editing torrent
files.

After several years of intermittent modifications, cleanups and modernization,
it seems like a good time to give this code an actual version number. All
applications have been tested and work as well as they did in version 0.3.18.
The library components have been substantially reorganized, so this is highly
likely to break dependent applications.

Using BitTornado Applications
=============================

## Download or seed a file

A single file can be downloaded with any of the following commands:

    btdownloadheadless.py myfile.torrent
    btdownloadcurses.py myfile.torrent
    btdownloadgui.py myfile.torrent

A directory of files can be downloaded with any of the following commands:

    btlaunchmany.py mydir
    btlaunchmanycurses.py mydir

Attempting to download an already downloaded file will seed it.

## Tracker
First, you need a tracker. If you're on a dynamic IP or otherwise 
unreliable connection, you should find someone else's tracker and 
use that. Otherwise, follow the rest of this step.

Trackers refer downloaders to each other. The load on the tracker 
is very small, so you only need one for all your files.

To run a tracker, execute the command bttrack.py Here is an example -

    bttrack.py --port 6969 --dfile dstate

`--dfile` is where persistent information is kept on the tracker across 
invocations. It makes everything start working again immediately if 
you restart the tracker. A new one will be created if it doesn't exist 
already.

The tracker must be on a net-addressible box, and you must know the 
ip number or dns name of it.

The tracker outputs web logs to standard out. You can get information 
about the files it's currently serving by getting its index page. 


## Creating torrent files

    btmakemetafile.py http://my.tracker:6969/announce myfile.ext

This will generate a file called `myfile.ext.torrent`

Make sure to include the port number in the tracker url if it isn't 80.

This command may take a while to scan over the whole file hashing it.

The `/announce` path is special and hard-coded into the tracker. 
Make sure to give the domain or ip your tracker is on instead of 
my.tracker.

You can use either a dns name or an IP address in the tracker url.

### Creating many torrent files

    btcompletedir.py http://my.tracker:6969/announce mydir

This will generate a torrent file for each file in `mydir`.

### GUI interface

`btmaketorrentgui.py` and `bt-t-make.py` provide GUI interfaces for
creating single torrent files or directories of files.

## Editing torrent files

To view metadata encoded in the torrent file:

    btshowmetainfo.py myfile.torrent

To set the announce tracker of a torrent file:

    btreannounce.py http://mytracker.com:6969/announce myfile.torrent

To copy the announce information from one file to another:

    btcopyannounce.py source.torrent destination.torrent

To set the default download name:

    btrename.py myfile.torrent targetFileName.ext

To set HTTP seeds:

    btsethttpseeds http://example.net/myfile myfile.torrent

To remove HTTP seeds:

    btsethttpseeds 0 myfile.torrent

