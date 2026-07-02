"""Tests for deep link detection and dispatch."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from vesper import App
from vesper.core.window import Window


# ── URL detection in argv ─────────────────────────────────────────────────────


def test_custom_scheme_detected(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["app.py", "myapp://path/to/thing"])
    assert App()._deeplink_url == "myapp://path/to/thing"


def test_http_url_not_treated_as_deeplink(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["app.py", "http://example.com"])
    assert App()._deeplink_url is None


def test_https_url_not_treated_as_deeplink(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["app.py", "https://example.com"])
    assert App()._deeplink_url is None


def test_ftp_url_not_treated_as_deeplink(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["app.py", "ftp://files.example.com"])
    assert App()._deeplink_url is None


def test_no_argv_deeplink_is_none(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["app.py"])
    assert App()._deeplink_url is None


def test_first_custom_scheme_wins(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["app.py", "myapp://first", "myapp://second"])
    assert App()._deeplink_url == "myapp://first"


# ── @app.on("deeplink") is a valid hook ──────────────────────────────────────


def test_deeplink_is_valid_hook():
    app = App()

    @app.on("deeplink")
    def handler(url): pass

    assert handler in app._hooks["deeplink"]


def test_invalid_hook_still_raises():
    app = App()
    with pytest.raises(ValueError):
        @app.on("unknown_event")
        def handler(): pass


# ── run() wires deeplink to loaded event ─────────────────────────────────────


def test_run_adds_loaded_hook_when_deeplink_present(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["app.py", "myapp://test"])

    app = App()
    captured = {}

    def fake_create(self, ipc_handler, config, hooks=None, **kwargs):
        captured["hooks"] = hooks

    monkeypatch.setattr(Window, "create", fake_create)
    monkeypatch.setattr(Window, "show", lambda self: None)

    app.run()

    assert "loaded" in captured["hooks"]
    assert len(captured["hooks"]["loaded"]) >= 1


def test_run_does_not_add_loaded_hook_without_deeplink(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["app.py"])

    app = App()
    captured = {}

    def fake_create(self, ipc_handler, config, hooks=None, **kwargs):
        captured["hooks"] = hooks

    monkeypatch.setattr(Window, "create", fake_create)
    monkeypatch.setattr(Window, "show", lambda self: None)

    app.run()

    hooks = captured.get("hooks") or {}
    assert "loaded" not in hooks


# ── Python callback fires when deeplink URL detected ─────────────────────────


def test_deeplink_fires_python_callback(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["app.py", "myapp://open/file"])
    monkeypatch.setattr(Window, "show", lambda self: None)
    monkeypatch.setattr(Window, "emit", lambda self, *a, **kw: None)

    app = App()
    received = []

    @app.on("deeplink")
    def handler(url):
        received.append(url)

    captured = {}

    def fake_create(self, ipc_handler, config, hooks=None, **kwargs):
        captured["hooks"] = hooks

    monkeypatch.setattr(Window, "create", fake_create)
    app.run()

    for fn in (captured.get("hooks") or {}).get("loaded", []):
        fn()

    assert received == ["myapp://open/file"]


def test_deeplink_emits_js_event(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["app.py", "myapp://open/file"])
    monkeypatch.setattr(Window, "show", lambda self: None)

    app = App()
    emitted = []
    monkeypatch.setattr(app.window, "emit", lambda event, payload: emitted.append((event, payload)))

    captured = {}

    def fake_create(self, ipc_handler, config, hooks=None, **kwargs):
        captured["hooks"] = hooks

    monkeypatch.setattr(Window, "create", fake_create)
    app.run()

    for fn in (captured.get("hooks") or {}).get("loaded", []):
        fn()

    assert ("deeplink", {"url": "myapp://open/file"}) in emitted
