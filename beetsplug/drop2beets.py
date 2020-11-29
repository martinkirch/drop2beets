import logging
import os
import subprocess
from os.path import expanduser

from inotify.adapters import InotifyTree

from beets import config
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets.ui.commands import import_files


_logger = logging.getLogger("drop2beets")

_SERVICE_TEMPLATE = """
[Unit]
Description=Drop2Beets

[Service]
Type=simple
ExecStart={beet_path} dropbox
Restart=on-failure

[Install]
WantedBy=default.target
"""

class Drop2BeetsPlugin(BeetsPlugin):

    def __init__(self):
        super(Drop2BeetsPlugin, self).__init__()
        self.attributes = None
        self.dropbox_path = self.config['dropbox_path'].as_filename()

        try:
            exec(self.config['on_item'].get(), globals())
            self.on_item = on_item
        except:
            self.on_item = lambda item, path: dict()

        self._command_dropbox = Subcommand('dropbox',
            help="Start watching %s for files to import automatically" %
                self.dropbox_path)
        self._command_dropbox.func = self._main

        self._command_install = Subcommand('install_dropbox',
            help="Install drop2beets as a user-lever systemd service")
        self._command_install.func = self._install

    def commands(self):
        return [self._command_dropbox, self._command_install]

    def on_import_begin(self, session):
        session.config['singletons'] = True
        config['import']['quiet'] = True
        self.attributes = None

    def on_import_task_created(self, task, session):
        path = str(task.item.path, 'utf-8', 'ignore')
        folder = os.path.dirname(path)
        dropbox_path = folder[len(self.dropbox_path):]
        self.attributes = self.on_item(task.item, dropbox_path)
        if self.attributes is None:
            _logger.info("Importation aborted by on_item")
            return []
        else:
            _logger.info("Applying %s", self.attributes)
            return [task]

    def on_item_imported(self, lib, item):
        if self.attributes:
            item.update(self.attributes)
            item.store()

    def _main(self, lib, opts, args):
        try:
            log_path = self.config['log_path'].as_filename()
        except:
            log_path = None
        logging.basicConfig(
            filename=log_path,
            level=logging.WARNING,
            format="%(asctime)s [%(filename)s:%(lineno)s] %(levelname)s %(message)s"
        )
        _logger.setLevel(logging.INFO)
        logging.getLogger('beets').addHandler(logging.getLogger().handlers[0])

        self.register_listener('import_begin', self.on_import_begin)
        self.register_listener('import_task_created', self.on_import_task_created)
        self.register_listener('item_imported', self.on_item_imported)

        i = InotifyTree(self.dropbox_path)
        _logger.info("Drop2beets starting to watch %s", self.dropbox_path)
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
                import_files(lib, [full_path], None)

    def _install(self, lib, opts, args):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(filename)s:%(lineno)s] %(levelname)s %(message)s"
        )
        beet_path = subprocess.getoutput("which beet")
        print("beet found in %s" % beet_path)
        with open("drop2beets.service", "w") as service_file:
            service_file.write(_SERVICE_TEMPLATE.format(beet_path=beet_path))

        targetdir = expanduser("~/.config/systemd/user")
        subprocess.run(["mkdir", "-p", targetdir], check=True)
        subprocess.run(["mv", "drop2beets.service", targetdir], check=True)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "start", "drop2beets"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "drop2beets"], check=True)
        subprocess.run(["loginctl", "enable-linger", os.getlogin()], check=True)

        print("""
        All done ! Drop2beets is running and will run again when rebooting (we enabled systemd's lingering)

        You can run
            systemctl --user start|stop|restart|status drop2beets
        to start/stop/restart/see the service, and
            systemctl --user disable drop2beets
        to remove the service from startup.
        """)
