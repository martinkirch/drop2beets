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
        A dict of custom attributes (according to path, maybe) ; return None if you don't want to import the file right now.
    """
    return {}



###############################################################################
import logging

from beets import config
from beets.ui.commands import import_files
from beets.plugins import load_plugins
from beets.library import Library
from inotify.adapters import InotifyTree

_logger = logging.getLogger("drop2beets")
_logger.setLevel(logging.INFO)


def get_library():
    return Library(path=BEETS_PATH, directory=BEETS_DIRECTORY)


def main():
    logging.basicConfig(
        filename=__file__.replace(".py", ".log"),
        level=logging.WARNING,
        format="%(asctime)s [%(filename)s:%(lineno)s] %(levelname)s %(message)s"
    )

    # to ensure integrity we'll re-open the library for each item to be imported,
    # but before doing anything else let's check the lib exists
    _ = get_library()
    logging.getLogger('beets').addHandler(logging.getLogger().handlers[0])

    load_plugins(names=['drop2beets']) # wild plugging of our plug-in !

    config['drop2beets']['dropbox_path'] = DROPBOX
    config['drop2beets']['custom_function'] = new_item

    _logger.info("Beets library found")
    _logger.info("Starting to monitor %s, put some files inside !", DROPBOX)

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
            _logger.info("Processing %s", filename)
            full_path = "%s/%s" % (folder, filename)
            import_files(get_library(), [full_path], None)


if __name__ == '__main__':
    if DROPBOX[-1] == '/':
        DROPBOX = DROPBOX[:-1]
    main()
