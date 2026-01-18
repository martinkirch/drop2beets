from time import sleep
from watchdog.events import FileSystemEvent, FileMovedEvent
from beetsplug.drop2beets import Drop2BeetsSingletonHandler

def test_debounce(monkeypatch):
    debounce_window = 10
    handler = Drop2BeetsSingletonHandler(None, debounce_window, None)

    imported_paths = None
    def fake_import (lib, paths, query):
        nonlocal imported_paths
        imported_paths = paths
        # the following flag shows that import has started: future events should be ignored
        # also, we expect exactly one path here
        assert handler.debounce[imported_paths[0]] < 0
    monkeypatch.setattr("beetsplug.drop2beets.import_files", fake_import)

    imported_paths = None
    handler.try_to_import()
    assert imported_paths is None # nothing to import

    handler.on_any_event(FileSystemEvent("some/songA.flac"))
    imported_paths = None
    handler.try_to_import()
    assert imported_paths is None

    sleep(debounce_window / 2.)
    handler.on_any_event(FileMovedEvent("/some/store/songB.flac", "some/songB.flac"))
    imported_paths = None
    handler.try_to_import()
    assert imported_paths is None

    sleep(debounce_window / 2. + 0.01)
    handler.on_any_event(FileSystemEvent("some/songB.flac"))
    imported_paths = None
    handler.try_to_import()
    assert imported_paths == ["some/songA.flac"]
    # new events on songA should be ignored because they're likely caused by Beets' import
    handler.on_any_event(FileSystemEvent("some/songA.flac"))

    sleep(debounce_window / 2. + 0.01)
    imported_paths = None
    handler.try_to_import()
    assert imported_paths is None

    sleep(debounce_window + 0.01)
    imported_paths = None
    handler.try_to_import()
    assert imported_paths == ["some/songB.flac"]

