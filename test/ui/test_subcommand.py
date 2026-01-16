import subprocess
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from beetsplug.drop2beets.handler.dropbox import BaseDropboxHandler
from beetsplug.drop2beets.handler.fs import BaseFileSystemEventHandler
from beetsplug.drop2beets.ui.subcommand import (
    BaseSubcommand,
    DropboxSubcommand,
    InstallSubcommand,
)


@pytest.fixture
def mock_dropbox_handler(lib):
    fs_handler = Mock(BaseFileSystemEventHandler)
    fs_handler.dropbox_path = "/tmp/dropbox"
    handler = Mock(BaseDropboxHandler)
    handler.get_fs_handler.return_value = fs_handler
    handler.dropbox_path = "/tmp/dropbox"
    return handler


@pytest.fixture
def log_path():
    return Mock(as_filename=Mock(return_value="/tmp/log"))


@pytest.fixture
def mock_register_listener():
    return Mock()


class DummySubcommand(BaseSubcommand):
    def __init__(self):
        super().__init__("dummy", "dummy")

    def _run(self, lib, opts, args):
        pass


# --- BaseSubcommand.__init__ --


def test_base_subcommand_init_has_correct_func():
    cmd = DummySubcommand()

    assert cmd.func == cmd._run


# --- DropboxSubcommand.__init__ ---


@pytest.mark.parametrize(
    "handlers, expected_help",
    [
        (
            [Mock(BaseDropboxHandler, dropbox_path="/tmp/dropbox")],
            "Start watching /tmp/dropbox for files to import automatically",
        ),
        (
            [
                Mock(BaseDropboxHandler, dropbox_path=f"/tmp/dropbox{i}")
                for i in range(2)
            ],
            "Start watching /tmp/dropbox0 and /tmp/dropbox1 "
            "for files to import automatically",
        ),
        (
            [
                Mock(BaseDropboxHandler, dropbox_path=f"/tmp/dropbox{i}")
                for i in range(3)
            ],
            "Start watching /tmp/dropbox0, /tmp/dropbox1 and /tmp/dropbox2 "
            "for files to import automatically",
        ),
    ],
)
def test_dropbox_subcommand_init_has_correct_description(
    handlers, expected_help, log_path, mock_register_listener
):
    cmd = DropboxSubcommand(log_path, handlers, mock_register_listener)

    assert cmd.help == expected_help


# --- DropboxSubcommand._run ---


@patch("beetsplug.drop2beets.ui.subcommand.Observer")
def test_dropbox_subcommand_run(
    mock_observer_class,
    lib,
    log_path,
    mock_dropbox_handler,
    mock_register_listener,
):
    mock_observer = MagicMock()
    mock_observer_class.return_value = mock_observer
    mock_observer.is_alive.side_effect = [True, False]

    cmd = DropboxSubcommand(
        log_path, [mock_dropbox_handler], mock_register_listener
    )
    cmd._run(lib, Mock(), [])

    mock_register_listener.assert_has_calls(
        [
            call("import_begin", mock_dropbox_handler.on_import_begin),
            call(
                "import_task_created",
                mock_dropbox_handler.on_import_task_created,
            ),
            call("item_imported", mock_dropbox_handler.on_item_imported),
        ]
    )

    fs_handler = mock_dropbox_handler.get_fs_handler.return_value
    mock_observer.schedule.assert_called_once_with(
        fs_handler, "/tmp/dropbox", recursive=True
    )
    mock_observer.start.assert_called_once()
    mock_observer.stop.assert_called_once()

    fs_handler.try_to_import.assert_called()


@patch("beetsplug.drop2beets.ui.subcommand.Observer")
def test_dropbox_subcommand_run_no_handlers(
    mock_observer_class, lib, log_path, mock_register_listener
):
    mock_observer = MagicMock()
    mock_observer_class.return_value = mock_observer
    mock_observer.is_alive.return_value = False

    cmd = DropboxSubcommand(log_path, [], mock_register_listener)
    cmd._run(lib, Mock(), [])

    mock_register_listener.assert_not_called()
    mock_observer.schedule.assert_not_called()


# --- InstallSubcommand._run ---


@patch(
    "beetsplug.drop2beets.ui.subcommand.getpass.getuser", return_value="user"
)
@patch("beetsplug.drop2beets.ui.subcommand.subprocess.run")
@patch(
    "beetsplug.drop2beets.ui.subcommand.shutil.which",
    return_value="/usr/bin/beet",
)
@patch("beetsplug.drop2beets.ui.subcommand.Path")
def test_install_subcommand_run(
    mock_path_class, mock_which, mock_subprocess_run, mock_getuser, lib
):
    from beetsplug.drop2beets.ui.subcommand import _SERVICE_TEMPLATE

    mock_systemd_path = MagicMock()
    mock_systemd_path.exists.return_value = True

    mock_home = MagicMock()
    mock_target = mock_home / ".config" / "systemd" / "user"
    mock_service_file = mock_target / "drop2beets.service"

    mock_path_class.side_effect = (
        lambda arg: mock_systemd_path
        if arg == "/run/systemd/system"
        else MagicMock()
    )
    mock_path_class.home.return_value = mock_home

    cmd = InstallSubcommand()
    cmd._run(lib, Mock(), [])

    mock_systemd_path.exists.assert_called_once()
    mock_which.assert_called_once_with("beet")
    mock_target.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_service_file.write_text.assert_called_once_with(
        _SERVICE_TEMPLATE.format(beet_path=mock_which.return_value)
    )
    mock_subprocess_run.assert_has_calls(
        [
            call(["systemctl", "--user", "daemon-reload"], check=True),
            call(["systemctl", "--user", "start", "drop2beets"], check=True),
            call(["systemctl", "--user", "enable", "drop2beets"], check=True),
            call(
                ["loginctl", "enable-linger", mock_getuser.return_value],
                check=True,
            ),
        ]
    )


@patch("builtins.print")
@patch("beetsplug.drop2beets.ui.subcommand.subprocess.run")
@patch(
    "beetsplug.drop2beets.ui.subcommand.shutil.which",
    new=MagicMock(return_value="/usr/bin/beet"),
)
@patch("beetsplug.drop2beets.ui.subcommand.Path")
def test_install_subcommand_handles_subprocess_error(
    mock_path_class, mock_subprocess_run, mock_print, lib
):
    mock_systemd_path = MagicMock()
    mock_systemd_path.exists.return_value = True

    mock_home = MagicMock()

    mock_path_class.side_effect = (
        lambda arg: mock_systemd_path
        if arg == "/run/systemd/system"
        else MagicMock()
    )
    mock_path_class.home.return_value = mock_home

    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        1, ["systemctl", "--user", "daemon-reload"]
    )

    cmd = InstallSubcommand()
    cmd._run(lib, Mock(), [])

    mock_print.assert_any_call(
        "Error: Failed to run 'systemctl --user daemon-reload' (exit code 1)"
    )


@patch("builtins.print")
@patch(
    "beetsplug.drop2beets.ui.subcommand.shutil.which",
    return_value=None,
)
@patch("beetsplug.drop2beets.ui.subcommand.Path")
def test_install_subcommand_run_no_beet(
    mock_path_class, mock_which, mock_print, lib
):
    mock_systemd_path = MagicMock()
    mock_systemd_path.exists.return_value = True

    mock_home = MagicMock()
    mock_target = mock_home / ".config" / "systemd" / "user"

    mock_path_class.side_effect = (
        lambda arg: mock_systemd_path
        if arg == "/run/systemd/system"
        else MagicMock()
    )

    cmd = InstallSubcommand()
    cmd._run(lib, Mock(), [])

    mock_which.assert_called_once_with("beet")
    mock_print.assert_any_call("Error: beet executable not found in PATH")
    mock_target.mkdir.assert_not_called()


@patch("builtins.print")
@patch("beetsplug.drop2beets.ui.subcommand.shutil.which")
@patch("beetsplug.drop2beets.ui.subcommand.Path")
def test_install_subcommand_run_no_systemd(
    mock_path_class, mock_which, mock_print, lib
):
    mock_systemd_path = MagicMock()
    mock_systemd_path.exists.return_value = False

    mock_path_class.side_effect = (
        lambda arg: mock_systemd_path
        if arg == "/run/systemd/system"
        else MagicMock()
    )

    cmd = InstallSubcommand()
    cmd._run(lib, Mock(), [])

    mock_systemd_path.exists.assert_called_once()
    mock_print.assert_any_call("Error: systemd is not running")
    mock_which.assert_not_called()
