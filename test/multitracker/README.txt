           USING THE TRACKER FOR MULTITRACKER OPERATIONS
           =============================================

The tracker in this package has been enhanced so that it can operate as
part of a cluster of trackers.  This directory includes some examples
that may help you set up such a cluster for your own use.

(This document assumes you are familiar with setting up a standalone
python tracker.  If you do not, you really need to find out how before
trying this.)


MULTITRACKER OPERATION
----------------------
The following option has been added to the tracker:

--multitracker_enabled <arg>
          whether to enable multitracker operation (defaults to 0)

Enabling this is step 1 for operating with multiple trackers.  Step 2
is to create (or reannounce) the .torrent files to include all the
trackers involved.  (For this use, you would separate the trackers with
commas; for instance, if you had 3 peered trackers, you could do
"btreannounce.py http://tracker1 --announce_list tracker1,tracker2,tracker3 file.torrent".
("tracker1" etc. are the full URLs for those trackers' announces.)  You
would then place these torrents in the tracker's allowed_dir.

When the tracker parses the allowed_dir, it will also read the
announce-lists from the .torrent files and begin polling those trackers
for their peer data.  The trackers are polled much the way a client
would poll them, except that they are polled more frequently but
requesting fewer users with each connection.  The data collected is
then mixed in with the peer data returned by the tracker to its
clients.

This operation does take extra bandwidth.  Each additional tracker in
the cluster, and each additional torrent being tracked will increase
the amount of bandwidth consumed.  For a 4-tracker cluster tracking 10
torrents together, the extra bandwidth consumed will be equivalent to
up to 60 additional clients connected to each tracker.  (This number
should not, however, increase depending on the number of peers per
tracker; at least, not past a certain point.)

PLEASE NOTE:  When running a tracker enabled for multitracker
operations, one needs to be careful about the data in the .torrent
files placed in that tracker's allowed_dir.  Since that data tells the
tracker to establish outgoing connections based on the contents of
those .torrents, the potential for abuse is high.  It is therefore
recommended that any .torrent added to the tracker's allowed_dir have
its announce-list either screened or automatically replaced.  (The
included utility "btcopyannounce.py" is useful for this purpose, in
that one can set up a "template" .torrent file and copy that data over
every incoming .torrent file.


DATA AGGREGATION
----------------
It would probably be sufficient to simply collect the data from each
tracker and add them together.  However, for anyone who wishes to keep
more accurate records, or obtain more specific log information, the
following options have been added to the tracker:

--aggregator <arg>
          whether to act as a data aggregator rather than a tracker. If
          enabled, may be 1, or <password>; if password is set, then an
          incoming password is required for access (defaults to '0')

--aggregate_forward <arg>
          format: <url>[,<password>] - if set, forwards all non-
          multitracker to this url with this optional password
          (defaults to '')

The first option changes the tracker's operation from a tracker to a
"data aggregator".  When it receives an announce, it adds the data to
its internal statistics, but then returns nothing.

The second option is to be used on the members of the tracker cluster,
and directs them to send a copy of each query received to a tracker
designated as a data aggregator.

The result is that the aggregator receives all the statistical
information captured by each tracker, including the peer IDs.  It is
able to sort this data by peer ID, developing an accurate picture of
the torrent even if a peer connects to more than one tracker.

Please note operating like this DOES use up quite a bit of bandwidth;
the upstream bandwidth use of each tracker will increase by 10-15%.
Alternatives are being looked into.  If you feel you cannot waste this
much bandwidth, the presence of an aggregator is optional.


EXAMPLES
--------
In this directory are some examples to show how a tracker cluster might
be set up.  To try them, copy the files and "allowed" directory to the
root BitTorrent directory.

"tracker0.bat" runs one tracker as a data aggregator on localhost, port
80.  (While it is named as an MS-DOS batch file, it can easily be
modified to work as a shell script.)  "tracker1.bat", "tracker2.bat",
and "tracker3.bat" will each run a tracker on ports 81, 82 and 83
respectively, configured to use the common directory "allowed" to read
multitracker data from.

The common allowed_dir directory also contains the metadata file
"blah.torrent", which has been set up to expect co-equivalent trackers
on localhost ports 81, 82 and 83.  You can run it multiple times from
the local computer and see from the tracker logs that the client will
connect randomly to the trackers; but they are able to see each other
(at worst, after a short delay), and that http://localhost will show
all the clients you run in its statistics.


TIPS 'N TRICKS
--------------
* When you start distributing a torrent, expecting heavy load, set it
  up normally, adding all the trackers in the cluster to the torrent
  file and letting it distribute itself across the cluster.  Then, when
  it gets old and the load tails off, remove the .torrent file from
  some or most of the trackers' allowed_dirs.  The clients will
  automatically skip off the trackers that have removed it, and attach
  to the ones that still have it.  Tracker-to-tracker bandwidth for
  these torrents will automatically discontinue from trackers that no
  longer support it.  As a result, you can save bandwidth, and save T2T
  for when you really need it.

* You can also set up the trackers under a round-robin DNS, though you
  will need to change the announce-list in the torrents in the
  allowed_dirs to reflect the actual IPs.  If you do this, even an old
  client that doesn't support the multitracker specification can search
  to multiple trackers.  The statistics on each tracker will be
  especially inaccurate, but if you are using an aggregator, its stats
  won't be affected.