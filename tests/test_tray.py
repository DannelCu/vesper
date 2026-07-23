"""Tests for system tray support (vesper.core.tray + App.tray())."""
from __future__ import annotations

import logging
import threading
import time
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


# ── The handler against REAL pystray ──────────────────────────────────────────
#
# These deliberately do not mock pystray. A MagicMock accepts any callable and
# never calls it back, which is exactly why a broken handler shipped: pystray
# validates the callback's arity at construction and invokes it with its own
# arguments, and only the real class does either.

pystray = pytest.importorskip("pystray")


def _fired_recorder():
    """An action plus an Event that is set once it has run on its own thread."""
    done = threading.Event()
    record = {}

    def action():
        record["thread"] = threading.current_thread().ident
        done.set()

    return action, done, record


def test_handler_is_accepted_by_real_pystray_and_runs_the_action():
    """
    The regression test for "every tray action was dead".

    pystray counts default parameters in co_argcount, so `lambda _, a=action:`
    counted as two and was invoked as (icon, menu_item) — binding the MenuItem
    over the real action. Constructing and invoking a real MenuItem catches both
    that and the opposite error (too many parameters → ValueError).
    """
    from vesper.core.tray import _handler

    action, done, _ = _fired_recorder()
    item = pystray.MenuItem("Show", _handler(action))

    # Exactly how pystray invokes a clicked item: MenuItem.__call__(icon).
    item(object())

    assert done.wait(2.0), "the action never ran"


def test_handler_binds_each_item_to_its_own_action():
    from vesper.core.tray import _handler

    fired = []
    lock = threading.Lock()
    done = threading.Semaphore(0)

    def record(name):
        def action():
            with lock:
                fired.append(name)
            done.release()
        return action

    items = [
        pystray.MenuItem("One", _handler(record("one"))),
        pystray.MenuItem("Two", _handler(record("two"))),
    ]
    for item in items:
        item(object())

    assert done.acquire(timeout=2.0) and done.acquire(timeout=2.0)
    assert sorted(fired) == ["one", "two"]


# ── Which thread the action runs on ───────────────────────────────────────────
#
# The regression test for "one tray click froze the whole app". pystray's
# AppIndicator and GTK backends dispatch menu items from the GLib main loop that
# is already running — PyWebView's, on the main thread. An action that waits on
# that loop (app.emit is evaluate_js, which blocks until an idle callback runs)
# deadlocks it forever. Vesper therefore runs every action off the caller's
# thread, whatever backend is underneath.


def test_action_does_not_run_on_the_calling_thread():
    from vesper.core.tray import _handler

    action, done, record = _fired_recorder()
    _handler(action)()

    assert done.wait(2.0), "the action never ran"
    assert record["thread"] != threading.current_thread().ident


def test_handler_returns_before_a_slow_action_finishes():
    """
    A tray click must never hold up the dispatching loop — that is what turns a
    blocking action into a frozen UI.
    """
    from vesper.core.tray import _handler

    release = threading.Event()
    started = threading.Event()

    def slow_action():
        started.set()
        release.wait(5.0)

    began = time.monotonic()
    _handler(slow_action)()
    elapsed = time.monotonic() - began

    assert started.wait(2.0)
    assert elapsed < 0.5, f"the handler blocked for {elapsed:.2f}s"
    release.set()


def test_action_that_raises_does_not_reach_the_caller(caplog):
    """pystray would otherwise see the exception and, on some backends, tear the
    icon down — one bad click costing the whole menu."""
    from vesper.core.tray import _handler

    done = threading.Event()

    def boom():
        try:
            raise RuntimeError("action exploded")
        finally:
            done.set()

    with caplog.at_level(logging.ERROR, logger="vesper.tray"):
        _handler(boom)()          # must not raise here
        assert done.wait(2.0)
        # The thread has to unwind past the raise before the log lands.
        for _ in range(200):
            if "Tray menu action raised" in caplog.text:
                break
            time.sleep(0.01)

    assert "Tray menu action raised" in caplog.text


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
