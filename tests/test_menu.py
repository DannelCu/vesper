"""Tests for native menu bar (vesper.core.menu + App.menu() + Window integration)."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from vesper import App, MenuItem
from vesper.core.menu import MenuItem as MenuItemDirect
from vesper.core.window import Window, _to_webview_menu
import vesper.core.window as window_mod


# ── MenuItem dataclass ────────────────────────────────────────────────────────


def test_menu_item_stores_label():
    item = MenuItem("File")
    assert item.label == "File"


def test_menu_item_default_action_is_none():
    item = MenuItem("File")
    assert item.action is None


def test_menu_item_default_submenu_is_none():
    item = MenuItem("File")
    assert item.submenu is None


def test_menu_item_with_action():
    fn = lambda: None
    item = MenuItem("Quit", action=fn)
    assert item.action is fn


def test_menu_item_with_submenu():
    child = MenuItem("Open")
    item = MenuItem("File", submenu=[child])
    assert item.submenu == [child]


def test_menu_item_exported_from_package():
    from vesper import MenuItem as MI
    assert MI is MenuItemDirect


# ── _to_webview_menu ──────────────────────────────────────────────────────────


def _mock_webview():
    mock = MagicMock()
    mock.MenuSeparator.return_value = MagicMock(name="Separator")
    mock.MenuAction.return_value = MagicMock(name="Action")
    mock.Menu.return_value = MagicMock(name="Menu")
    return mock


def test_to_webview_menu_leaf_item(monkeypatch):
    mock_wv = _mock_webview()
    monkeypatch.setattr(window_mod, "webview", mock_wv)

    fn = lambda: None
    _to_webview_menu([MenuItem("Open", action=fn)])

    mock_wv.MenuAction.assert_called_once_with("Open", fn)


def test_to_webview_menu_separator(monkeypatch):
    mock_wv = _mock_webview()
    monkeypatch.setattr(window_mod, "webview", mock_wv)

    _to_webview_menu([None])

    mock_wv.MenuSeparator.assert_called_once()


def test_to_webview_menu_submenu(monkeypatch):
    mock_wv = _mock_webview()
    monkeypatch.setattr(window_mod, "webview", mock_wv)

    child = MenuItem("Open", action=lambda: None)
    _to_webview_menu([MenuItem("File", submenu=[child])])

    mock_wv.Menu.assert_called_once()
    call_args = mock_wv.Menu.call_args
    assert call_args[0][0] == "File"


def test_to_webview_menu_item_without_action_uses_noop(monkeypatch):
    mock_wv = _mock_webview()
    monkeypatch.setattr(window_mod, "webview", mock_wv)

    _to_webview_menu([MenuItem("Edit")])

    mock_wv.MenuAction.assert_called_once()
    _, action = mock_wv.MenuAction.call_args[0]
    assert callable(action)


def test_to_webview_menu_returns_list(monkeypatch):
    mock_wv = _mock_webview()
    monkeypatch.setattr(window_mod, "webview", mock_wv)

    result = _to_webview_menu([MenuItem("A", action=lambda: None), None])
    assert len(result) == 2


def test_to_webview_menu_nested_submenu(monkeypatch):
    mock_wv = _mock_webview()
    monkeypatch.setattr(window_mod, "webview", mock_wv)

    grandchild = MenuItem("Item", action=lambda: None)
    child = MenuItem("Sub", submenu=[grandchild])
    _to_webview_menu([MenuItem("Top", submenu=[child])])

    assert mock_wv.Menu.call_count == 2


# ── App.menu() ────────────────────────────────────────────────────────────────


def test_app_menu_stores_items():
    app = App()
    items = [MenuItem("File", submenu=[MenuItem("Quit")])]
    app.menu(items)
    assert app._menu_items is items


def test_app_menu_default_is_none():
    app = App()
    assert app._menu_items is None


# ── App.run() passes menu through Window.create() ─────────────────────────────


def test_app_run_passes_menu_to_window_create(monkeypatch):
    captured = {}

    def fake_create(self, ipc_handler, config, hooks=None, secondary_windows=None,
                    menu=None, splash=None, serve_url=None):
        captured["menu"] = menu

    monkeypatch.setattr(Window, "create", fake_create)
    monkeypatch.setattr(Window, "show", lambda self: None)

    app = App()
    items = [MenuItem("File", submenu=[MenuItem("Quit")])]
    app.menu(items)
    app.run()

    assert captured["menu"] is items


def test_app_run_no_menu_passes_none(monkeypatch):
    captured = {}

    def fake_create(self, ipc_handler, config, hooks=None, secondary_windows=None,
                    menu=None, splash=None, serve_url=None):
        captured["menu"] = menu

    monkeypatch.setattr(Window, "create", fake_create)
    monkeypatch.setattr(Window, "show", lambda self: None)

    App().run()

    assert captured["menu"] is None


# ── Window.create() stores menu and Window.show() passes it to webview.start() ─


def test_window_create_stores_menu(monkeypatch):
    mock_wv = _mock_webview()
    mock_wv.create_window.return_value = MagicMock()
    monkeypatch.setattr(window_mod, "webview", mock_wv)
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    from vesper.core.ipc import IPC
    from vesper.core.registry import CommandRegistry
    from vesper.core.config import WindowConfig

    registry = CommandRegistry()
    ipc = IPC(registry)
    config = WindowConfig(frontend="index.html")
    items = [MenuItem("File", submenu=[])]

    w = Window()
    w.create(ipc, config, menu=items)

    assert w._menu is items


def test_window_show_calls_webview_start_with_menu(monkeypatch):
    mock_wv = _mock_webview()
    mock_wv.create_window.return_value = MagicMock()
    monkeypatch.setattr(window_mod, "webview", mock_wv)
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    from vesper.core.ipc import IPC
    from vesper.core.registry import CommandRegistry
    from vesper.core.config import WindowConfig

    registry = CommandRegistry()
    ipc = IPC(registry)
    config = WindowConfig(frontend="index.html")
    items = [MenuItem("File", action=lambda: None)]

    w = Window()
    w.create(ipc, config, menu=items)
    w.show()

    mock_wv.start.assert_called_once()
    kwargs = mock_wv.start.call_args[1]
    assert "menu" in kwargs


def test_window_show_calls_webview_start_without_menu_kwarg(monkeypatch):
    mock_wv = _mock_webview()
    mock_wv.create_window.return_value = MagicMock()
    monkeypatch.setattr(window_mod, "webview", mock_wv)
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    from vesper.core.ipc import IPC
    from vesper.core.registry import CommandRegistry
    from vesper.core.config import WindowConfig

    registry = CommandRegistry()
    ipc = IPC(registry)
    config = WindowConfig(frontend="index.html")

    w = Window()
    w.create(ipc, config)
    w.show()

    mock_wv.start.assert_called_once_with()
