import logging
from typing import TYPE_CHECKING, Any

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand

from beetsplug.drop2beets.handler.dropbox import (
    BaseDropboxHandler,
    create_dropbox_handler,
)
from beetsplug.drop2beets.ui.subcommand import (
    DropboxSubcommand,
    InstallSubcommand,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from beets.library import Item

log = logging.getLogger("drop2beets")


class Drop2BeetsPlugin(BeetsPlugin):
    """Beets plugin for automatic import of music files from dropbox folders."""

    def __init__(self) -> None:
        super().__init__()

        self.config.add(
            {
                "debounce_window": 10,
                "dropbox_paths": {},
                "log_path": None,
                "on_item": None,
            }
        )

        self.debounce_window: int = self.config["debounce_window"].get(int)
        self.log_path: str | None = (
            self.config["log_path"].as_filename()
            if self.config["log_path"]
            else None
        )

        self.on_item: Callable[[Item, str], dict[str, str] | None]
        on_item_code: str | None = self.config["on_item"].get()

        if on_item_code:
            local_ns: dict[str, Any] = {}
            exec(on_item_code, globals(), local_ns)
            self.on_item = local_ns["on_item"]
        else:
            self.on_item = lambda item, path: {}

        self.dropbox_handlers: list[BaseDropboxHandler] = [
            dropbox_handler
            for key in self.config["dropbox_paths"].keys()
            if (
                dropbox_handler := create_dropbox_handler(
                    key,
                    self.config["dropbox_paths"][key],
                    self.debounce_window,
                    self.on_item,
                )
            )
        ]

        # Fallback to drop2beets.dropbox_path. Will be removed in the future.
        if not self.dropbox_handlers:
            log.warning(
                "The 'drop2beets.dropbox_path' config is deprecated, "
                "use 'drop2beets.dropbox_paths.singleton' instead"
            )
            if dropbox_handler := create_dropbox_handler(
                "singleton",
                self.config["dropbox_path"],
                self.debounce_window,
                self.on_item,
            ):
                self.dropbox_handlers.append(dropbox_handler)

    def commands(self) -> list[Subcommand]:
        return [
            DropboxSubcommand(
                self.log_path, self.dropbox_handlers, self.register_listener
            ),
            InstallSubcommand(),
        ]
