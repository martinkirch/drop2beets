import logging
from abc import ABC, abstractmethod
from pathlib import Path
from time import time

from beets.library import Library
from watchdog.events import (
    FileMovedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)

try:
    from beets.ui.commands.import_ import (  # type: ignore[import-not-found]
        import_files,
    )
except ImportError:
    # for beets<=2.5.1:
    from beets.ui.commands import import_files

log = logging.getLogger("drop2beets")


class BaseFileSystemEventHandler(ABC, FileSystemEventHandler):
    """Base class for handling filesystem events in the dropbox folder.

    Implements debouncing to avoid triggering imports
    while files are still being written.
    """

    def __init__(
        self, dropbox_path: Path, debounce_window: int, lib: Library
    ) -> None:
        super().__init__()

        self.dropbox_path: Path = dropbox_path
        self.debounce_window: int = debounce_window
        self.lib: Library = lib

        self.debounce: dict[bytes, float] = {}

    def try_to_import(self) -> None:
        if self.debounce:
            limit = time() - self.debounce_window
            to_remove: list[bytes] = []
            to_process: list[bytes] = []

            for path, timestamp in self.debounce.items():
                if timestamp <= 0:
                    to_remove.append(path)
                elif timestamp <= limit:
                    self.debounce[path] = -1
                    to_process.append(path)

            for path in to_remove:
                del self.debounce[path]

            for path in to_process:
                log.info("Processing %s", path.decode(errors="ignore"))
                import_files(self.lib, [path], None)

    def on_any_event(self, event: FileSystemEvent) -> None:
        log.debug("Received event: %r", event)
        debounce_path = self._get_debounce_path(event)

        if debounce_path:
            current = self.debounce.get(debounce_path, 1)
            if current > 0:
                self.debounce[debounce_path] = time()

    @abstractmethod
    def _get_debounce_path(self, event: FileSystemEvent) -> bytes | None:
        """Returns the path to use as debounce key for the given event.

        Returns None to ignore the event.
        """


class DefaultFileSystemEventHandler(BaseFileSystemEventHandler):
    """Filesystem event handler that debounces on the entire dropbox folder."""

    def _get_debounce_path(self, event: FileSystemEvent) -> bytes | None:
        return str(self.dropbox_path).encode(errors="ignore")


class SingletonFileSystemEventHandler(BaseFileSystemEventHandler):
    """Filesystem event handler that debounces on individual files."""

    def _get_debounce_path(self, event: FileSystemEvent) -> bytes | None:
        if event and not event.is_directory:
            if isinstance(event, FileMovedEvent):
                path = event.dest_path
            else:
                path = event.src_path
            return (
                path.encode(errors="ignore") if isinstance(path, str) else path
            )
        return None
