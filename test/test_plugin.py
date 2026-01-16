import textwrap
from typing import TYPE_CHECKING
from unittest.mock import Mock

from beets import config
from beets.library import Item

from beetsplug.drop2beets import Drop2BeetsPlugin
from beetsplug.drop2beets.handler.dropbox import (
    DefaultDropboxHandler,
    SingletonDropboxHandler,
)
from beetsplug.drop2beets.ui.subcommand import (
    DropboxSubcommand,
    InstallSubcommand,
)

if TYPE_CHECKING:
    from beets.ui import Subcommand


# --- Drop2BeetsPlugin.__init__ ---


def test_plugin_has_default_config() -> None:
    plugin = Drop2BeetsPlugin()

    assert plugin.config.flatten() == {
        "debounce_window": 10,
        "dropbox_paths": {},
        "log_path": None,
        "on_item": None,
    }


def test_plugin_uses_custom_debounce_window() -> None:
    config["drop2beets"]["debounce_window"] = 60

    plugin = Drop2BeetsPlugin()

    assert plugin.debounce_window == 60


def test_plugin_uses_custom_log_path() -> None:
    config["drop2beets"]["log_path"] = "/tmp/dropbox/log"

    plugin = Drop2BeetsPlugin()

    assert plugin.log_path == "/tmp/dropbox/log"


def test_plugin_uses_custom_on_item() -> None:
    config["drop2beets"]["on_item"] = textwrap.dedent("""
        def on_item(item, path):
            return {"key": "value"}
    """)

    plugin = Drop2BeetsPlugin()
    attributes = plugin.on_item(Mock(Item), "")

    assert attributes == {"key": "value"}


def test_plugin_creates_default_dropbox_handler() -> None:
    config["drop2beets"]["dropbox_paths"] = {
        "default": "/tmp/dropbox/default",
    }

    plugin = Drop2BeetsPlugin()

    assert len(plugin.dropbox_handlers) == 1
    assert isinstance(plugin.dropbox_handlers[0], DefaultDropboxHandler)


def test_plugin_creates_singleton_dropbox_handler() -> None:
    config["drop2beets"]["dropbox_paths"] = {
        "singleton": "/tmp/dropbox/singleton",
    }

    plugin = Drop2BeetsPlugin()

    assert len(plugin.dropbox_handlers) == 1
    assert isinstance(plugin.dropbox_handlers[0], SingletonDropboxHandler)


def test_plugin_creates_multiple_dropbox_handlers() -> None:
    config["drop2beets"]["dropbox_paths"] = {
        "default": "/tmp/dropbox/default",
        "singleton": "/tmp/dropbox/singleton",
    }

    plugin = Drop2BeetsPlugin()

    assert len(plugin.dropbox_handlers) == 2
    assert all(
        isinstance(h, (DefaultDropboxHandler, SingletonDropboxHandler))
        for h in plugin.dropbox_handlers
    )


def test_plugin_ignores_invalid_dropbox_path_keys() -> None:
    config["drop2beets"]["dropbox_paths"] = {
        "default": "/tmp/dropbox/default",
        "invalid": "/tmp/dropbox/invalid",
    }

    plugin = Drop2BeetsPlugin()

    assert len(plugin.dropbox_handlers) == 1


def test_plugin_creates_legacy_dropbox_handler() -> None:
    config["drop2beets"]["dropbox_path"] = "/tmp/dropbox/legacy"

    plugin = Drop2BeetsPlugin()

    assert len(plugin.dropbox_handlers) == 1
    assert isinstance(plugin.dropbox_handlers[0], SingletonDropboxHandler)


# --- Drop2BeetsPlugin.commands ---


def test_plugin_has_dropbox_subcommand() -> None:
    plugin = Drop2BeetsPlugin()
    commands: list[Subcommand] = plugin.commands()

    assert len(commands) > 0
    assert any(isinstance(c, DropboxSubcommand) for c in commands)


def test_plugin_has_install_subcommand() -> None:
    plugin = Drop2BeetsPlugin()
    commands: list[Subcommand] = plugin.commands()

    assert len(commands) > 0
    assert any(isinstance(c, InstallSubcommand) for c in commands)
