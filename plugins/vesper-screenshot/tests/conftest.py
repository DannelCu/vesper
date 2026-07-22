from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from vesper.core.module import Container


class FakeShot:
    rgb = b"\x00" * 12
    size = (2, 2)


@pytest.fixture(autouse=True)
def mock_mss(monkeypatch):
    """Replace mss with a controllable mock (no display in CI)."""
    mock_module = MagicMock()
    sct = MagicMock()
    sct.monitors = [
        {"left": 0, "top": 0, "width": 3200, "height": 1080},   # virtual
        {"left": 0, "top": 0, "width": 1920, "height": 1080},
        {"left": 1920, "top": 0, "width": 1280, "height": 1024},
    ]
    sct.grab.return_value = FakeShot()
    mock_module.mss.return_value.__enter__ = MagicMock(return_value=sct)
    mock_module.mss.return_value.__exit__ = MagicMock(return_value=False)
    mock_module._sct = sct

    tools = MagicMock()
    tools.to_png.return_value = b"\x89PNG fake bytes"
    mock_module.tools = tools

    monkeypatch.setitem(sys.modules, "mss", mock_module)
    monkeypatch.setitem(sys.modules, "mss.tools", tools)
    return mock_module


@pytest.fixture(autouse=True)
def not_wayland(monkeypatch):
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)


@pytest.fixture(autouse=True)
def clear_container_globals():
    Container.clear_global()
    yield
    Container.clear_global()
