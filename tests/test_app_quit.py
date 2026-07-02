"""Tests for app quit (App.quit(), vesper:app:quit IPC command)."""
from __future__ import annotations

from unittest.mock import MagicMock

from vesper import App
from vesper.core.window import Window


# ── Window.quit() ─────────────────────────────────────────────────────────────


def test_window_quit_destroys_pywebview_window():
    w = Window()
    w.window = MagicMock()
    w.quit()
    w.window.destroy.assert_called_once()


def test_window_quit_is_noop_before_create():
    w = Window()
    w.quit()  # should not raise


# ── App.quit() ────────────────────────────────────────────────────────────────


def test_app_quit_delegates_to_window():
    app = App()
    app.window.window = MagicMock()
    app.quit()
    app.window.window.destroy.assert_called_once()


# ── IPC registration ─────────────────────────────────────────────────────────


def test_vesper_app_quit_registered():
    assert "vesper:app:quit" in App().registry._commands


def test_vesper_app_quit_via_ipc():
    app = App()
    app.window.window = MagicMock()
    resp = app.ipc.handle({"id": "1", "command": "vesper:app:quit", "args": {}})
    assert resp["ok"] is True
    app.window.window.destroy.assert_called_once()
