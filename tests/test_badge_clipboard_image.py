"""Tests for taskbar/dock badges and clipboard image support."""
from __future__ import annotations

import base64
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from vesper import App
from vesper.core import badge, clipboard

# A 1x1 PNG — small enough to inline, real enough to round-trip.
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
PNG_DATA_URL = "data:image/png;base64," + base64.b64encode(PNG_BYTES).decode()


@pytest.fixture(autouse=True)
def reset_badge_warnings():
    badge._warned.clear()
    yield
    badge._warned.clear()


# ── clamping ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("value,expected", [
    (0.5, 0.5), (0, 0.0), (1, 1.0),
    (-0.5, 0.0), (1.5, 1.0),          # a caller computing i/total can overshoot
    ("nonsense", 0.0), (None, 0.0),
])
def test_progress_fraction_is_clamped(value, expected):
    assert badge._clamp(value) == expected


# ── Linux ────────────────────────────────────────────────────────────────────


def test_linux_progress_sends_a_launcher_update(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "linux")
    with patch.object(badge, "_linux_launcher_update", return_value=True) as update:
        assert badge.set_progress(0.42) is True

    assert update.call_args[0][0] == {"progress": 0.42, "progress-visible": True}


def test_linux_clear_progress_hides_it(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "linux")
    with patch.object(badge, "_linux_launcher_update", return_value=True) as update:
        badge.clear_progress()

    assert update.call_args[0][0] == {"progress-visible": False}


def test_linux_badge_sets_a_count(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "linux")
    with patch.object(badge, "_linux_launcher_update", return_value=True) as update:
        badge.set_badge(7)

    assert update.call_args[0][0] == {"count": 7, "count-visible": True}


def test_missing_dbus_degrades_to_a_noop(monkeypatch):
    """Most desktops no longer implement LauncherEntry; that must be a no-op."""
    monkeypatch.setattr(badge.sys, "platform", "linux")
    with patch.dict("sys.modules", {"dbus": None}):
        assert badge.set_progress(0.5) is False


# ── macOS ────────────────────────────────────────────────────────────────────


def test_macos_badge_uses_the_dock_tile(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "darwin")
    with patch.object(badge, "_macos_set_badge", return_value=True) as set_badge:
        assert badge.set_badge(3) is True
    set_badge.assert_called_once_with("3")


def test_macos_progress_shows_a_percentage(monkeypatch):
    """There is no dock progress bar, so the percentage goes in the badge."""
    monkeypatch.setattr(badge.sys, "platform", "darwin")
    with patch.object(badge, "_macos_set_badge", return_value=True) as set_badge:
        badge.set_progress(0.42)
    set_badge.assert_called_once_with("42%")


def test_macos_without_pyobjc_degrades(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "darwin")
    with patch.dict("sys.modules", {"AppKit": None}):
        assert badge.set_badge(1) is False


# ── Windows ──────────────────────────────────────────────────────────────────


def test_windows_progress_uses_itaskbarlist3(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "win32")
    taskbar = MagicMock()

    with patch.object(badge, "_windows_taskbar", return_value=taskbar), \
         patch.object(badge, "_windows_hwnd", return_value=1234):
        assert badge.set_progress(0.5) is True

    taskbar.SetProgressValue.assert_called_once_with(1234, 50, 100)


def test_windows_without_comtypes_degrades(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "win32")
    with patch.object(badge, "_windows_taskbar", return_value=None):
        assert badge.set_progress(0.5) is False


def test_windows_badge_is_unsupported(monkeypatch):
    """Documented as unimplemented rather than silently pretending to work."""
    monkeypatch.setattr(badge.sys, "platform", "win32")
    assert badge.set_badge(3) is False


# ── shared behaviour ─────────────────────────────────────────────────────────


def test_zero_count_clears_the_badge(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "linux")
    with patch.object(badge, "_linux_launcher_update", return_value=True) as update:
        badge.set_badge(0)

    assert update.call_args[0][0] == {"count-visible": False}


def test_negative_count_is_treated_as_zero(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "linux")
    with patch.object(badge, "_linux_launcher_update", return_value=True) as update:
        badge.set_badge(-5)
    assert update.call_args[0][0] == {"count-visible": False}


def test_a_failing_backend_never_raises(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "linux")
    with patch.object(badge, "_linux_launcher_update", side_effect=RuntimeError("bus down")):
        assert badge.set_progress(0.5) is False
        assert badge.clear_progress() is False
        assert badge.set_badge(2) is False


def test_unavailability_is_logged_once(monkeypatch, caplog):
    """A progress bar updated in a loop must not flood the log."""
    monkeypatch.setattr(badge.sys, "platform", "linux")
    with patch.dict("sys.modules", {"dbus": None}):
        for _ in range(10):
            badge.set_progress(0.5)

    assert len(badge._warned) == 1


# ── clipboard images ─────────────────────────────────────────────────────────


def test_read_image_returns_a_data_url(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    with patch.object(clipboard, "_linux_read_image", return_value=PNG_BYTES):
        result = clipboard.read_image()

    assert result.startswith("data:image/png;base64,")
    assert base64.b64decode(result.split(",", 1)[1]) == PNG_BYTES


def test_read_image_without_an_image_returns_none(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    with patch.object(clipboard, "_linux_read_image", return_value=None):
        assert clipboard.read_image() is None


def test_read_image_survives_a_missing_tool(monkeypatch, caplog):
    """
    A missing helper is a configuration fact, not an error.

    Apps poll the clipboard, so logging a traceback per call would bury the log.
    """
    import logging

    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    with caplog.at_level(logging.DEBUG, logger="vesper.clipboard"), \
         patch.object(clipboard, "_linux_read_image", side_effect=FileNotFoundError("no xclip")):
        assert clipboard.read_image() is None

    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_read_image_reports_a_real_failure(monkeypatch, caplog):
    """An unexpected failure still surfaces, unlike a missing binary."""
    import logging

    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    with caplog.at_level(logging.ERROR, logger="vesper.clipboard"), \
         patch.object(clipboard, "_linux_read_image", side_effect=RuntimeError("bus error")):
        assert clipboard.read_image() is None

    assert any(r.levelno >= logging.ERROR for r in caplog.records)


def test_write_image_accepts_a_data_url(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    with patch.object(clipboard, "_linux_write_image", return_value=True) as writer:
        assert clipboard.write_image(PNG_DATA_URL) is True

    writer.assert_called_once_with(PNG_BYTES)


def test_write_image_accepts_bare_base64(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    with patch.object(clipboard, "_linux_write_image", return_value=True) as writer:
        assert clipboard.write_image(base64.b64encode(PNG_BYTES).decode()) is True

    writer.assert_called_once_with(PNG_BYTES)


@pytest.mark.parametrize("bad", ["", "not base64!!", "data:image/png;base64,@@@"])
def test_write_image_rejects_invalid_data(bad):
    assert clipboard.write_image(bad) is False


def test_round_trip_through_the_data_url_format(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    stored: dict = {}

    with patch.object(clipboard, "_linux_write_image", side_effect=lambda raw: stored.update(raw=raw) or True):
        clipboard.write_image(PNG_DATA_URL)

    with patch.object(clipboard, "_linux_read_image", return_value=stored["raw"]):
        assert clipboard.read_image() == PNG_DATA_URL


def test_linux_image_uses_the_png_mime_type(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    with patch.object(clipboard.subprocess, "run",
                      return_value=subprocess.CompletedProcess([], 0)) as run:
        clipboard._linux_write_image(PNG_BYTES)

    argv = run.call_args[0][0]
    assert argv[:2] == ["xclip", "-selection"]
    assert "image/png" in argv


def test_windows_image_uses_sta_mode(monkeypatch):
    """The Windows clipboard API requires a single-threaded apartment."""
    monkeypatch.setattr(clipboard.sys, "platform", "win32")
    with patch.object(clipboard.subprocess, "run",
                      return_value=subprocess.CompletedProcess([], 0)) as run:
        clipboard._windows_write_image(PNG_BYTES)

    assert "-STA" in run.call_args[0][0]


# ── IPC registration ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("command", [
    "vesper:badge:set_progress",
    "vesper:badge:clear_progress",
    "vesper:badge:set_badge",
    "vesper:badge:clear_badge",
    "vesper:clipboard:read_image",
    "vesper:clipboard:write_image",
])
def test_command_is_registered(command):
    assert command in App().registry._commands


def test_progress_over_ipc(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "linux")
    app = App()

    with patch.object(badge, "_linux_launcher_update", return_value=True):
        resp = app.ipc.handle({
            "id": "1", "command": "vesper:badge:set_progress", "args": {"fraction": 0.5},
        })

    assert resp["ok"] is True
    assert resp["result"] is True
