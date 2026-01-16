import math
from time import time
from unittest.mock import Mock, patch

import pytest
from watchdog.events import (
    DirMovedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileMovedEvent,
    FileSystemEvent,
)

from beetsplug.drop2beets.handler.fs import (
    DefaultFileSystemEventHandler,
    SingletonFileSystemEventHandler,
)

from . import DummyFileSystemEventHandler


@pytest.fixture
def fs_event_handler(dropbox_dir, lib):
    return DummyFileSystemEventHandler(str(dropbox_dir), 1, lib)


# --- BaseFileSystemEventHandler.try_to_import ---


@patch("beetsplug.drop2beets.handler.fs.import_files")
def test_try_to_import_no_debounce(mock_import, fs_event_handler):
    fs_event_handler.try_to_import()
    mock_import.assert_not_called()


@pytest.mark.parametrize("timestamp", [0, -1])
def test_try_to_import_remove_negative_timestamps(fs_event_handler, timestamp):
    path = b"/path"
    fs_event_handler.debounce[path] = timestamp

    before_count = len(fs_event_handler.debounce)
    fs_event_handler.try_to_import()

    assert len(fs_event_handler.debounce) == before_count - 1
    assert path not in fs_event_handler.debounce


@patch("beetsplug.drop2beets.handler.fs.import_files")
@patch("beetsplug.drop2beets.handler.fs.time")
def test_try_to_import_process_expired(
    mock_time, mock_import, fs_event_handler
):
    path = b"/expired"
    mock_time.return_value = 100.0
    fs_event_handler.debounce[path] = 98.0

    fs_event_handler.try_to_import()

    assert fs_event_handler.debounce[path] == -1
    mock_import.assert_called_once_with(fs_event_handler.lib, [path], None)


def test_try_to_import_ignore_recent(fs_event_handler):
    path = b"/recent"
    fs_event_handler.debounce[path] = time()

    fs_event_handler.try_to_import()

    assert fs_event_handler.debounce[path] > 0


# --- BaseFileSystemEventHandler.on_any_event ---


def test_on_any_event_no_debounce_path(fs_event_handler):
    event = Mock(FileSystemEvent)
    with patch.object(
        fs_event_handler, "_get_debounce_path", return_value=None
    ):
        fs_event_handler.on_any_event(event)

    assert fs_event_handler.debounce == {}


@patch("beetsplug.drop2beets.handler.fs.time")
def test_on_any_event_update_timestamp(mock_time, fs_event_handler):
    event = Mock(FileSystemEvent)
    debounce_path = b"/test"
    mock_time.return_value = 123.45

    with patch.object(
        fs_event_handler, "_get_debounce_path", return_value=debounce_path
    ):
        fs_event_handler.on_any_event(event)

    assert math.isclose(fs_event_handler.debounce[debounce_path], 123.45)


@patch("beetsplug.drop2beets.handler.fs.time")
def test_on_any_event_ignore_existing_recent(mock_time, fs_event_handler):
    event = Mock(FileSystemEvent)
    debounce_path = b"/existing"
    mock_time.return_value = 100.0
    fs_event_handler.debounce[debounce_path] = 99.5  # recent

    with patch.object(
        fs_event_handler, "_get_debounce_path", return_value=debounce_path
    ):
        fs_event_handler.on_any_event(event)

    assert math.isclose(fs_event_handler.debounce[debounce_path], 100.0)


def test_on_any_event_skip_processing_path(fs_event_handler):
    event = Mock(FileSystemEvent)
    debounce_path = b"/processing"
    fs_event_handler.debounce[debounce_path] = -1

    with patch.object(
        fs_event_handler, "_get_debounce_path", return_value=debounce_path
    ):
        fs_event_handler.on_any_event(event)

    assert fs_event_handler.debounce[debounce_path] == -1


# --- DefaultFileSystemEventHandler / SingletonFileSystemEventHandler ---


def test_default_fs_handler_get_debounce_path(dropbox_dir, lib):
    handler = DefaultFileSystemEventHandler(str(dropbox_dir), 1, lib)
    event = Mock(FileSystemEvent)

    result = handler._get_debounce_path(event)

    assert result == bytes(dropbox_dir)


@pytest.mark.parametrize(
    "event_cls, path_attr, expected_path",
    [
        (FileMovedEvent, "dest_path", b"/dest/file.mp3"),
        (FileDeletedEvent, "src_path", b"/src/file.mp3"),
        (FileCreatedEvent, "src_path", b"/created/file.mp3"),
    ],
)
def test_singleton_fs_handler_get_debounce_path(
    event_cls, path_attr, expected_path, dropbox_dir, lib
):
    handler = SingletonFileSystemEventHandler(str(dropbox_dir), 1, lib)
    event = Mock(event_cls)
    setattr(event, path_attr, expected_path)
    event.is_directory = False

    result = handler._get_debounce_path(event)

    assert result == expected_path


def test_singleton_ignore_directory(dropbox_dir, lib):
    handler = SingletonFileSystemEventHandler(str(dropbox_dir), 1, lib)
    event = Mock(DirMovedEvent)
    event.is_directory = True

    result = handler._get_debounce_path(event)

    assert not result
