from watchdog.events import FileSystemEvent

from beetsplug.drop2beets.handler.fs import BaseFileSystemEventHandler


class DummyFileSystemEventHandler(BaseFileSystemEventHandler):
    def _get_debounce_path(self, event: FileSystemEvent) -> bytes | None:
        return b"/tmp/debounce"
