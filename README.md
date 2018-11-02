BitTornado
==========

BitTornado is a fork of the original Python BitTorrent distribution, made by
John Hoffman to add some experimental features, most (if not all) of which are
now standard in other clients and trackers. The last official release was made
in 2006, and thus many newer features are missing, but BitTornado is also an
accessible Python library, and has several simple tools for editing torrent
files.

After several years of intermittent modifications, cleanups, modernization, and
porting to Python 3.4, I have begun assigning version numbers. I have done my
best to ensure that tagged versions and python-labelled branches (see below)
work at least as well as they did in version 0.3.18. Since 0.4.0, the library
components have been substantially reorganized, so expect dependent
applications to break on upgrade.

Notice of unmaintained status
=============================

I appreciate that people have made an effort to use and report bugs in this
package, which I believe is the most approachable implementation of many aspects
of the protocol and file format. However, the BitTorrent ecosystem has moved on,
and I don't have time to keep up with it.

At the time of this writing, in November 2018, it's been over two years since I
was able to do more than briefly respond to an issue or review a small PR. This
notice is less a decision and more an acknowledgment that I cannot devote any
effort to maintaining this repository.

There are various known [issues](https://github.com/effigies/BitTornado/issues)
that are unresolved and will remain so unless somebody takes up maintenance.

Thanks to all who contributed time and effort on this.

Branches/Tags
=============

Further development will be done in Python 3, although patches to the other
branches may be accepted.

* [v0.3.18](https://github.com/effigies/BitTornado/tree/v0.3.18): Original
    import
* [legacy](https://github.com/effigies/BitTornado/tree/legacy): Library
    structure unchanged, some fixes/cleanups made
* [python2.6](https://github.com/effigies/BitTornado/tree/python2.6): Python
    2.6 compatibility maintained (legacy)
* [v0.4.0](https://github.com/effigies/BitTornado/tree/v0.4.0): Major
    restructuring, breaking depending applications
* [python2.7](https://github.com/effigies/BitTornado/tree/python2.7): Python
    2.7 compatibility maintained (library structure updated)
* [master](https://github.com/effigies/BitTornado/tree/master): Python 3

Using BitTornado Applications
=============================

## Download or seed a file

A single file can be downloaded with any of the following commands:

    btdownloadheadless.py myfile.torrent
    btdownloadcurses.py myfile.torrent

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

