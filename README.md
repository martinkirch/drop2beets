# drop2beets

Import singles to [Beets](http://beets.io/) as soon as they are dropped in a folder.
We use Beets' auto-tagger in quiet mode.

You can provide a function to set meta-data
or custom attributes depending on the sub-folder in which the file has been dropped.
The `examples` folder contains some examples of `on_item` functions you may
adapt to your needs.


## Get started

You'll need Python3 on a Linux box, and obviously an existing Beets library.
If you installed Beets in a virtual environment, activate it first.
Clone and install the plug-in:

```bash
git clone https://github.com/martinkirch/drop2beets.git
cd drop2beets/
pip install -e .
```

Enable and configure the plug-in by running `beet config -e` and set at least
the path to the "dropbox" folder.

```yaml
plugins: drop2beets
drop2beets:
    dropbox_path: ~/beets-dropbox
```

We advise you set Beets' `quiet_fallback` configuration option:

```yaml
import:
    quiet_fallback: asis
```

This parameter tells Beets what to do when the auto-tagger is not sure about
the song's identifiaction :
set it to `skip` to abort the importation in case of ambiguity,
or `asis` to import using tags as they are in the incoming file.
This will avoid surprises in case of ambiguous matches,
because this script invokes Beet's auto-tagger in quiet mode (as `beet import -q`)
after your custom function.

This function is `on_item`. It is written in Python,
and lets you set some tags depending of which sub-folder the file is dropped in.
If you want one, define it in the configuration:

```yaml
drop2beets:
    on_item: |
        def on_item(item, path):
            """
            Parameters:
                item: the beets Item that we're about to import
                path: its sub-folders path in our dropbox ; if the items has been dropped at the root, then it's empty.
            Returns:
                A dict of custom attributes (according to path, maybe) ; return None if you don't want to import the file right now.
            """
            return {}
```

Now you're ready to test by calling `beet dropbox` on the command line and
dropping a few files in the folder.
Hit Ctrl+C to close the script.

For a longer-term installation, configure a log file path

```yaml
drop2beets:
    log_path: ~/drop2beets/log.log
```

And install this as a user-lever systemd service by running `beet install_dropbox`
(in a shell where the virtual environment is activated).

Note that you'll have to restart the service when you update the `on_item` function.


## Examples wanted !

I'd be happy to include your own variations of this script or the `on_item` function
in the `examples` folder, feel free to post them in Issues or Pull Requests.
