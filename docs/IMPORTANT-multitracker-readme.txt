                 MULTITRACKER EXTENSION INFORMATION
                 ==================================

The multitracker support given in this client is not officially
supported, and future support may be different.

                   THIS DOCUMENT IS VERY IMPORTANT.
              READ CAREFULLY OR YOUR CLIENTS WILL SUFFER.

-----------------------------------------------------------------------

This specification allows the client to connect to back-up trackers in
the event of the failure of a main tracker.  It can also function to
divide tracker traffic between multiple trackers.  Do *NOT* use this
feature unless your trackers can share peer data with each other.
Doing so will result in the peers forming separate groups, or "clouds",
between which they cannot share, and some groups may become unseeded or
may operate inefficiently.

The source package includes highly experimental peerable tracker code;
please see the contents of the multitracker folder for more
information.

As of this release, the utilities "btmakemetafile.py", "btreannounce.py"
and "btcompletedir.py" have been modified to be able to add a multiple
tracker list, "btshowmetainfo.py" has been modified to be able to show
the list, and a new utility "btmaketorrentgui.py" has been added, that is
able to manipulate the multiple tracker list.  "btcompletedirgui.py" has
been superceded by this new utility.  Also included is "btcopyannounce.py",
which can copy announce information from a "template" .torrent file.

The "announce list" is separate from the torrent file's standard
"announce" entry.  To be compatible with all clients, the torrent must
contain a standard announce entry.  Clients that support this
multitracker specification will ignore the standard announce and use
only the list if it is present.

To reannounce a torrent file to use multiple trackers, use the
following format:

"btreannounce.py http://maintrk.com:6969/announce --announce-list http://maintrk.com:6969/announce|http://bkup1.com:6969/announce|http://bkup2.com:6969/announce mytorrent.torrent"

Note that the main tracker is mentioned twice, both as the standard
announce and as the first element in the tracker list.  This is
important; do not forget it.

Also note that the URLs for the trackers are separated by the vertical
bar character ("|").  Again, UNLESS YOUR TRACKERS TRADE PEER
INFORMATION, DO NOT USE THE COMMAS.


-----------------------------------------------------------------------



btmakemetafile.py file trackerurl [params]

--announce-list <arg>
          a list of announce URLs - explained below (defaults to '')

--piece_size_pow2 <arg>
          which power of 2 to set the piece size to (defaults to 18)

--comment <arg>
          optional human-readable comment to put in .torrent (defaults
          to '')

--target <arg>
          optional target file for the torrent (defaults to '')




btreannounce.py <announce> [--announce-list <arg>] file1.torrent [file2.torrent...]

  Where:
    announce = tracker URL
           Example: http://www.tracker.com:6699/announce

    announce-list = optional list of redundant/backup tracker URLs, in
                    the format:
     url[,url...][|url[,url...]...]
          where URLs separated by commas are all tried first
          before the next group of URLs separated by the pipe is
          checked.
          If none is given, it is assumed you don't want one in
          the metafile.
          If announce-list is given, clients which support it
          will ignore the <announce> value.
           Examples:
          http://tracker1.com|http://tracker2.com|http://tracker3.com
               (tries trackers 1-3 in order)
          http://tracker1.com,http://tracker2.com,http://tracker3.com
               (tries trackers 1-3 in a randomly selected order)
          http://tracker1.com|http://backup1.com,http://backup2.com
               (tries tracker 1 first, then tries between the 2
               backups randomly)

