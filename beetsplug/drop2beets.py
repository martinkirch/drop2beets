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
from beets.ui import Subcommand
try:
    from beets.ui.commands.import_ import import_files
except ImportError:
    # for beets<=2.5.1:
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

class Drop2BeetsDefaultHandler(FileSystemEventHandler):
    """
    This class handles events in drop2beets' default target folder.

    Implementation note:
    We must debounce events and import only a few seconds after the last one
    because no Watchdog event matches our definition of "a file appears". For
    example:
     - moving a file to the watched folder fires only FileCreatedEvent
     - moving a file *in* the watched folder fires FileMovedEvent
     - (s)cp a file to the watched folder fires FileCreatedEvent/FileModifiedEvent/FileClosedEvent
    also, starting the importation might fire an event on the file too.

    In the default dropbox, all events are debounced together on the root
    dropbox_path. This is intentional so that when multiple album folders are
    uploaded in parallel and their events are interleaved, drop2beets still
    waits until the whole tree has settled before triggering a single import.
    """

    def __init__(self, dropbox_path, debounce_window:int, lib):
        self.dropbox_path = dropbox_path
        self.debounce_window = debounce_window
        self.lib = lib
        self.debounce = {}
        super().__init__()

    def try_to_import(self):
        """
        Import paths that had no event for a few seconds (following self.debounce_window).
        Cleanup paths that have been imported.
        """
        if self.debounce:
            limit = time() - self.debounce_window
            for path, timestamp in list(self.debounce.items()):
                if timestamp <= 0:
                    del self.debounce[path]
                elif timestamp <= limit:
                    self.debounce[path] = -1
                    _logger.info("Processing %s", path)
                    import_files(self.lib, [path], None)

    def on_any_event(self, event:FileSystemEvent):
        _logger.debug("got %r", event)
        debounce_path = self._get_debounce_path(event)
        if debounce_path:
            current = self.debounce.get(debounce_path, 1)
            if current > 0:
                self.debounce[debounce_path] = time()

    def _get_debounce_path(self, event:FileSystemEvent):
        return self.dropbox_path

class Drop2BeetsSingletonHandler(Drop2BeetsDefaultHandler):
    """
    This class handles events in drop2beets' singleton target folder.

    Like the default handler, it debounces filesystem activity for a few
    seconds after the last event because no Watchdog event matches our
    definition of "a file appears" (moving a file, copying it, or even the
    import itself can all generate different event sequences).

    Unlike the default handler, debouncing is done per file path instead of
    the whole dropbox_path. This is suited for single tracks: each file is
    imported on its own after its own stream of events has settled.
    """

    def _get_debounce_path(self, event:FileSystemEvent):
        if event and not event.is_directory:
            if isinstance(event, FileMovedEvent):
                return event.dest_path
            else:
                return event.src_path
        return None

class Drop2BeetsPlugin(BeetsPlugin):

    def __init__(self):
        super(Drop2BeetsPlugin, self).__init__()
        self.observer = None
        self.attributes = {}
        self.debounce_window = int(self.config['debounce_window'].as_number()) \
            if self.config['debounce_window'].exists() else 10
        self.dropbox_paths = {
            key: self._normalize_path(p.as_filename())
            for key in ['default', 'singleton']
            if (p := self.config['dropbox_paths'][key]).exists()
        }
        # Fallback to drop2beets.dropbox_path. Will be removed in the future.
        if len(self.dropbox_paths) == 0:
            _logger.warning("The 'drop2beets.dropbox_path' config is deprecated, "
                          "use 'drop2beets.dropbox_paths.singleton' instead")
            self.dropbox_paths['singleton'] = self._normalize_path(self.config['dropbox_path'].as_filename())

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
        if len(session.paths) == 1 and os.path.isfile(session.paths[0]):
            session.config['singletons'] = True
        config['import']['quiet'] = True
        self.attributes = {}

    def on_import_task_created(self, task, session):
        # Some ImportTasks, like progress updates, have no item; ignore them
        if not hasattr(task, 'items') and not hasattr(task, 'item'):
            return [task]
        items = task.items if task.is_album else [task.item]
        valid_items = []
        for item in items:
            path = str(item.path, 'utf-8', 'ignore')
            path_type = self._get_path_type(path)

            if not path_type:
                _logger.warning("Path type for %s not found", path)
                continue

            folder = os.path.dirname(path)
            dropbox_path = folder[len(self.dropbox_paths[path_type]):]
            self.attributes[path] = self.on_item(item, dropbox_path)
            if self.attributes[path] is None:
                _logger.info("Importation of %s skipped by on_item", path)
            else:
                _logger.info("Applying %s", self.attributes[path])
                valid_items.append(item)

        if task.is_album:
            task.items = valid_items
        else:
            task.item = valid_items[0]

        if len(valid_items) == 0:
            return []

        return [task]

    def on_item_imported(self, lib, item):
        path = str(item.path, 'utf-8', 'ignore')
        if path in self.attributes:
            item.update(self.attributes[path])
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
        handlers = {
            path_value: (Drop2BeetsSingletonHandler(path_value, self.debounce_window, lib)
                         if path_type == 'singleton'
                         else Drop2BeetsDefaultHandler(path_value, self.debounce_window, lib))
            for path_type, path_value in self.dropbox_paths.items()
        }
        for path, handler in handlers.items():
            self.observer.schedule(handler, path, recursive=True)
            _logger.info("Drop2beets starting to watch %s", path)
        self.observer.start()
        try:
            while self.observer.is_alive():
                self.observer.join(1)
                for _, handler in handlers.items():
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

    def _normalize_path(self, path):
        return os.path.abspath(path.rstrip(os.sep))

    def _get_path_type(self, path):
        normalized_path = self._normalize_path(path)
        best_match = None
        best_len = -1

        for path_type, root in self.dropbox_paths.items():
            prefix = root + os.sep
            if normalized_path == root or normalized_path.startswith(prefix):
                if len(root) > best_len:
                    best_len = len(root)
                    best_match = path_type

        return best_match
