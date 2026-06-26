"""Tests for system tray support (vesper.core.tray + App.tray())."""
from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock, call, patch

import pytest

from vesper import App, TrayMenuItem
from vesper.core.tray import Tray


# ── TrayMenuItem ──────────────────────────────────────────────────────────────


def test_tray_menu_item_stores_label_and_action():
    fn = lambda: None
    item = TrayMenuItem(label="Open", action=fn)
    assert item.label == "Open"
    assert item.action is fn


def test_tray_menu_item_exported_from_package():
    from vesper import TrayMenuItem as TMI
    assert TMI is TrayMenuItem


# ── Tray.start / stop ─────────────────────────────────────────────────────────


def _make_pystray_mock():
    mock_pystray = MagicMock()
    mock_icon_instance = MagicMock()
    mock_pystray.Icon.return_value = mock_icon_instance
    mock_pystray.Menu.SEPARATOR = "SEP"
    return mock_pystray, mock_icon_instance


def test_tray_start_creates_pystray_icon(tmp_path):
    icon_file = tmp_path / "icon.png"
    icon_file.write_bytes(b"")

    mock_pystray, mock_icon_instance = _make_pystray_mock()
    mock_image = MagicMock()
    mock_pil = MagicMock()
    mock_pil.Image.open.return_value = mock_image

    tray = Tray(icon=str(icon_file), menu=[], title="My App")

    with patch.dict("sys.modules", {"pystray": mock_pystray, "PIL": mock_pil, "PIL.Image": mock_pil.Image}):
        tray.start()

    mock_pystray.Icon.assert_called_once()
    mock_icon_instance.run_detached.assert_called_once()


def test_tray_start_passes_title_to_icon(tmp_path):
    icon_file = tmp_path / "icon.png"
    icon_file.write_bytes(b"")

    mock_pystray, mock_icon_instance = _make_pystray_mock()
    mock_pil = MagicMock()

    tray = Tray(icon=str(icon_file), menu=[], title="Settings")

    with patch.dict("sys.modules", {"pystray": mock_pystray, "PIL": mock_pil, "PIL.Image": mock_pil.Image}):
        tray.start()

    _, kwargs = mock_pystray.Icon.call_args
    assert kwargs.get("title") == "Settings" or mock_pystray.Icon.call_args[0][2] == "Settings"


def test_tray_stop_calls_icon_stop(tmp_path):
    icon_file = tmp_path / "icon.png"
    icon_file.write_bytes(b"")

    mock_pystray, mock_icon_instance = _make_pystray_mock()
    mock_pil = MagicMock()

    tray = Tray(icon=str(icon_file), menu=[], title="")

    with patch.dict("sys.modules", {"pystray": mock_pystray, "PIL": mock_pil, "PIL.Image": mock_pil.Image}):
        tray.start()
        tray.stop()

    mock_icon_instance.stop.assert_called_once()


def test_tray_stop_before_start_is_noop():
    tray = Tray(icon="icon.png", menu=[], title="")
    tray.stop()  # must not raise


def test_tray_none_menu_item_becomes_separator(tmp_path):
    icon_file = tmp_path / "icon.png"
    icon_file.write_bytes(b"")

    mock_pystray, mock_icon_instance = _make_pystray_mock()
    mock_pystray.Menu.SEPARATOR = "<<sep>>"
    mock_pil = MagicMock()

    menu = [TrayMenuItem("Open", lambda: None), None, TrayMenuItem("Quit", lambda: None)]
    tray = Tray(icon=str(icon_file), menu=menu, title="")

    captured_items = []

    def fake_menu(*items):
        captured_items.extend(items)
        return MagicMock()

    mock_pystray.Menu.side_effect = fake_menu

    with patch.dict("sys.modules", {"pystray": mock_pystray, "PIL": mock_pil, "PIL.Image": mock_pil.Image}):
        tray.start()

    assert "<<sep>>" in captured_items


def test_tray_start_raises_if_pystray_missing():
    import sys

    tray = Tray(icon="icon.png", menu=[], title="")

    with patch.dict("sys.modules", {"pystray": None, "PIL": None}):
        with pytest.raises(RuntimeError, match="pystray"):
            tray.start()


# ── App.tray() integration ────────────────────────────────────────────────────


def test_app_tray_stores_tray_instance():
    app = App()
    assert app._tray is None

    mock_pystray = MagicMock()
    mock_pil = MagicMock()

    with patch.dict("sys.modules", {"pystray": mock_pystray, "PIL": mock_pil, "PIL.Image": mock_pil.Image}):
        app.tray("icon.png", [TrayMenuItem("Quit", lambda: None)])

    assert app._tray is not None


def test_app_run_starts_and_stops_tray(tmp_path):
    html = tmp_path / "index.html"
    html.write_text("<html></html>")

    app = App(frontend=str(html))

    mock_tray = MagicMock()
    app._tray = mock_tray

    import webview
    with patch.object(webview, "create_window", return_value=MagicMock()), \
         patch.object(webview, "start"):
        app.run()

    mock_tray.start.assert_called_once()
    mock_tray.stop.assert_called_once()


def test_app_run_stops_tray_even_if_webview_raises(tmp_path):
    html = tmp_path / "index.html"
    html.write_text("<html></html>")

    app = App(frontend=str(html))

    mock_tray = MagicMock()
    app._tray = mock_tray

    import webview
    with patch.object(webview, "create_window", return_value=MagicMock()), \
         patch.object(webview, "start", side_effect=RuntimeError("crash")):
        with pytest.raises(RuntimeError):
            app.run()

    mock_tray.stop.assert_called_once()


def test_app_run_without_tray_works(tmp_path):
    html = tmp_path / "index.html"
    html.write_text("<html></html>")

    app = App(frontend=str(html))
    assert app._tray is None

    import webview
    with patch.object(webview, "create_window", return_value=MagicMock()), \
         patch.object(webview, "start"):
        app.run()  # must not raise
