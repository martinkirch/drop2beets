# drop2beets

Import singles to beets as soon as they are dropped in a folder.

The script includes a customizable function that may allow you to set meta-data
or custom attributes depending on the sub-folder in which the file has been dropped.

**This script's only output is in `./drop2beets.log`**.

TODO link to examples


## Examples wanted !

I'd be happy to include your own variations of this script in the `examples`
folder, feel free to post them in Issues or Pull Requests.

## Get started

You'll need Python3 on a Linux box, and obviously an existing [Beets](http://beets.io/) library.

    :::bash
    git clone git@github.com:martinkirch/drop2beets.git
    cd drop2beets/
    python3 -m venv drop2beets
    source drop2beets/bin/activate
    pip install -e .

Then, adapt `drop2beets.py` to your needs and machine.
You need to at least to change `BEETS_PATH`, `BEETS_DIRECTORY` and `DROPBOX`.
If you'd like to set some tags depending of which sub-folder the file is dropped in,
modify the `new_item` function.

You can test by calling `./drop2beets.py` on the command line and drop a few files to add.
Hit Ctrl+C to close the script.
Both good news and errors are always written to `./drop2beets.log`.

For a longer-term installation,

    :::bash
    sudo cp drop2beets.sh /etc/init.d/
    sudo update-rc.d drop2beets.sh defaults
    sudo service drop2beets.sh start

