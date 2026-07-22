from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

from vesper.core.module import Container


@pytest.fixture(autouse=True)
def mock_desktop_notifier(monkeypatch):
    """
    Replace desktop_notifier with a controllable mock.

    Per the coverage philosophy: CI verifies the call the plugin builds, not
    that a bubble appears — that is a documented manual test.
    """
    mock_module = MagicMock()
    notifier = MagicMock()
    notifier.send = AsyncMock(return_value="platform-id")
    mock_module.DesktopNotifier.return_value = notifier

    # Button/Icon become recording constructors so tests can inspect kwargs.
    mock_module.Button = MagicMock(side_effect=lambda **kw: {"button": kw})
    mock_module.Icon = MagicMock(side_effect=lambda **kw: {"icon": kw})
    mock_module.DEFAULT_SOUND = "DEFAULT_SOUND"

    monkeypatch.setitem(sys.modules, "desktop_notifier", mock_module)
    return mock_module


@pytest.fixture(autouse=True)
def clear_container_globals():
    Container.clear_global()
    yield
    Container.clear_global()
