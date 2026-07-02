from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vesper.core.module import Container


@pytest.fixture(autouse=True)
def mock_pynput(monkeypatch):
    """Replace pynput.keyboard with a mock so tests never touch the OS."""
    mock_kb = MagicMock()
    mock_listener = MagicMock()
    mock_kb.GlobalHotKeys.return_value = mock_listener
    monkeypatch.setitem(__import__("sys").modules, "pynput", MagicMock(keyboard=mock_kb))
    monkeypatch.setitem(__import__("sys").modules, "pynput.keyboard", mock_kb)
    return mock_kb, mock_listener


@pytest.fixture(autouse=True)
def clear_container_globals():
    Container.clear_global()
    yield
    Container.clear_global()
