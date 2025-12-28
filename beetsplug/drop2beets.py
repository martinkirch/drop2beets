from __future__ import annotations
import logging
import os
import subprocess
from os.path import expanduser
from time import time

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent, FileMovedEvent

from beets import config
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, commands


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

class Drop2BeetsHandler(FileSystemEventHandler):
    """
    This class handles events in drop2beets' target folder.

    Implementation note:
    We must debounce events and import only a few seconds after the last one
    because no Watchdog event matches our definition of "a file appears". For
    example:
     - moving a file to the watched folder fires only FileCreatedEvent
     - moving a file *in* the watched folder fires FileMovedEvent
     - (s)cp a file to the watched folder fires FileCreatedEvent/FileModifiedEvent/FileClosedEvent
    also, starting the importation might fire an event on the file too.
    """

    # How many seconds should we wait for events to stop before importing
    DEBOUNCE_WINDOW = 10

    def __init__(self, lib):
        self.lib = lib
        self.debounce = {}
        super().__init__()

    def try_to_import(self):
        """
        Import paths that had no event for a few seconds (following DEBOUNCE_WINDOW).
        Cleanup paths that have been imported.
        """
        if self.debounce:
            limit = time() - self.DEBOUNCE_WINDOW
            for path, timestamp in list(self.debounce.items()):
                if timestamp <= 0:
                    del self.debounce[path]
                elif timestamp <= limit:
                    self.debounce[path] = -1
                    _logger.info("Processing %s", path)
                    commands.import_files(self.lib, [path], None)

    def on_any_event(self, event:FileSystemEvent):
        _logger.debug("got %r", event)
        if event and not event.is_directory:
            if isinstance(event, FileMovedEvent):
                fullpath = event.dest_path
            else:
                fullpath = event.src_path
            current = self.debounce.get(fullpath, 1)
            if current > 0:
                self.debounce[fullpath] = time()


class Drop2BeetsPlugin(BeetsPlugin):

    def __init__(self):
        super(Drop2BeetsPlugin, self).__init__()
        self.observer = None
        self.attributes = None
        self.dropbox_paths = {
            key: p.as_filename()
            for key in ['default', 'singleton']
            if (p := self.config['dropbox_paths'][key]).exists()
        }

        try:
            exec(self.config['on_item'].get(), globals())
            self.on_item = on_item
        except:
            self.on_item = lambda item, path: dict()

        self._command_dropbox = Subcommand('dropbox',
            help="Start watching %s for files to import automatically" %
                self.dropbox_paths.values())
        self._command_dropbox.func = self._main

        self._command_install = Subcommand('install_dropbox',
            help="Install drop2beets as a user-lever systemd service")
        self._command_install.func = self._install

    def commands(self):
        return [self._command_dropbox, self._command_install]

    def on_import_begin(self, session):
        if not session.config['singletons']:
            # If this is an album, ignore the missing_tracks penalty because tracks are being imported one by one
            if 'distance_weights' not in config['match']: config['match']['distance_weights'] = {}
            config['match']['distance_weights']['missing_tracks'] = 0.0
            # Also set duplicate_action to merge otherwise it will end up in a duplicate-skip because tracks are being imported one by one
            config['import']['duplicate_action'] = 'merge'
        config['import']['quiet'] = True
        self.attributes = None

    def on_import_task_created(self, task, session):
        if hasattr(task, 'item'):
            item = task.item
        elif hasattr(task, 'items') and len(task.items) > 0:
            item = task.items[0]
        else:
            # Some ImportTasks, like progress updates, have no item; ignore them
            return [task]

        path = str(item.path, 'utf-8', 'ignore')
        path_type = self._get_path_type(path)

        if not path_type:
            _logger.warn("Path type for %s not found", path)
            return [task]

        session.config['singletons'] = path_type == 'singleton'
        folder = os.path.dirname(path)
        dropbox_path = folder[len(self.dropbox_paths[path_type]):]
        self.attributes = self.on_item(item, dropbox_path)
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

        self.observer = Observer()
        handler = Drop2BeetsHandler(lib)
        for _, path in self.dropbox_paths.items():
            self.observer.schedule(handler, path, recursive=True)
            _logger.info("Drop2beets starting to watch %s", path)
        self.observer.start()
        try:
            while self.observer.is_alive():
                self.observer.join(1)
                handler.try_to_import()
        finally:
            self.observer.stop()
            self.observer.join()

    def _install(self, lib, opts, args):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(filename)s:%(lineno)s] %(levelname)s %(message)s"
        )
        beet_path = subprocess.getoutput("which beet")
        print(f"beet found in {beet_path}")
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

    def _get_path_type(self, path):
        for path_type, path_value in self.dropbox_paths.items():
            if path.startswith(path_value):
                return path_type

        return None
