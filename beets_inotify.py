#!/usr/bin/env python
"""
This is watching a folder for singles to be imported to a Beets library.

You have to tune the constants below before starting.
"""

#### the first two should match what's in your Beets config :
# beet's "library"
BEETS_PATH = "/home/martin/beets/library.db"
# beets' "directory"
BEETS_DIRECTORY = "/home/martin/Musique/"

# main folder of our dropbox - keep it separated from BEETS_DIRECTORY
DROPBOX = "/home/martin/beets-dropbox/"


#### Maybe, apply your own path rules here :

def new_item(item, path):
    """
    Parameters:
        item: the beets Item that we're about to import
        path: its sub-folders path in our dropbox ; if the items has been dropped at the root, then it's empty.
    Returns:
        the item modified as you like, maybe according to path ; return None if you prefer to skip the file.
    """
    print (item)
    print (path)
    print (item.get_album())
    print("new_item done")
    return item



###############################################################################

from beets.library import Library, Item
from inotify.adapters import InotifyTree


def get_library():
    return Library(path=BEETS_PATH, directory=BEETS_DIRECTORY)

def main():
    # to ensure integrity we'll re-open the library for each item to be imported,
    # but before doing anything else let's check the lib exists
    _ = get_library()

    i = InotifyTree(DROPBOX)
    for event in i.event_gen():
        if event is None:
            continue
        event_type = event[1]
        folder = event[2]
        filename = event[3]
        if 'IN_ISDIR' in event_type:
            continue
        #print("event_type=%s, folder=%s, filename=%s" % (event_type, folder, filename))
        if 'IN_MOVED_TO' in event_type or 'IN_CLOSE_WRITE' in event_type:
            item = Item.from_path("%s/%s" % (folder, filename))
            dropbox_path = folder[len(DROPBOX):]
            item = new_item(item, dropbox_path)
            if item:
                pass # TODO import
                # get_library().add(item)
                print("should move to "+item.destination())
                # item.move()


# event_type=['IN_MOVED_TO'], folder=/home/martin/beets-dropbox/mix/148, filename=17 - La danse des gros.mp3
# event_type=['IN_CLOSE_WRITE'], folder=/home/martin/beets-dropbox/mix/148, filename=Breaking E - 8m4o - 136BPM.flac

if __name__ == '__main__':
    if DROPBOX[-1] == '/':
        DROPBOX = DROPBOX[:-1]
    main()
