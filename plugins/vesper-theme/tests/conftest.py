from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vesper.core.module import Container


@pytest.fixture(autouse=True)
def mock_darkdetect(monkeypatch):
    """Replace darkdetect with a controllable mock."""
    mock_dd = MagicMock()
    mock_dd.theme.return_value = "Light"
    mock_dd.listener = MagicMock()
    monkeypatch.setitem(__import__("sys").modules, "darkdetect", mock_dd)
    return mock_dd


@pytest.fixture(autouse=True)
def clear_container_globals():
    Container.clear_global()
    yield
    Container.clear_global()
