"""Tests for screen info built-in (vesper:screen:list)."""
from __future__ import annotations

from unittest.mock import MagicMock

import vesper.core.window as window_mod
from vesper import App
from vesper.core.window import Window


def _mock_screen(width=1920, height=1080, x=0, y=0):
    s = MagicMock()
    s.width = width
    s.height = height
    s.x = x
    s.y = y
    return s


# ── Window.list_screens() ─────────────────────────────────────────────────────


def test_list_screens_single_monitor(monkeypatch):
    monkeypatch.setattr(window_mod.webview, "screens", [_mock_screen(1920, 1080)])
    result = Window().list_screens()
    assert result == [{"width": 1920, "height": 1080, "x": 0, "y": 0}]


def test_list_screens_multiple_monitors(monkeypatch):
    screens = [_mock_screen(1920, 1080, 0, 0), _mock_screen(2560, 1440, 1920, 0)]
    monkeypatch.setattr(window_mod.webview, "screens", screens)
    result = Window().list_screens()
    assert len(result) == 2
    assert result[1]["width"] == 2560
    assert result[1]["x"] == 1920


def test_list_screens_missing_x_y_defaults_to_zero(monkeypatch):
    s = MagicMock(spec=["width", "height"])
    s.width = 1280
    s.height = 800
    monkeypatch.setattr(window_mod.webview, "screens", [s])
    result = Window().list_screens()
    assert result[0]["x"] == 0
    assert result[0]["y"] == 0


def test_list_screens_empty(monkeypatch):
    monkeypatch.setattr(window_mod.webview, "screens", [])
    assert Window().list_screens() == []


# ── IPC registration ─────────────────────────────────────────────────────────


def test_vesper_screen_list_registered():
    assert "vesper:screen:list" in App().registry._commands


def test_vesper_screen_list_via_ipc(monkeypatch):
    monkeypatch.setattr(window_mod.webview, "screens", [_mock_screen(2560, 1440)])
    app = App()
    resp = app.ipc.handle({"id": "1", "command": "vesper:screen:list", "args": {}})
    assert resp["ok"] is True
    assert resp["result"][0]["width"] == 2560
