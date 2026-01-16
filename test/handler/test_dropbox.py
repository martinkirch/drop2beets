import os
from collections.abc import Callable
from unittest.mock import Mock

import pytest
from beets import config
from beets.importer import ImportSession, ImportTask, SingletonImportTask
from beets.library import Item
from confuse import ConfigView  # type: ignore[import-untyped]

from beetsplug.drop2beets.handler.dropbox import (
    BaseDropboxHandler,
    DefaultDropboxHandler,
    SingletonDropboxHandler,
    create_dropbox_handler,
)
from beetsplug.drop2beets.handler.fs import (
    BaseFileSystemEventHandler,
    DefaultFileSystemEventHandler,
    SingletonFileSystemEventHandler,
)

from . import DummyFileSystemEventHandler


class DummyDropboxHandler(BaseDropboxHandler):
    def _get_fs_handler_cls(self) -> type[BaseFileSystemEventHandler]:
        return DummyFileSystemEventHandler


@pytest.fixture
def on_item_mock() -> Callable[[Item, str], dict[str, str] | None]:
    return Mock(return_value={"key": "value"})


@pytest.fixture
def dropbox_handler(dropbox_dir, on_item_mock) -> BaseDropboxHandler:
    return DummyDropboxHandler(str(dropbox_dir), 1, on_item_mock)


@pytest.fixture(autouse=True)
def clear_handler_attributes(dropbox_handler):
    dropbox_handler._attributes.clear()
    yield
    dropbox_handler._attributes.clear()


@pytest.fixture
def mock_item(lib, dropbox_dir):
    return Mock(
        Item,
        path=bytes(dropbox_dir / "sub" / "file.mp3"),
        update=Mock(),
        store=Mock(),
    )


@pytest.fixture
def mock_album_items(lib, dropbox_dir):
    item1 = Mock(Item)
    item1.path = bytes(dropbox_dir / "ok" / "file.mp3")
    item2 = Mock(Item)
    item2.path = bytes(dropbox_dir / "skip" / "file.mp3")
    item3 = Mock(Item)
    item3.path = bytes(dropbox_dir / "ok" / "file2.mp3")
    return [item1, item2, item3]


def make_import_session(paths):
    return Mock(
        ImportSession,
        paths=paths,
        config=config["import"],
    )


# --- BaseDropboxHandler.get_fs_handler ---


def test_get_fs_handler_lazy_instantiation(dropbox_handler, lib):
    assert not dropbox_handler._fs_event_handler

    fs_handler = dropbox_handler.get_fs_handler(lib)

    assert isinstance(fs_handler, DummyFileSystemEventHandler)
    assert fs_handler is dropbox_handler.get_fs_handler(lib)


# --- BaseDropboxHandler._normalize_path ---


@pytest.mark.parametrize("suffix", ["", os.sep])
def test_normalize_path_strips_trailing_sep(tmp_path, suffix):
    raw = str(tmp_path) + suffix

    normalized = BaseDropboxHandler._normalize_path(raw)

    assert normalized == tmp_path.resolve()
    assert not str(normalized).endswith(os.sep)


# --- BaseDropboxHandler._is_responsible_for_path ---


def test_is_responsible_for_path_with_session_inside_dropbox(
    dropbox_handler, dropbox_dir
):
    session = make_import_session([bytes(dropbox_dir / "sub" / "file.mp3")])

    assert dropbox_handler._is_responsible_for_path(session)


def test_is_responsible_for_path_with_session_outside_dropbox(
    dropbox_handler, tmp_path
):
    session = make_import_session([bytes(tmp_path / "other" / "file.mp3")])

    assert not dropbox_handler._is_responsible_for_path(session)


def test_is_responsible_for_path_with_session_empty_paths(dropbox_handler):
    session = make_import_session([])

    assert not dropbox_handler._is_responsible_for_path(session)


def test_is_responsible_for_path_with_item_inside_dropbox(
    dropbox_handler, mock_item
):
    assert dropbox_handler._is_responsible_for_path(mock_item)


def test_is_responsible_for_path_with_item_outside_dropbox(
    dropbox_handler, lib, tmp_path
):
    item = Mock(
        Item,
        path=bytes(tmp_path / "other" / "file.mp3"),
    )

    assert not dropbox_handler._is_responsible_for_path(item)


def test_is_responsible_for_path_exact_dropbox_dir(
    dropbox_handler, lib, dropbox_dir
):
    item = Mock(
        Item,
        path=bytes(dropbox_dir / "file.mp3"),
    )

    assert dropbox_handler._is_responsible_for_path(item)


# --- BaseDropboxHandler.on_import_begin ---


def test_on_import_begin_sets_quiet(dropbox_handler, dropbox_dir):
    session = make_import_session([bytes(dropbox_dir / "sub" / "file.mp3")])

    dropbox_handler.on_import_begin(session)

    assert config["import"]["quiet"].get(bool)


def test_on_import_begin_clears_attributes(dropbox_handler, dropbox_dir):
    session = make_import_session([bytes(dropbox_dir / "sub" / "file.mp3")])
    dropbox_handler._attributes = {"x": {"y": "z"}}

    dropbox_handler.on_import_begin(session)

    assert dropbox_handler._attributes == {}


def test_on_import_begin_ignored_for_unrelated_path(dropbox_handler, tmp_path):
    session = make_import_session([bytes(tmp_path / "other" / "file.mp3")])
    dropbox_handler._attributes = {"x": {"y": "z"}}

    dropbox_handler.on_import_begin(session)

    assert dropbox_handler._attributes == {"x": {"y": "z"}}
    assert not config["import"]["quiet"].get(bool)


# --- BaseDropboxHandler.on_import_task_created (album and single) ---


def _build_task_for_items(items):
    if len(items) > 1:
        task = Mock(ImportTask)
        task.items = items
    else:
        task = Mock(SingletonImportTask)
        task.item = items[0]
    return task


def test_on_import_task_created_ignores_tasks_without_items(
    dropbox_handler, dropbox_dir
):
    session = make_import_session([bytes(dropbox_dir / "sub" / "file.mp3")])
    task = Mock(ImportTask)

    result = dropbox_handler.on_import_task_created(task, session)

    assert result == [task]


def test_on_import_task_created_album_filters_items(
    dropbox_handler, mock_album_items, dropbox_dir, on_item_mock
):
    def side_effect(item, dropbox_rel):
        if item is mock_album_items[1]:
            return None
        elif item is mock_album_items[2]:
            return {}
        return {"tag": dropbox_rel}

    on_item_mock.side_effect = side_effect
    session = make_import_session([bytes(dropbox_dir / "ok")])
    task = _build_task_for_items(mock_album_items)

    result = dropbox_handler.on_import_task_created(task, session)

    assert result == [task]
    assert task.items == [mock_album_items[0], mock_album_items[2]]
    p1 = mock_album_items[0].path.decode(errors="ignore")
    p2 = mock_album_items[1].path.decode(errors="ignore")
    p3 = mock_album_items[2].path.decode(errors="ignore")
    assert dropbox_handler._attributes[p1] == {"tag": "ok"}
    assert dropbox_handler._attributes[p2] is None
    assert dropbox_handler._attributes[p3] == {}


def test_on_import_task_created_album_all_items_filtered_returns_empty(
    dropbox_handler, mock_album_items, dropbox_dir, on_item_mock
):
    on_item_mock.return_value = None
    session = make_import_session(
        [bytes(mock_album_items[0].path).decode().rsplit(os.sep, 2)[0].encode()]
    )
    task = _build_task_for_items(mock_album_items)

    result = dropbox_handler.on_import_task_created(task, session)

    assert result == []


def test_on_import_task_created_single_item(
    dropbox_handler, mock_item, dropbox_dir, on_item_mock
):
    session = make_import_session([mock_item.path])
    task = _build_task_for_items([mock_item])

    result = dropbox_handler.on_import_task_created(task, session)

    assert result == [task]
    assert task.item is mock_item
    p = mock_item.path.decode(errors="ignore")
    assert dropbox_handler._attributes[p] == {"key": "value"}


def test_on_import_task_created_single_item_all_filtered(
    dropbox_handler, mock_item, dropbox_dir, on_item_mock
):
    on_item_mock.return_value = None
    session = make_import_session([mock_item.path])
    task = _build_task_for_items([mock_item])

    result = dropbox_handler.on_import_task_created(task, session)

    assert result == []


def test_on_import_task_created_session_not_responsible(
    dropbox_handler, lib, tmp_path
):
    item = Mock(Item)
    item.path = bytes(tmp_path / "other" / "file.mp3")
    session = make_import_session([item.path])
    task = _build_task_for_items([item])

    result = dropbox_handler.on_import_task_created(task, session)

    assert result == []


# --- BaseDropboxHandler.on_item_imported ---


def test_on_item_imported_updates_and_stores_when_attributes_present(
    dropbox_handler, mock_item
):
    norm_path = str(
        dropbox_handler._normalize_path(mock_item.path.decode(errors="ignore"))
    )
    dropbox_handler._attributes[norm_path] = {"key": "value"}

    dropbox_handler.on_item_imported(Mock(), mock_item)

    mock_item.update.assert_called_once_with({"key": "value"})
    mock_item.store.assert_called_once()


def test_on_item_imported_ignored_when_not_responsible(
    dropbox_handler, lib, tmp_path
):
    item = Mock(Item)
    item.path = bytes(tmp_path / "other" / "file.mp3")

    dropbox_handler.on_item_imported(lib, item)

    item.update.assert_not_called()
    item.store.assert_not_called()


def test_on_item_imported_no_attributes(dropbox_handler, mock_item):
    dropbox_handler.on_item_imported(Mock(), mock_item)

    mock_item.update.assert_not_called()
    mock_item.store.assert_not_called()


# --- DefaultDropboxHandler / SingletonDropboxHandler ---


def test_default_dropbox_handler_fs_class(dropbox_dir, on_item_mock):
    h = DefaultDropboxHandler(str(dropbox_dir), 1, on_item_mock)

    assert isinstance(h.get_fs_handler(Mock()), DefaultFileSystemEventHandler)


def test_singleton_dropbox_handler_fs_class(dropbox_dir, on_item_mock):
    h = SingletonDropboxHandler(str(dropbox_dir), 1, on_item_mock)

    assert isinstance(h.get_fs_handler(Mock()), SingletonFileSystemEventHandler)


def test_singleton_dropbox_handler_on_import_begin_sets_singletons(
    dropbox_dir, on_item_mock
):
    h = SingletonDropboxHandler(str(dropbox_dir), 1, on_item_mock)
    session = make_import_session([bytes(dropbox_dir / "file.mp3")])

    h.on_import_begin(session)

    assert config["import"]["quiet"].get(bool)
    assert session.config["singletons"].get(bool)


# --- create_dropbox_handler ---


class DummyConfigView(ConfigView):
    def __init__(self, exists_flag: bool, filename: str | None = None):
        object.__init__(self)
        self._exists_flag = exists_flag
        self._filename = filename

    def exists(self) -> bool:
        return self._exists_flag

    def as_filename(self) -> str:
        if self._filename is None:
            raise AssertionError("as_filename called without filename")
        return self._filename


def test_create_dropbox_handler_returns_none_when_path_missing(on_item_mock):
    cv = DummyConfigView(False)

    result = create_dropbox_handler("default", cv, 1, on_item_mock)

    assert not result


def test_create_dropbox_handler_returns_none_for_invalid_key(
    on_item_mock, tmp_path
):
    cv = DummyConfigView(True, str(tmp_path))

    result = create_dropbox_handler("unknown", cv, 1, on_item_mock)

    assert result is None


@pytest.mark.parametrize(
    "key, expected_cls",
    [
        ("default", DefaultDropboxHandler),
        ("singleton", SingletonDropboxHandler),
    ],
)
def test_create_dropbox_handler_creates_correct_handler_type(
    key, expected_cls, on_item_mock, tmp_path
):
    cv = DummyConfigView(True, str(tmp_path))

    result = create_dropbox_handler(key, cv, 1, on_item_mock)

    assert isinstance(result, expected_cls)
