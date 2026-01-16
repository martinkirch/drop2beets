from pathlib import Path
from unittest.mock import Mock

import pytest
from beets import config
from beets.library import Library


@pytest.fixture(autouse=True)
def reset_config():
    config.clear()
    config.read(False)
    yield
    config.clear()
    config.read(False)


@pytest.fixture
def lib() -> Library:
    return Mock(Library)


@pytest.fixture
def dropbox_dir(tmp_path) -> Path:
    d = tmp_path / "dropbox"
    d.mkdir()
    return d
