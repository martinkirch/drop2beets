# drop2beets

Import singles to [Beets](http://beets.io/) as soon as they are dropped in a folder.

The script includes a customizable function that may allow you to set meta-data
or custom attributes depending on the sub-folder in which the file has been dropped.

The `examples` folder contains some examples of `new_item` functions you may
adapt to your needs.

## Get started

You'll need Python3 on a Linux box, and obviously an existing Beets library.

```bash
git clone https://github.com/martinkirch/drop2beets.git
cd drop2beets/
python3 -m venv drop2beets
source drop2beets/bin/activate
pip install -e .
```

Then, adapt `drop2beets.py` to your needs and machine.
You need to at least to change `BEETS_PATH`, `BEETS_DIRECTORY` and `DROPBOX`.
If you'd like to set some tags depending of which sub-folder the file is dropped in,
modify the `new_item` function.

You can test by calling `./drop2beets.py` on the command line and drop a few files to add.
**This script's only output is always in `./drop2beets.log`**.
Hit Ctrl+C to close the script.

For a longer-term installation,
you can install it as a user-lever systemd service by running `./install_service.sh`
(in a shell where the virtual environment is activated).

Note that you'll have to restart the service when you update the `new_item` function.


## Examples wanted !

I'd be happy to include your own variations of this script or the `new_item` function
in the `examples` folder, feel free to post them in Issues or Pull Requests.
