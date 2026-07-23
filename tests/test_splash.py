"""Tests for splashscreen (App.splash() + Window.create() integration)."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import vesper.core.window as window_mod
from vesper import App
from vesper.core.window import Window


# ── App.splash() ─────────────────────────────────────────────────────────────


def test_splash_stores_config():
    app = App()
    app.splash("<p>Loading</p>", width=300, height=200)
    assert app._splash_config == {"html": "<p>Loading</p>", "width": 300, "height": 200}


def test_splash_default_dimensions():
    app = App()
    app.splash()
    assert app._splash_config["width"] == 400
    assert app._splash_config["height"] == 300


def test_splash_default_is_none():
    assert App()._splash_config is None


# ── App.run() passes splash through Window.create() ──────────────────────────


def test_run_passes_splash_to_window_create(monkeypatch):
    captured = {}

    def fake_create(self, ipc_handler, config, hooks=None, secondary_windows=None,
                    menu=None, splash=None, serve_url=None):
        captured["splash"] = splash

    monkeypatch.setattr(Window, "create", fake_create)
    monkeypatch.setattr(Window, "show", lambda self: None)

    app = App()
    app.splash("<p>hi</p>", width=320, height=240)
    app.run()

    assert captured["splash"] == {"html": "<p>hi</p>", "width": 320, "height": 240}


def test_run_passes_none_splash_when_not_configured(monkeypatch):
    captured = {}

    def fake_create(self, ipc_handler, config, hooks=None, secondary_windows=None,
                    menu=None, splash=None, serve_url=None):
        captured["splash"] = splash

    monkeypatch.setattr(Window, "create", fake_create)
    monkeypatch.setattr(Window, "show", lambda self: None)

    App().run()

    assert captured["splash"] is None


# ── Window.create() splash window creation ───────────────────────────────────


def _make_webview_mock():
    mock_wv = MagicMock()
    main_win = MagicMock()
    main_win.events = MagicMock()
    splash_win = MagicMock()
    mock_wv.create_window.side_effect = [main_win, splash_win]
    return mock_wv, main_win, splash_win


def test_create_with_splash_creates_two_windows(monkeypatch):
    mock_wv, main_win, splash_win = _make_webview_mock()
    monkeypatch.setattr(window_mod, "webview", mock_wv)
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    from vesper.core.ipc import IPC
    from vesper.core.registry import CommandRegistry
    from vesper.core.config import WindowConfig

    ipc = IPC(CommandRegistry())
    config = WindowConfig(frontend="index.html")

    w = Window()
    w.create(ipc, config, splash={"html": "<p>loading</p>", "width": 400, "height": 300})

    assert mock_wv.create_window.call_count == 2


def test_create_with_splash_main_window_is_hidden(monkeypatch):
    mock_wv, main_win, splash_win = _make_webview_mock()
    monkeypatch.setattr(window_mod, "webview", mock_wv)
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    from vesper.core.ipc import IPC
    from vesper.core.registry import CommandRegistry
    from vesper.core.config import WindowConfig

    ipc = IPC(CommandRegistry())
    config = WindowConfig(frontend="index.html")

    w = Window()
    w.create(ipc, config, splash={"html": "", "width": 400, "height": 300})

    first_call_kwargs = mock_wv.create_window.call_args_list[0][1]
    assert first_call_kwargs.get("hidden") is True


def test_create_without_splash_main_window_not_hidden(monkeypatch):
    mock_wv = MagicMock()
    mock_wv.create_window.return_value = MagicMock()
    monkeypatch.setattr(window_mod, "webview", mock_wv)
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    from vesper.core.ipc import IPC
    from vesper.core.registry import CommandRegistry
    from vesper.core.config import WindowConfig

    ipc = IPC(CommandRegistry())
    config = WindowConfig(frontend="index.html")

    w = Window()
    w.create(ipc, config)

    first_call_kwargs = mock_wv.create_window.call_args_list[0][1]
    assert first_call_kwargs.get("hidden") is False or "hidden" not in first_call_kwargs or first_call_kwargs["hidden"] is False


def test_create_with_splash_registers_loaded_dismiss_handler(monkeypatch):
    mock_wv, main_win, splash_win = _make_webview_mock()
    monkeypatch.setattr(window_mod, "webview", mock_wv)
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    from vesper.core.ipc import IPC
    from vesper.core.registry import CommandRegistry
    from vesper.core.config import WindowConfig

    ipc = IPC(CommandRegistry())
    config = WindowConfig(frontend="index.html")

    # Capture the loaded mock before create() is called so the += assignment
    # does not replace the reference we're inspecting.
    loaded_event = main_win.events.loaded

    w = Window()
    w.create(ipc, config, splash={"html": "", "width": 400, "height": 300})

    loaded_event.__iadd__.assert_called_once()


def test_create_splash_uses_html_kwarg_for_inline_html(monkeypatch):
    mock_wv, main_win, splash_win = _make_webview_mock()
    monkeypatch.setattr(window_mod, "webview", mock_wv)
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    from vesper.core.ipc import IPC
    from vesper.core.registry import CommandRegistry
    from vesper.core.config import WindowConfig

    ipc = IPC(CommandRegistry())
    config = WindowConfig(frontend="index.html")

    w = Window()
    w.create(ipc, config, splash={"html": "<p>hi</p>", "width": 400, "height": 300})

    splash_call_kwargs = mock_wv.create_window.call_args_list[1][1]
    assert "html" in splash_call_kwargs
    assert splash_call_kwargs["html"] == "<p>hi</p>"


def test_create_splash_uses_url_kwarg_for_html_file(monkeypatch):
    mock_wv, main_win, splash_win = _make_webview_mock()
    monkeypatch.setattr(window_mod, "webview", mock_wv)
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    from vesper.core.ipc import IPC
    from vesper.core.registry import CommandRegistry
    from vesper.core.config import WindowConfig

    ipc = IPC(CommandRegistry())
    config = WindowConfig(frontend="index.html")

    w = Window()
    w.create(ipc, config, splash={"html": "splash.html", "width": 400, "height": 300})

    splash_call_kwargs = mock_wv.create_window.call_args_list[1][1]
    assert "url" in splash_call_kwargs
    assert splash_call_kwargs["url"] == "splash.html"


def test_dismiss_handler_destroys_splash_and_shows_main(monkeypatch):
    mock_wv, main_win, splash_win = _make_webview_mock()
    monkeypatch.setattr(window_mod, "webview", mock_wv)
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    from vesper.core.ipc import IPC
    from vesper.core.registry import CommandRegistry
    from vesper.core.config import WindowConfig

    ipc = IPC(CommandRegistry())
    config = WindowConfig(frontend="index.html")

    # Capture before create() reassigns via +=
    loaded_event = main_win.events.loaded

    w = Window()
    w.create(ipc, config, splash={"html": "", "width": 400, "height": 300})

    # Extract and invoke the dismiss handler
    dismiss = loaded_event.__iadd__.call_args[0][0]
    dismiss()

    splash_win.destroy.assert_called_once()
    main_win.show.assert_called_once()


def test_dismiss_shows_main_before_destroying_splash(monkeypatch):
    # Ordering is load-bearing: the main window is created hidden, and destroying
    # the splash first leaves a moment with no mapped window that WebKitGTK does
    # not recover from — the splash vanishes and the main window never appears.
    # The main window must be shown (and un-hidden) BEFORE the splash is torn down.
    mock_wv, main_win, splash_win = _make_webview_mock()
    monkeypatch.setattr(window_mod, "webview", mock_wv)
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    from vesper.core.ipc import IPC
    from vesper.core.registry import CommandRegistry
    from vesper.core.config import WindowConfig

    ipc = IPC(CommandRegistry())
    config = WindowConfig(frontend="index.html")

    loaded_event = main_win.events.loaded

    # A shared parent records the interleaving of calls across both windows.
    order = MagicMock()
    order.attach_mock(main_win.show, "main_show")
    order.attach_mock(splash_win.destroy, "splash_destroy")

    w = Window()
    w.create(ipc, config, splash={"html": "", "width": 400, "height": 300})

    dismiss = loaded_event.__iadd__.call_args[0][0]
    dismiss()

    assert [c[0] for c in order.mock_calls] == ["main_show", "splash_destroy"]
    assert main_win.hidden is False
