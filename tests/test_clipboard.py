"""Tests for clipboard API (vesper.core.clipboard + vesper:clipboard:* IPC commands)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vesper import App
from vesper.core import clipboard as clip_mod


# ── read — platform dispatch ─────────────────────────────────────────────────


def test_read_windows_calls_powershell(monkeypatch):
    monkeypatch.setattr(clip_mod.sys, "platform", "win32")
    with patch.object(clip_mod.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(stdout="hello\r\n")
        clip_mod.read()
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "powershell"
    assert "Get-Clipboard" in " ".join(cmd)


def test_read_macos_calls_pbpaste(monkeypatch):
    monkeypatch.setattr(clip_mod.sys, "platform", "darwin")
    with patch.object(clip_mod.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(stdout="hello")
        clip_mod.read()
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "pbpaste"


def test_read_linux_calls_xclip(monkeypatch):
    monkeypatch.setattr(clip_mod.sys, "platform", "linux")
    with patch.object(clip_mod.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(stdout="hello")
        clip_mod.read()
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "xclip"
    assert "-selection" in cmd
    assert "clipboard" in cmd
    assert "-o" in cmd


def test_read_windows_strips_trailing_crlf(monkeypatch):
    monkeypatch.setattr(clip_mod.sys, "platform", "win32")
    with patch.object(clip_mod.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(stdout="hello\r\n")
        result = clip_mod.read()
    assert result == "hello"


def test_read_windows_strips_trailing_lf(monkeypatch):
    monkeypatch.setattr(clip_mod.sys, "platform", "win32")
    with patch.object(clip_mod.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(stdout="hello\n")
        result = clip_mod.read()
    assert result == "hello"


def test_read_macos_returns_stdout_as_is(monkeypatch):
    monkeypatch.setattr(clip_mod.sys, "platform", "darwin")
    with patch.object(clip_mod.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(stdout="copied text")
        result = clip_mod.read()
    assert result == "copied text"


# ── write — platform dispatch ─────────────────────────────────────────────────


def test_write_windows_calls_powershell(monkeypatch):
    monkeypatch.setattr(clip_mod.sys, "platform", "win32")
    with patch.object(clip_mod.subprocess, "run") as mock_run:
        clip_mod.write("hello")
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "powershell"
    assert "Set-Clipboard" in " ".join(cmd)


def test_write_windows_passes_text_via_stdin(monkeypatch):
    monkeypatch.setattr(clip_mod.sys, "platform", "win32")
    with patch.object(clip_mod.subprocess, "run") as mock_run:
        clip_mod.write("it's here")
    kwargs = mock_run.call_args[1]
    # Text must arrive via stdin, not interpolated into the command string
    assert kwargs["input"] == "it's here".encode("utf-8")
    cmd_str = " ".join(mock_run.call_args[0][0])
    assert "it's here" not in cmd_str


def test_write_macos_calls_pbcopy(monkeypatch):
    monkeypatch.setattr(clip_mod.sys, "platform", "darwin")
    with patch.object(clip_mod.subprocess, "run") as mock_run:
        clip_mod.write("hello")
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "pbcopy"


def test_write_macos_passes_text_as_stdin(monkeypatch):
    monkeypatch.setattr(clip_mod.sys, "platform", "darwin")
    with patch.object(clip_mod.subprocess, "run") as mock_run:
        clip_mod.write("hello")
    kwargs = mock_run.call_args[1]
    assert kwargs["input"] == b"hello"


def test_write_linux_calls_xclip(monkeypatch):
    monkeypatch.setattr(clip_mod.sys, "platform", "linux")
    with patch.object(clip_mod.subprocess, "run") as mock_run:
        clip_mod.write("hello")
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "xclip"
    assert "-selection" in cmd
    assert "clipboard" in cmd


def test_write_linux_passes_text_as_stdin(monkeypatch):
    monkeypatch.setattr(clip_mod.sys, "platform", "linux")
    with patch.object(clip_mod.subprocess, "run") as mock_run:
        clip_mod.write("hello")
    kwargs = mock_run.call_args[1]
    assert kwargs["input"] == b"hello"


# ── IPC registration ─────────────────────────────────────────────────────────


def test_vesper_clipboard_read_registered():
    app = App()
    assert "vesper:clipboard:read" in app.registry._commands


def test_vesper_clipboard_write_registered():
    app = App()
    assert "vesper:clipboard:write" in app.registry._commands


def test_vesper_clipboard_read_via_ipc(monkeypatch):
    monkeypatch.setattr(clip_mod.sys, "platform", "darwin")
    app = App()
    with patch.object(clip_mod.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(stdout="copied")
        resp = app.ipc.handle({"id": "1", "command": "vesper:clipboard:read", "args": {}})
    assert resp["ok"] is True
    assert resp["result"] == "copied"


def test_vesper_clipboard_write_via_ipc(monkeypatch):
    monkeypatch.setattr(clip_mod.sys, "platform", "darwin")
    app = App()
    with patch.object(clip_mod.subprocess, "run") as mock_run:
        resp = app.ipc.handle({
            "id": "2",
            "command": "vesper:clipboard:write",
            "args": {"text": "hello"},
        })
    assert resp["ok"] is True
    assert mock_run.called
