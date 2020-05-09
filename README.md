# beets-inotify

Import singles to beets as soon as they are dropped in a folder.

The script includes a customizable function that may allow you to set meta-data
or custom attributes depending on the sub-folder in which the file has been dropped.

**This script tells its whole life in `./beets_inotify.log` and anywhere else**.

TODO link to examples


## Examples wanted !

I'd be happy to include your own variations of this script in the `examples`
folder, feel free to post them in Issues or Pull Requests.

## Get started

You'll need Python3 on a Linux box, and obviously an existing [Beets](http://beets.io/) library.

```
git clone git@github.com:martinkirch/beets-inotify.git
cd beets-inotify/
python3 -m venv beets_inotify
pip install -e .
```

Then, adapt `beets_inotify.py` to your needs and machine.
You need to at least to change `BEETS_PATH`, `BEETS_DIRECTORY` and `DROPBOX`.
If you'd like to set some tags depending of which sub-folder the file is dropped in,
modify the `new_item` function.

You can test by calling `./beets_inotify.py` on the command line and drop a few files to add.
Hit Ctrl+C to close the script.
Both good news and errors are always written to `./beets_inotify.log`.

For a longer-term installation, TODO
