"""Tests for app quit (App.quit(), vesper:app:quit IPC command)."""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from vesper import App
from vesper.core import app as app_module
from vesper.core.window import Window


def _wait_until(predicate, timeout: float = 2.0) -> bool:
    """Poll until predicate holds — App.quit() destroys the window off-thread."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return False


@pytest.fixture(autouse=True)
def instant_quit(monkeypatch):
    """Drop the quit delay so tests do not pay for it."""
    monkeypatch.setattr(app_module, "_QUIT_DELAY_SECONDS", 0)


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
    assert _wait_until(lambda: app.window.window.destroy.call_count == 1)


def test_app_quit_is_deferred_not_immediate():
    """
    The window must outlive the call itself.

    PyWebView delivers a command's return value through evaluate_js on a non-daemon
    thread. Destroying the WebView before that reply lands strands the thread and the
    process hangs at shutdown, so a "Quit" button would close the window and leave the
    process alive.
    """
    app = App()
    app.window.window = MagicMock()

    monkeypatched_delay = 5.0
    app_module._QUIT_DELAY_SECONDS = monkeypatched_delay
    try:
        app.quit()
        # Still intact right after the call returns.
        app.window.window.destroy.assert_not_called()
    finally:
        app_module._QUIT_DELAY_SECONDS = 0


def test_app_quit_does_not_block_the_caller():
    app = App()
    app.window.window = MagicMock()

    app_module._QUIT_DELAY_SECONDS = 5.0
    try:
        start = time.monotonic()
        app.quit()
        assert time.monotonic() - start < 1.0
    finally:
        app_module._QUIT_DELAY_SECONDS = 0


# ── IPC registration ─────────────────────────────────────────────────────────


def test_vesper_app_quit_registered():
    assert "vesper:app:quit" in App().registry._commands


def test_vesper_app_quit_via_ipc():
    app = App()
    app.window.window = MagicMock()
    resp = app.ipc.handle({"id": "1", "command": "vesper:app:quit", "args": {}})
    assert resp["ok"] is True
    assert _wait_until(lambda: app.window.window.destroy.call_count == 1)


def test_vesper_app_quit_replies_before_window_is_destroyed():
    """The IPC response must be produced while the WebView can still receive it."""
    app = App()
    app.window.window = MagicMock()

    app_module._QUIT_DELAY_SECONDS = 5.0
    try:
        resp = app.ipc.handle({"id": "1", "command": "vesper:app:quit", "args": {}})
        assert resp["ok"] is True
        app.window.window.destroy.assert_not_called()
    finally:
        app_module._QUIT_DELAY_SECONDS = 0


def test_quit_from_inside_a_command_still_returns_its_result():
    """The pattern that deadlocked: a command that quits and returns a value."""
    app = App()
    app.window.window = MagicMock()

    @app.command("finish")
    def finish() -> str:
        app.quit()
        return "done"

    resp = app.ipc.handle({"id": "1", "command": "finish", "args": {}})
    assert resp["ok"] is True
    assert resp["result"] == "done"
    assert _wait_until(lambda: app.window.window.destroy.call_count == 1)
