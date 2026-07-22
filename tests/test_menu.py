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


# The menu classes are resolved once at import (only `Menu` is re-exported at
# PyWebView's top level; MenuAction and MenuSeparator live in webview.menu), so
# these tests patch the resolved names rather than the webview module.
#
# The previous version replaced the whole webview module with a bare MagicMock,
# which happily invents any attribute asked of it — so it kept passing while
# window.py reached for webview.MenuAction, which does not exist. Every menu
# raised AttributeError before the window opened. test_menu_classes_exist below
# is the guard that would have caught it.


class _Recorder:
    """A stand-in that records construction, without inventing anything else."""

    def __init__(self) -> None:
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        return ("built", args)

    @property
    def call_count(self) -> int:
        return len(self.calls)


# The attributes Window.create()/show() touch on the webview module. A list spec,
# not spec=webview: spec=webview walks every attribute of the real module to set
# itself up, and one of them — webview.screens — is a lazy proxy that calls
# initialize(), which raises on a headless Linux box with no GTK/Qt (the CI
# runners). A list spec still rejects any attribute not named here, which is the
# protection that matters, without importing a backend.
_WEBVIEW_USED = ("create_window", "start")


def _mock_webview():
    """A webview stand-in for the Window.create/show tests, which need one."""
    mock = MagicMock(spec=_WEBVIEW_USED)
    mock.create_window.return_value = MagicMock()
    return mock


@pytest.fixture
def menu_classes(monkeypatch):
    """Patch the three resolved classes and hand back the recorders."""
    made = {name: _Recorder() for name in ("Menu", "MenuAction", "MenuSeparator")}
    monkeypatch.setattr(window_mod, "_MENU", made["Menu"])
    monkeypatch.setattr(window_mod, "_MENU_ACTION", made["MenuAction"])
    monkeypatch.setattr(window_mod, "_MENU_SEPARATOR", made["MenuSeparator"])
    return made


# ── the classes actually exist ───────────────────────────────────────────────


@pytest.mark.parametrize("name", ["Menu", "MenuAction", "MenuSeparator"])
def test_menu_classes_exist(name):
    """
    Resolved against the real PyWebView, not a mock.

    This is the test the mocked ones could never be: it fails if PyWebView moves
    or renames a menu class, which is exactly what had already happened.
    """
    resolved = window_mod._menu_class(name)
    assert resolved is not None, f"PyWebView has no menu class {name!r}"
    assert callable(resolved)


def test_a_real_menu_can_be_built():
    """End to end against real PyWebView classes — no patching at all."""
    built = _to_webview_menu([
        MenuItem("File", submenu=[MenuItem("Open", action=lambda: None), None]),
    ])
    assert len(built) == 1


def test_to_webview_menu_leaf_item(menu_classes):
    fn = lambda: None
    _to_webview_menu([MenuItem("Open", action=fn)])

    assert menu_classes["MenuAction"].calls == [("Open", fn)]


def test_to_webview_menu_separator(menu_classes):
    _to_webview_menu([None])

    assert menu_classes["MenuSeparator"].call_count == 1


def test_to_webview_menu_submenu(menu_classes):
    child = MenuItem("Open", action=lambda: None)
    _to_webview_menu([MenuItem("File", submenu=[child])])

    assert menu_classes["Menu"].call_count == 1
    assert menu_classes["Menu"].calls[0][0] == "File"


def test_to_webview_menu_item_without_action_uses_noop(menu_classes):
    _to_webview_menu([MenuItem("Edit")])

    assert menu_classes["MenuAction"].call_count == 1
    _, action = menu_classes["MenuAction"].calls[0]
    assert callable(action)


def test_to_webview_menu_returns_list(menu_classes):
    result = _to_webview_menu([MenuItem("A", action=lambda: None), None])
    assert len(result) == 2


def test_to_webview_menu_nested_submenu(menu_classes):
    grandchild = MenuItem("Item", action=lambda: None)
    child = MenuItem("Sub", submenu=[grandchild])
    _to_webview_menu([MenuItem("Top", submenu=[child])])

    assert menu_classes["Menu"].call_count == 2


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
