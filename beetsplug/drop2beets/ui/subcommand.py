import getpass
import logging
import optparse
import shutil
import subprocess
import textwrap
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from beets.library import Library
from beets.plugins import EventType
from beets.ui import Subcommand
from watchdog.observers import Observer

from beetsplug.drop2beets.handler.dropbox import BaseDropboxHandler

if TYPE_CHECKING:
    from beetsplug.drop2beets.handler.fs import BaseFileSystemEventHandler

_SERVICE_TEMPLATE: Final[str] = """
[Unit]
Description=Drop2Beets

[Service]
Type=simple
ExecStart={beet_path} dropbox
Restart=on-failure

[Install]
WantedBy=default.target
"""

log = logging.getLogger("drop2beets")


class BaseSubcommand(ABC, Subcommand):
    """Base class for drop2beets CLI subcommands."""

    def __init__(self, name: str, description: str) -> None:
        super().__init__(name, help=description)
        self.func = self._run

    @abstractmethod
    def _run(
        self, lib: Library, opts: optparse.Values, args: list[str]
    ) -> None:
        """Executes the subcommand."""


class DropboxSubcommand(BaseSubcommand):
    """Subcommand to start watching dropbox folders for automatic imports."""

    def __init__(
        self,
        log_path: str | None,
        dropbox_handlers: list[BaseDropboxHandler],
        register_listener_func: Callable[[EventType, Callable[..., Any]], None],
    ) -> None:
        self.log_path: str | None = log_path
        self.dropbox_handlers: list[BaseDropboxHandler] = dropbox_handlers
        self.register_listener_func: Callable[
            [EventType, Callable[..., Any]], None
        ] = register_listener_func

        dropbox_paths: list[Path] = [
            handler.dropbox_path for handler in dropbox_handlers
        ]

        if len(dropbox_paths) > 1:
            paths_str = (
                ", ".join(str(p) for p in dropbox_paths[:-1])
                + f" and {dropbox_paths[-1]}"
            )
        else:
            paths_str = str(dropbox_paths[0]) if dropbox_paths else ""

        super().__init__(
            "dropbox",
            f"Start watching {paths_str} for files to import automatically",
        )

    def _run(
        self, lib: Library, opts: optparse.Values, args: list[str]
    ) -> None:
        observer = Observer()

        log.setLevel(logging.INFO)

        logging.basicConfig(
            filename=self.log_path,
            level=logging.WARNING,
            format="%(asctime)s [%(filename)s:%(lineno)s] %(levelname)s %(message)s",
        )

        logging.getLogger("beets").addHandler(logging.getLogger().handlers[0])

        for dropbox_handler in self.dropbox_handlers:
            self.register_listener_func(
                "import_begin", dropbox_handler.on_import_begin
            )

            self.register_listener_func(
                "import_task_created", dropbox_handler.on_import_task_created
            )

            self.register_listener_func(
                "item_imported", dropbox_handler.on_item_imported
            )

            fs_handler: BaseFileSystemEventHandler = (
                dropbox_handler.get_fs_handler(lib)
            )
            observer.schedule(
                fs_handler, str(fs_handler.dropbox_path), recursive=True
            )
            log.info("Started watching %s", fs_handler.dropbox_path)

        observer.start()

        try:
            while observer.is_alive():
                observer.join(1)
                for dropbox_handler in self.dropbox_handlers:
                    dropbox_handler.get_fs_handler(lib).try_to_import()
        finally:
            observer.stop()
            observer.join()


class InstallSubcommand(BaseSubcommand):
    """Subcommand to install drop2beets as a systemd user service."""

    def __init__(self) -> None:
        super().__init__(
            "install_dropbox",
            "Install drop2beets as a user-level systemd service",
        )

    def _run(
        self, lib: Library, opts: optparse.Values, args: list[str]
    ) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(filename)s:%(lineno)s] %(levelname)s %(message)s",
        )

        if not Path("/run/systemd/system").exists():
            print("Error: systemd is not running")
            return

        beet_path = shutil.which("beet")
        if beet_path is None:
            print("Error: beet executable not found in PATH")
            return

        print(f"beet found in {beet_path}")

        target: Path = Path.home() / ".config" / "systemd" / "user"
        target.mkdir(parents=True, exist_ok=True)

        service_file = target / "drop2beets.service"
        service_file.write_text(_SERVICE_TEMPLATE.format(beet_path=beet_path))

        try:
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
            subprocess.run(
                ["systemctl", "--user", "start", "drop2beets"], check=True
            )
            subprocess.run(
                ["systemctl", "--user", "enable", "drop2beets"], check=True
            )
            subprocess.run(
                ["loginctl", "enable-linger", getpass.getuser()], check=True
            )
        except subprocess.CalledProcessError as e:
            print(
                f"Error: Failed to run '{' '.join(e.cmd)}' "
                f"(exit code {e.returncode})"
            )
            return

        print(
            textwrap.dedent("""
            All done!
            Drop2beets is running and will run again when rebooting
            (we enabled systemd's lingering)

            You can run
                systemctl --user start|stop|restart|status drop2beets
            to start/stop/restart/see the service, and
                systemctl --user disable drop2beets
            to remove the service from startup.
        """)
        )
