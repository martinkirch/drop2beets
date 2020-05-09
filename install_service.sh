#!/bin/bash

## installs drop2beets as a systemd user service

set -e

if [ -z $VIRTUAL_ENV ]
then
    echo "VIRTUAL_ENV variable not found ; run this from the virtual environment you created when installing drop2beets (use 'activate')"
    exit 1
fi

CWD=`pwd`
PYTHON=`which python`

cat > drop2beets.service <<- END
[Unit]
Description=Drop2Beets

[Service]
Type=simple
ExecStart=$PYTHON $CWD/drop2beets.py
WorkingDirectory=$CWD
Restart=on-failure

[Install]
WantedBy=multi-user.target
END

mkdir -p ~/.config/systemd/user
mv drop2beets.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user start drop2beets
systemctl --user enable drop2beets

echo "All done ! Drop2beets is running and will run again when rebooting."
echo ""
echo "You can run"
echo "    systemctl --user start|stop|restart|status drop2beets"
echo "to start/stop/restart/see the service, and"
echo "    systemctl --user disable drop2beets'"
echo "to remove the service from startup."

