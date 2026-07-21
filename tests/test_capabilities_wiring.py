"""
Tests for the two consumers of capabilities.probe(): the vesper:capabilities command
the frontend queries, and the startup preflight warning.

The detection itself is covered by test_capabilities.py. These tests only check the
wiring, so probe() is mocked throughout.
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from vesper import App
from vesper.core import capabilities


def _report(**overrides) -> dict:
    """A full capability report, available unless a test says otherwise."""
    report = {
        name: {"available": True, "detail": "stub", "fix": None}
        for name in (
            "clipboard_text", "clipboard_image", "notifications", "trash",
            "keep_awake", "tray", "badge", "power_events", "global_shortcuts",
        )
    }
    for name, entry in overrides.items():
        report[name] = entry
    return report


MISSING_TRAY = {
    "available": False,
    "detail": "missing: pystray",
    "fix": 'pip install "vesper[tray]"',
}


# ── vesper:capabilities command ──────────────────────────────────────────────


def test_capabilities_command_is_registered():
    app = App()
    assert "vesper:capabilities" in app.registry._commands


def test_capabilities_command_returns_booleans_only():
    app = App()
    with patch.object(capabilities, "probe", return_value=_report(tray=MISSING_TRAY)):
        resp = app.ipc.handle({"id": "1", "command": "vesper:capabilities", "args": {}})

    assert resp["ok"] is True
    assert resp["result"]["tray"] is False
    assert resp["result"]["clipboard_image"] is True
    assert all(isinstance(v, bool) for v in resp["result"].values())


def test_capabilities_command_does_not_leak_the_fix_strings():
    """Install instructions are for whoever runs the app, not for the web UI."""
    app = App()
    with patch.object(capabilities, "probe", return_value=_report(tray=MISSING_TRAY)):
        resp = app.ipc.handle({"id": "1", "command": "vesper:capabilities", "args": {}})

    serialized = str(resp["result"])
    assert "vesper[tray]" not in serialized
    assert "pystray" not in serialized


def test_capabilities_command_covers_every_capability():
    app = App()
    resp = app.ipc.handle({"id": "1", "command": "vesper:capabilities", "args": {}})
    assert set(resp["result"]) == set(capabilities.probe())


def test_capabilities_command_is_json_safe():
    """It crosses the IPC bridge, so it must survive a round trip."""
    import json

    app = App()
    resp = app.ipc.handle({"id": "1", "command": "vesper:capabilities", "args": {}})
    assert json.loads(json.dumps(resp["result"])) == resp["result"]


# ── SDK surface ──────────────────────────────────────────────────────────────


def test_sdk_exposes_capabilities():
    from importlib.resources import files

    sdk = files("vesper").joinpath("sdk", "vesper.js").read_text(encoding="utf-8")
    assert 'invoke("vesper:capabilities"' in sdk
    assert "capabilities," in sdk, "must be on the exported vesper object"


# ── startup preflight ────────────────────────────────────────────────────────


def _run_app(app):
    with patch.object(app.window, "create"), patch.object(app.window, "show"):
        app.run()


def test_preflight_warns_when_the_tray_backend_is_missing(caplog):
    app = App()
    # A stand-in for what .tray() sets: constructing a real Tray needs pystray,
    # and start()/stop() are called by run().
    app._tray = MagicMock()

    with patch.object(capabilities, "probe", return_value=_report(tray=MISSING_TRAY)):
        with caplog.at_level(logging.WARNING):
            _run_app(app)

    assert "system tray" in caplog.text
    assert "missing: pystray" in caplog.text


def test_preflight_includes_the_fix(caplog):
    app = App()
    app._tray = MagicMock()

    with patch.object(capabilities, "probe", return_value=_report(tray=MISSING_TRAY)):
        with caplog.at_level(logging.WARNING):
            _run_app(app)

    assert 'Fix: pip install "vesper[tray]"' in caplog.text


def test_preflight_is_silent_when_the_backend_is_available(caplog):
    app = App()
    app._tray = MagicMock()

    with patch.object(capabilities, "probe", return_value=_report()):
        with caplog.at_level(logging.WARNING):
            _run_app(app)

    assert caplog.text == ""


def test_preflight_is_silent_when_nothing_is_configured(caplog):
    """An app with no tray must not be warned about one."""
    app = App()

    with patch.object(capabilities, "probe", return_value=_report(tray=MISSING_TRAY)):
        with caplog.at_level(logging.WARNING):
            _run_app(app)

    assert caplog.text == ""


def test_preflight_does_not_probe_when_nothing_is_configured():
    """The common case must not pay for PATH lookups it cannot act on."""
    app = App()

    with patch.object(capabilities, "probe") as probe:
        _run_app(app)

    probe.assert_not_called()


def test_preflight_never_aborts(caplog):
    """It warns; the app still starts. Only .tray() itself is allowed to raise."""
    app = App()
    app._tray = MagicMock()

    with patch.object(capabilities, "probe", return_value=_report(tray=MISSING_TRAY)):
        _run_app(app)   # must not raise


def test_preflight_runs_once_per_run(caplog):
    app = App()
    app._tray = MagicMock()

    with patch.object(capabilities, "probe", return_value=_report(tray=MISSING_TRAY)):
        with caplog.at_level(logging.WARNING):
            _run_app(app)

    assert caplog.text.count("system tray") == 1


def test_preflight_runs_before_the_window_is_created():
    """A warning after the window opens is a warning the user has already missed."""
    order = []

    app = App()
    app._tray = MagicMock()

    with patch.object(capabilities, "probe", return_value=_report(tray=MISSING_TRAY)), \
         patch.object(app, "_preflight", side_effect=lambda: order.append("preflight")), \
         patch.object(app.window, "create", side_effect=lambda **kw: order.append("create")), \
         patch.object(app.window, "show"):
        app.run()

    assert order == ["preflight", "create"]


def test_preflight_is_skipped_when_another_instance_wins():
    """A process that is about to exit has nothing to warn anybody about."""
    app = App()
    app._tray = MagicMock()

    class _LostTheRace:
        def acquire(self):
            return False

    app._single_instance = _LostTheRace()

    with patch.object(capabilities, "probe") as probe:
        app.run()

    probe.assert_not_called()


MISSING_POWER_EVENTS = {
    "available": False,
    "detail": "jeepney not importable",
    "fix": "pip install jeepney",
}


def test_preflight_warns_when_power_events_are_unavailable(caplog):
    app = App(power_events=True)

    with patch.object(
        capabilities, "probe", return_value=_report(power_events=MISSING_POWER_EVENTS)
    ):
        with caplog.at_level(logging.WARNING):
            _run_app(app)

    assert "power events" in caplog.text
    assert "jeepney not importable" in caplog.text
    assert "Fix: pip install jeepney" in caplog.text


def test_preflight_is_silent_when_power_events_are_available(caplog):
    app = App(power_events=True)

    with patch.object(capabilities, "probe", return_value=_report()):
        with caplog.at_level(logging.WARNING):
            _run_app(app)

    assert caplog.text == ""


def test_preflight_ignores_power_events_when_not_opted_in(caplog):
    """An app that never asked for the events must not be told about jeepney."""
    app = App()

    with patch.object(
        capabilities, "probe", return_value=_report(power_events=MISSING_POWER_EVENTS)
    ):
        with caplog.at_level(logging.WARNING):
            _run_app(app)

    assert "power events" not in caplog.text


def test_preflight_warns_about_both_when_both_are_missing(caplog):
    app = App(power_events=True)
    app._tray = MagicMock()

    with patch.object(
        capabilities,
        "probe",
        return_value=_report(tray=MISSING_TRAY, power_events=MISSING_POWER_EVENTS),
    ):
        with caplog.at_level(logging.WARNING):
            _run_app(app)

    assert "system tray" in caplog.text
    assert "power events" in caplog.text
