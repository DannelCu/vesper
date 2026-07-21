"""Tests for native notifications (vesper.core.notify + App.notify())."""
from __future__ import annotations

import threading
from unittest.mock import MagicMock, call, patch

import pytest

from vesper import App
from vesper.core import notify as notify_mod


# ── Platform dispatch ─────────────────────────────────────────────────────────


def _run_send(monkeypatch, platform, *args):
    """
    Call send() and run the thread body inline.

    send() wraps the platform backend so a missing notify-send is logged instead of
    dumping a traceback from the thread, so these assert the backend actually invoked
    rather than the Thread kwargs — which are an implementation detail.
    """
    monkeypatch.setattr(notify_mod.sys, "platform", platform)

    with patch.object(notify_mod, "threading") as mock_threading:
        mock_threading.Thread.return_value = MagicMock()
        notify_mod.send(*args)

    target = mock_threading.Thread.call_args.kwargs["target"]
    target()


def test_send_dispatches_windows(monkeypatch):
    with patch.object(notify_mod, "_notify_windows") as backend:
        _run_send(monkeypatch, "win32", "Hello", "World")
    backend.assert_called_once_with("Hello", "World")


def test_send_dispatches_macos(monkeypatch):
    with patch.object(notify_mod, "_notify_macos") as backend:
        _run_send(monkeypatch, "darwin", "Hello", "World")
    backend.assert_called_once_with("Hello", "World")


def test_send_dispatches_linux(monkeypatch):
    with patch.object(notify_mod, "_notify_linux") as backend:
        _run_send(monkeypatch, "linux", "Hello", "World")
    backend.assert_called_once_with("Hello", "World")


def test_send_passes_title_and_body(monkeypatch):
    with patch.object(notify_mod, "_notify_linux") as backend:
        _run_send(monkeypatch, "linux", "My Title", "My Body")
    backend.assert_called_once_with("My Title", "My Body")


def test_send_default_body_is_empty(monkeypatch):
    with patch.object(notify_mod, "_notify_linux") as backend:
        _run_send(monkeypatch, "linux", "Title only")
    backend.assert_called_once_with("Title only", "")


def test_send_spawns_daemon_thread(monkeypatch):
    monkeypatch.setattr(notify_mod.sys, "platform", "linux")

    with patch.object(notify_mod, "threading") as mock_threading:
        mock_threading.Thread.return_value = MagicMock()
        notify_mod.send("T", "B")

    assert mock_threading.Thread.call_args.kwargs.get("daemon") is True


# ── Windows notification ──────────────────────────────────────────────────────


def test_notify_windows_calls_powershell():
    with patch.object(notify_mod.subprocess, "run") as mock_run:
        notify_mod._notify_windows("Hello", "World")

    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "powershell"
    script = cmd[-1]
    assert "Hello" in script
    assert "World" in script


def test_notify_windows_escapes_single_quotes():
    with patch.object(notify_mod.subprocess, "run") as mock_run:
        notify_mod._notify_windows("It's a test", "O'Brien said hi")

    script = mock_run.call_args[0][0][-1]
    assert "It''s a test" in script
    assert "O''Brien said hi" in script


def test_notify_windows_runs_hidden():
    with patch.object(notify_mod.subprocess, "run") as mock_run:
        notify_mod._notify_windows("T", "B")

    cmd = mock_run.call_args[0][0]
    assert "-WindowStyle" in cmd
    assert "Hidden" in cmd


# ── macOS notification ────────────────────────────────────────────────────────


def test_notify_macos_calls_osascript():
    with patch.object(notify_mod.subprocess, "run") as mock_run:
        notify_mod._notify_macos("Hello", "World")

    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "osascript"
    script = cmd[-1]
    assert "Hello" in script
    assert "World" in script


def test_notify_macos_escapes_double_quotes():
    with patch.object(notify_mod.subprocess, "run") as mock_run:
        notify_mod._notify_macos('Say "hi"', 'Body "text"')

    script = mock_run.call_args[0][0][-1]
    assert '\\"hi\\"' in script
    assert '\\"text\\"' in script


# ── Linux notification ────────────────────────────────────────────────────────


def test_notify_linux_calls_notify_send():
    with patch.object(notify_mod.subprocess, "run") as mock_run:
        notify_mod._notify_linux("Hello", "World")

    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "notify-send"
    assert "Hello" in cmd
    assert "World" in cmd


# ── App.notify() ──────────────────────────────────────────────────────────────


def test_app_notify_calls_send():
    app = App()
    with patch("vesper.core.notify.send") as mock_send:
        app.notify("Title", "Body")

    mock_send.assert_called_once_with("Title", "Body")


def test_app_notify_default_body():
    app = App()
    with patch("vesper.core.notify.send") as mock_send:
        app.notify("Title only")

    mock_send.assert_called_once_with("Title only", "")


# ── vesper:notify built-in command ────────────────────────────────────────────


def test_vesper_notify_command_registered():
    app = App()
    from vesper.core.registry import CommandRegistry
    assert "vesper:notify" in app.registry._commands


def test_vesper_notify_command_via_ipc():
    app = App()
    with patch("vesper.core.notify.send") as mock_send, \
         patch.object(notify_mod, "threading") as mock_threading:
        mock_threading.Thread.return_value = MagicMock()
        resp = app.ipc.handle({"id": "1", "command": "vesper:notify", "args": {"title": "Hi", "body": "There"}})

    assert resp["ok"] is True
