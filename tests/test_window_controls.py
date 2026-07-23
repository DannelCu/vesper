"""Tests for window control built-ins (minimize/maximize/restore/fullscreen/resize/move)."""
from __future__ import annotations

from unittest.mock import MagicMock

from vesper import App
from vesper.core.window import Window


def _app_with_mock_win():
    app = App()
    app.window.window = MagicMock()
    return app


# ── Window method delegation ─────────────────────────────────────────────────


def test_window_minimize_calls_pywebview():
    w = Window()
    w.window = MagicMock()
    w.minimize()
    w.window.minimize.assert_called_once()


def test_window_maximize_calls_pywebview():
    w = Window()
    w.window = MagicMock()
    w.maximize()
    w.window.maximize.assert_called_once()


def test_window_restore_calls_pywebview():
    w = Window()
    w.window = MagicMock()
    w.restore()
    w.window.restore.assert_called_once()


def test_window_hide_calls_pywebview():
    w = Window()
    w.window = MagicMock()
    w.hide()
    w.window.hide.assert_called_once()


def test_window_show_window_calls_pywebview_show():
    # show_window() toggles visibility via the backend's show(); it must not be
    # confused with Window.show(), which starts the GUI event loop.
    w = Window()
    w.window = MagicMock()
    w.show_window()
    w.window.show.assert_called_once()


def test_window_show_window_clears_the_hidden_flag():
    # PyWebView's GTK show() re-hides a window whose `hidden` flag is still set,
    # because the GTK main level reads 0 under Gtk.Application.run().
    w = Window()
    w.window = MagicMock()
    w.window.hidden = True
    w.show_window()
    assert w.window.hidden is False
    w.window.show.assert_called_once()


def test_window_toggle_fullscreen_calls_pywebview():
    w = Window()
    w.window = MagicMock()
    w.toggle_fullscreen()
    w.window.toggle_fullscreen.assert_called_once()


def test_window_resize_calls_pywebview_with_dimensions():
    w = Window()
    w.window = MagicMock()
    w.resize(1024, 768)
    w.window.resize.assert_called_once_with(1024, 768)


def test_window_move_calls_pywebview_with_coords():
    w = Window()
    w.window = MagicMock()
    w.move(100, 200)
    w.window.move.assert_called_once_with(100, 200)


def test_window_methods_are_noop_before_create():
    w = Window()
    # None of these should raise when window is None
    w.minimize()
    w.maximize()
    w.restore()
    w.hide()
    w.show_window()
    w.toggle_fullscreen()
    w.resize(800, 600)
    w.move(0, 0)


# ── IPC registration ─────────────────────────────────────────────────────────


def test_vesper_window_minimize_registered():
    assert "vesper:window:minimize" in App().registry._commands


def test_vesper_window_maximize_registered():
    assert "vesper:window:maximize" in App().registry._commands


def test_vesper_window_restore_registered():
    assert "vesper:window:restore" in App().registry._commands


def test_vesper_window_hide_registered():
    assert "vesper:window:hide" in App().registry._commands


def test_vesper_window_show_registered():
    assert "vesper:window:show" in App().registry._commands


def test_vesper_window_fullscreen_registered():
    assert "vesper:window:fullscreen" in App().registry._commands


def test_vesper_window_resize_registered():
    assert "vesper:window:resize" in App().registry._commands


def test_vesper_window_move_registered():
    assert "vesper:window:move" in App().registry._commands


# ── IPC invocation ───────────────────────────────────────────────────────────


def test_minimize_via_ipc():
    app = _app_with_mock_win()
    resp = app.ipc.handle({"id": "1", "command": "vesper:window:minimize", "args": {}})
    assert resp["ok"] is True
    app.window.window.minimize.assert_called_once()


def test_maximize_via_ipc():
    app = _app_with_mock_win()
    resp = app.ipc.handle({"id": "1", "command": "vesper:window:maximize", "args": {}})
    assert resp["ok"] is True
    app.window.window.maximize.assert_called_once()


def test_restore_via_ipc():
    app = _app_with_mock_win()
    resp = app.ipc.handle({"id": "1", "command": "vesper:window:restore", "args": {}})
    assert resp["ok"] is True
    app.window.window.restore.assert_called_once()


def test_hide_via_ipc():
    app = _app_with_mock_win()
    resp = app.ipc.handle({"id": "1", "command": "vesper:window:hide", "args": {}})
    assert resp["ok"] is True
    app.window.window.hide.assert_called_once()


def test_show_via_ipc():
    app = _app_with_mock_win()
    resp = app.ipc.handle({"id": "1", "command": "vesper:window:show", "args": {}})
    assert resp["ok"] is True
    app.window.window.show.assert_called_once()


def test_fullscreen_via_ipc():
    app = _app_with_mock_win()
    resp = app.ipc.handle({"id": "1", "command": "vesper:window:fullscreen", "args": {}})
    assert resp["ok"] is True
    app.window.window.toggle_fullscreen.assert_called_once()


def test_resize_via_ipc():
    app = _app_with_mock_win()
    resp = app.ipc.handle({"id": "1", "command": "vesper:window:resize", "args": {"width": 1280, "height": 720}})
    assert resp["ok"] is True
    app.window.window.resize.assert_called_once_with(1280, 720)


def test_move_via_ipc():
    app = _app_with_mock_win()
    resp = app.ipc.handle({"id": "1", "command": "vesper:window:move", "args": {"x": 50, "y": 100}})
    assert resp["ok"] is True
    app.window.window.move.assert_called_once_with(50, 100)
