import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, overload

from beets import config
from beets.importer import ImportSession, ImportTask, SingletonImportTask
from beets.library import Item, Library
from confuse import ConfigView  # type: ignore[import-untyped]

from beetsplug.drop2beets.handler.fs import (
    BaseFileSystemEventHandler,
    DefaultFileSystemEventHandler,
    SingletonFileSystemEventHandler,
)

log = logging.getLogger("drop2beets")


class BaseDropboxHandler(ABC):
    """Base class for handling imports from a dropbox folder.

    Manages the import lifecycle including event handling, path validation,
    and applying custom attributes to imported items.
    """

    _session_config: dict[str, Any] = {}
    """Session configuration to apply when import begins
    (merged into session.config)."""

    def __init__(
        self,
        dropbox_path: str,
        debounce_window: int,
        on_item: Callable[[Item, str], dict[str, str] | None],
    ) -> None:
        self._attributes: dict[str, dict[str, str] | None] = {}
        self._fs_event_handler: BaseFileSystemEventHandler | None = None

        self.dropbox_path: Path = self._normalize_path(dropbox_path)
        self.debounce_window: int = debounce_window
        self.on_item: Callable[[Item, str], dict[str, str] | None] = on_item

    def get_fs_handler(self, lib: Library) -> BaseFileSystemEventHandler:
        if self._fs_event_handler is None:
            self._fs_event_handler = self._get_fs_handler_cls()(
                self.dropbox_path, self.debounce_window, lib
            )

        return self._fs_event_handler

    def on_import_begin(self, session: ImportSession) -> None:
        if not self._is_responsible_for_path(session):
            return

        config["import"]["quiet"] = True
        for key, value in self._session_config.items():
            session.config[key] = value
        self._attributes = {}

    def on_import_task_created(
        self, task: SingletonImportTask | ImportTask, session: ImportSession
    ) -> list[ImportTask]:
        if not self._is_responsible_for_path(session):
            return []

        if not hasattr(task, "items") and not hasattr(task, "item"):
            return [task]

        items: list[Item] = (
            [task.item] if isinstance(task, SingletonImportTask) else task.items
        )
        valid_items: list[Item] = []

        for item in items:
            path_str = item.path.decode(errors="ignore")
            dropbox_rel_path = Path(path_str).parent.relative_to(
                self.dropbox_path
            )

            self._attributes[path_str] = self.on_item(
                item, str(dropbox_rel_path)
            )

            if self._attributes[path_str] is None:
                log.info("Skipped import of %s by on_item", path_str)
            else:
                if self._attributes[path_str]:
                    log.info(
                        "Applying attributes to %s: %s",
                        path_str,
                        self._attributes[path_str],
                    )
                valid_items.append(item)

        if valid_items:
            if isinstance(task, SingletonImportTask):
                task.item = valid_items[0]
            else:
                task.items = valid_items

            return [task]
        else:
            return []

    # noinspection PyUnusedLocal
    def on_item_imported(self, lib: Library, item: Item) -> None:
        if not self._is_responsible_for_path(item):
            return

        path_str = str(self._normalize_path(item.path.decode(errors="ignore")))
        if path_str in self._attributes and self._attributes[path_str]:
            item.update(self._attributes[path_str])
            item.store()

    @overload
    def _is_responsible_for_path(self, input_: ImportSession) -> bool: ...

    @overload
    def _is_responsible_for_path(self, input_: Item) -> bool: ...

    def _is_responsible_for_path(self, input_: ImportSession | Item) -> bool:
        if isinstance(input_, ImportSession) and input_.paths:
            path_raw = input_.paths[0]
        elif isinstance(input_, Item):
            path_raw = input_.path
        else:
            return False

        path = self._normalize_path(path_raw.decode(errors="ignore"))
        return path.is_relative_to(self.dropbox_path)

    @staticmethod
    def _normalize_path(path: str) -> Path:
        return Path(path).resolve()

    @abstractmethod
    def _get_fs_handler_cls(self) -> type[BaseFileSystemEventHandler]:
        """Returns the file system event handler class for this dropbox type."""


class DefaultDropboxHandler(BaseDropboxHandler):
    """Handler for importing entire albums from the dropbox folder."""

    def _get_fs_handler_cls(self) -> type[BaseFileSystemEventHandler]:
        return DefaultFileSystemEventHandler


class SingletonDropboxHandler(BaseDropboxHandler):
    """Handler for importing individual tracks (singletons) from the dropbox folder."""

    _session_config = {"singletons": True}

    def _get_fs_handler_cls(self) -> type[BaseFileSystemEventHandler]:
        return SingletonFileSystemEventHandler


_DROPBOX_HANDLER: Final[dict[str, type[BaseDropboxHandler]]] = {
    "default": DefaultDropboxHandler,
    "singleton": SingletonDropboxHandler,
}


def create_dropbox_handler(
    key: str,
    dropbox_path: ConfigView,
    debounce_window: int,
    on_item: Callable[[Item, str], dict[str, str] | None],
) -> BaseDropboxHandler | None:
    """Factory function to create a dropbox handler by key.

    Returns None if the dropbox_path doesn't exist or the key is unknown.
    """
    if not dropbox_path.exists():
        return None

    handler_cls = _DROPBOX_HANDLER.get(key)
    if handler_cls is None:
        return None

    return handler_cls(dropbox_path.as_filename(), debounce_window, on_item)
