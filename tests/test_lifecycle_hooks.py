from unittest.mock import MagicMock, patch

import pytest

from vesper import App
from vesper.core.window import Window, _HOOK_TO_EVENT
from vesper.core.ipc import IPC
from vesper.core.registry import CommandRegistry
from vesper.core.config import WindowConfig


class _EventMock:
    """Minimal stand-in for a PyWebView event object that supports +=."""
    def __init__(self):
        self.handlers: list = []

    def __iadd__(self, fn):
        self.handlers.append(fn)
        return self


def _make_pywebview_mock(event_names=None):
    """Build a mock PyWebView window with EventMock for each event attribute."""
    event_names = event_names or list(_HOOK_TO_EVENT.values())
    mock_win = MagicMock()
    for attr in event_names:
        setattr(mock_win.events, attr, _EventMock())
    return mock_win


# ── app.on() unit tests ───────────────────────────────────────────────────────


def test_on_stores_handler():
    app = App()

    @app.on("close")
    def handler():
        pass

    assert handler in app._hooks.get("close", [])


def test_on_multiple_handlers_same_event():
    app = App()

    @app.on("close")
    def h1(): pass

    @app.on("close")
    def h2(): pass

    assert len(app._hooks["close"]) == 2
    assert h1 in app._hooks["close"]
    assert h2 in app._hooks["close"]


def test_on_different_events_stored_separately():
    app = App()

    @app.on("close")
    def on_close(): pass

    @app.on("minimize")
    def on_minimize(): pass

    assert "close" in app._hooks
    assert "minimize" in app._hooks
    assert app._hooks["close"] != app._hooks["minimize"]


def test_on_returns_original_function():
    app = App()

    def handler():
        return 42

    result = app.on("close")(handler)
    assert result is handler
    assert result() == 42


def test_on_invalid_event_raises():
    app = App()
    with pytest.raises(ValueError, match="Unknown lifecycle event"):
        @app.on("nonexistent")
        def handler(): pass


def test_on_all_valid_events_accepted():
    app = App()
    for event in ("close", "minimize", "restore", "focus", "blur", "loaded"):
        @app.on(event)
        def handler(): pass


# ── Window.create() hook attachment tests ────────────────────────────────────


def test_window_create_attaches_close_hook(monkeypatch):
    import webview
    mock_win = _make_pywebview_mock()
    monkeypatch.setattr(webview, "create_window", lambda **kw: mock_win)
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    w = Window()
    ipc = IPC(CommandRegistry())
    config = WindowConfig(frontend="frontend/index.html")

    called = []
    w.create(ipc, config, hooks={"close": [lambda: called.append(1)]})

    assert len(mock_win.events.closed.handlers) == 1
    mock_win.events.closed.handlers[0]()
    assert called == [1]


def test_window_create_attaches_minimize_hook(monkeypatch):
    import webview
    mock_win = _make_pywebview_mock()
    monkeypatch.setattr(webview, "create_window", lambda **kw: mock_win)
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    w = Window()
    ipc = IPC(CommandRegistry())
    config = WindowConfig(frontend="frontend/index.html")

    called = []
    w.create(ipc, config, hooks={"minimize": [lambda: called.append("min")]})

    assert len(mock_win.events.minimized.handlers) == 1
    mock_win.events.minimized.handlers[0]()
    assert called == ["min"]


def test_window_create_attaches_multiple_handlers_same_event(monkeypatch):
    import webview
    mock_win = _make_pywebview_mock()
    monkeypatch.setattr(webview, "create_window", lambda **kw: mock_win)
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    w = Window()
    ipc = IPC(CommandRegistry())
    config = WindowConfig(frontend="frontend/index.html")

    results = []
    w.create(
        ipc, config,
        hooks={"close": [lambda: results.append(1), lambda: results.append(2)]},
    )

    assert len(mock_win.events.closed.handlers) == 2
    for fn in mock_win.events.closed.handlers:
        fn()
    assert results == [1, 2]


def test_window_create_no_hooks_does_not_crash(monkeypatch):
    import webview
    mock_win = _make_pywebview_mock()
    monkeypatch.setattr(webview, "create_window", lambda **kw: mock_win)
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    w = Window()
    ipc = IPC(CommandRegistry())
    config = WindowConfig(frontend="frontend/index.html")

    w.create(ipc, config)  # no hooks argument
    w.create(ipc, config, hooks=None)
    w.create(ipc, config, hooks={})


def test_window_create_unknown_hook_silently_skipped(monkeypatch):
    import webview
    mock_win = _make_pywebview_mock()
    monkeypatch.setattr(webview, "create_window", lambda **kw: mock_win)
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    w = Window()
    ipc = IPC(CommandRegistry())
    config = WindowConfig(frontend="frontend/index.html")

    # Unknown key in hooks dict — should not crash
    w.create(ipc, config, hooks={"unknown_event": [lambda: None]})


# ── App.run() passes hooks through ───────────────────────────────────────────


def test_app_run_passes_hooks_to_window_create(monkeypatch):
    captured = {}

    def fake_create(self, ipc_handler, config, hooks=None, **kwargs):
        captured["hooks"] = hooks

    monkeypatch.setattr(Window, "create", fake_create)
    monkeypatch.setattr(Window, "show", lambda self: None)

    app = App()

    @app.on("close")
    def on_close(): pass

    @app.on("minimize")
    def on_minimize(): pass

    app.run()

    assert "close" in captured["hooks"]
    assert "minimize" in captured["hooks"]
    assert on_close in captured["hooks"]["close"]
    assert on_minimize in captured["hooks"]["minimize"]


def test_app_run_no_hooks_passes_none(monkeypatch):
    captured = {}

    def fake_create(self, ipc_handler, config, hooks=None, **kwargs):
        captured["hooks"] = hooks

    monkeypatch.setattr(Window, "create", fake_create)
    monkeypatch.setattr(Window, "show", lambda self: None)

    App().run()

    assert captured["hooks"] is None
