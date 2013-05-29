"""Generate metafile data for use in BitTorrent applications

These data structures are generalizations of the original BitTorrent and
BitTornado makemetafile.py behaviors.
"""

import os
from .Info import Info, MetaInfo


class BTTree(object):
    """BTTree - Recursive data structure that tracks the total size of a
    file or directory, which can then be used to create torrent files.

    BTTree attributes
        str      loc    Location of source file/directory
        str[]    path   Path
        BTTree[] subs   List of direct children (empty, if a file)
        int      size   Total size of subfiles (or self, if a file)
    """
    def __init__(self, loc, path):
        """
        Parameters
            str         loc     Location of source file/directory
            str[]       path    File path e.g. ['path','to','file.ext']
        """
        self.loc = os.path.abspath(loc)
        self.path = path
        self.subs = []

        # The only important bit of information at this stage is size
        if os.path.isfile(loc):
            self.size = os.path.getsize(loc)

        # We'll need to know the size of all subfiles
        elif os.path.isdir(loc):
            for sub in sorted(os.listdir(self.loc)):
                # Ignore .* (glob, not regex)
                if sub[0] == '.':
                    continue
                sloc = os.path.join(loc, sub)
                spath = self.path + [sub]
                try:
                    self.subs.append(BTTree(sloc, spath))

                # Notify, but ignore entries that are neither
                # files nor directories
                except IOError as problem:
                    print(problem)

            # For bittorrent's purposes, size(dir) = size(subs)
            self.size = sum(sub.size for sub in self.subs)
        else:
            raise IOError("Entry is neither file nor directory: " + loc)

    def initInfo(self, **params):
        """Determine name of file and instantiate an Info structure"""
        if self.path == []:
            name = os.path.basename(self.loc)
        else:
            name = self.path[0]

        return Info(name, self.size, **params)

    def makeInfo(self, **params):
        """Generate an Info data structure from a BTTree"""

        info = self.initInfo(**params)

        self.updateInfo(info)

        return info

    def addFileToInfos(self, infos):
        """Add file information and data hash to a sequence of Info
        structures"""
        with open(self.loc, 'rb') as fhandle:
            pos = 0
            piece_length = 0
            for info in infos:
                piece_length = max(piece_length, info.hasher.pieceLength)
                info.add_file_info(self.size, self.path)

            while pos < self.size:
                nbytes = min(piece_length, self.size - pos)
                buf = fhandle.read(nbytes)
                pos += nbytes
                for info in infos:
                    info.add_data(buf)

    def updateInfo(self, info):
        """Add a sub-BTTree to an Info structure

        Parameters
            Info    info   - Info structure to update
        """
        if not os.path.isdir(self.loc) and self.subs == []:
            self.addFileToInfos((info,))
        else:
            for sub in self.subs:
                sub.updateInfo(info)

    #pylint: disable=W0102
    def buildMetaTree(self, tracker, target, infos=[], **params):
        """Construct a directory structure such that, for every path in
        the source structure defined by the object, there is a .torrent
        file describing it.

        This is an inlining of makeInfo and updateInfo so that, when a
        subtree is complete, its .torrent file is written, preserving
        memory.

        Parameters
            str     tracker - URL of tracker
            str     target  - target directory
            Info[]  infos   - List of Info's to add current file to
        """
        info = self.initInfo(**params)

        # Since append updates the object, while + creates a new one
        infos += [info]

        # Add the file pointed to by this BTTree to all infos
        if self.subs == []:
            self.addFileToInfos(infos)

        # Recurse in this directory
        else:
            for sub in self.subs:
                sub.buildMetaTree(tracker, target, infos, **params)

        # Verify we can make our target .torrent file
        target_dir = os.path.dirname(target)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        metainfo = MetaInfo(announce=tracker, info=info, **params)
        metainfo.write(os.path.join(target, *self.path) + '.torrent')
