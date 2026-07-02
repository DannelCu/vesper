"""Tests for vesper-theme plugin."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import threading

import pytest

from vesper import App
from vesper_theme import ThemePlugin
from vesper_theme.plugin import ThemePlugin as ThemePluginDirect


# ── IPC registration ─────────────────────────────────────────────────────────


def test_vesper_theme_get_registered():
    app = App(plugins=[ThemePlugin(watch=False)])
    assert "vesper:theme:get" in app.registry._commands


# ── vesper:theme:get ──────────────────────────────────────────────────────────


def test_get_returns_light_theme(mock_darkdetect):
    mock_darkdetect.theme.return_value = "Light"
    app = App(plugins=[ThemePlugin(watch=False)])
    resp = app.ipc.handle({"id": "1", "command": "vesper:theme:get", "args": {}})
    assert resp["ok"] is True
    assert resp["result"]["theme"] == "Light"
    assert resp["result"]["is_dark"] is False


def test_get_returns_dark_theme(mock_darkdetect):
    mock_darkdetect.theme.return_value = "Dark"
    app = App(plugins=[ThemePlugin(watch=False)])
    resp = app.ipc.handle({"id": "1", "command": "vesper:theme:get", "args": {}})
    assert resp["ok"] is True
    assert resp["result"]["theme"] == "Dark"
    assert resp["result"]["is_dark"] is True


def test_get_defaults_to_light_when_darkdetect_returns_none(mock_darkdetect):
    mock_darkdetect.theme.return_value = None
    app = App(plugins=[ThemePlugin(watch=False)])
    resp = app.ipc.handle({"id": "1", "command": "vesper:theme:get", "args": {}})
    assert resp["ok"] is True
    assert resp["result"]["theme"] == "Light"


# ── watch=True starts listener thread ────────────────────────────────────────


def test_watch_true_starts_background_thread(mock_darkdetect):
    threads_before = {t.ident for t in threading.enumerate()}
    plugin = ThemePlugin(watch=True)
    app = App(plugins=[plugin])
    # Give the thread a moment to start
    import time; time.sleep(0.05)
    threads_after = {t.ident for t in threading.enumerate()}
    # A new daemon thread should have started
    new_threads = threads_after - threads_before
    # We can't assert the exact thread without hooking into it, so just check
    # that darkdetect.listener was called
    mock_darkdetect.listener.assert_called_once()


def test_watch_false_does_not_call_listener(mock_darkdetect):
    app = App(plugins=[ThemePlugin(watch=False)])
    mock_darkdetect.listener.assert_not_called()


# ── theme change callback emits JS event ─────────────────────────────────────


def test_theme_change_emits_js_event(mock_darkdetect):
    plugin = ThemePlugin(watch=True)
    app = App(plugins=[plugin])
    emitted = []
    app.window.emit = lambda event, payload: emitted.append((event, payload))

    # Extract and call the on_change callback passed to darkdetect.listener
    on_change = mock_darkdetect.listener.call_args[0][0]
    on_change("Dark")

    assert ("theme:change", {"theme": "Dark", "is_dark": True}) in emitted


def test_theme_change_light_is_not_dark(mock_darkdetect):
    plugin = ThemePlugin(watch=True)
    app = App(plugins=[plugin])
    emitted = []
    app.window.emit = lambda event, payload: emitted.append((event, payload))

    on_change = mock_darkdetect.listener.call_args[0][0]
    on_change("Light")

    assert ("theme:change", {"theme": "Light", "is_dark": False}) in emitted


# ── Plugin export ─────────────────────────────────────────────────────────────


def test_plugin_alias():
    from vesper_theme import Plugin
    assert Plugin is ThemePluginDirect
