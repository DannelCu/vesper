"""Tests for shell integration (vesper.core.shell + vesper:shell:* IPC commands)."""
from __future__ import annotations

import ntpath
from unittest.mock import MagicMock, patch

import pytest

from vesper import App
from vesper.core import shell as shell_mod


# ── open_url ─────────────────────────────────────────────────────────────────


def test_open_url_calls_webbrowser():
    with patch.object(shell_mod.webbrowser, "open") as mock_open:
        shell_mod.open_url("https://example.com")
    mock_open.assert_called_once_with("https://example.com")


def test_open_url_passes_url_unchanged():
    with patch.object(shell_mod.webbrowser, "open") as mock_open:
        shell_mod.open_url("https://example.com/path?q=1")
    mock_open.assert_called_once_with("https://example.com/path?q=1")


# ── reveal — Windows ─────────────────────────────────────────────────────────


def test_reveal_windows_calls_explorer(monkeypatch):
    monkeypatch.setattr(shell_mod.sys, "platform", "win32")
    # reveal() absolutizes the path, and posixpath does not recognize "C:\..." as
    # absolute — so the Windows path rules have to be simulated too, or this asserts
    # against a cwd-prefixed path that would never occur on Windows.
    monkeypatch.setattr(shell_mod.os.path, "abspath", ntpath.abspath)

    with patch.object(shell_mod.subprocess, "run") as mock_run:
        shell_mod.reveal("C:\\Users\\user\\file.txt")
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "explorer"
    assert "/select," in cmd
    assert "C:\\Users\\user\\file.txt" in cmd


# ── reveal — macOS ───────────────────────────────────────────────────────────


def test_reveal_macos_calls_open_r(monkeypatch):
    monkeypatch.setattr(shell_mod.sys, "platform", "darwin")
    with patch.object(shell_mod.subprocess, "run") as mock_run:
        shell_mod.reveal("/Users/user/file.txt")
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "open"
    assert "-R" in cmd
    assert "/Users/user/file.txt" in cmd


# ── reveal — Linux ───────────────────────────────────────────────────────────


def test_reveal_linux_file_opens_parent(monkeypatch, tmp_path):
    monkeypatch.setattr(shell_mod.sys, "platform", "linux")
    f = tmp_path / "file.txt"
    f.write_text("x")
    with patch.object(shell_mod.subprocess, "run") as mock_run:
        shell_mod.reveal(str(f))
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "xdg-open"
    assert cmd[1] == str(tmp_path)


def test_reveal_linux_directory_opens_itself(monkeypatch, tmp_path):
    monkeypatch.setattr(shell_mod.sys, "platform", "linux")
    with patch.object(shell_mod.subprocess, "run") as mock_run:
        shell_mod.reveal(str(tmp_path))
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "xdg-open"
    assert cmd[1] == str(tmp_path)


# ── IPC registration ─────────────────────────────────────────────────────────


def test_vesper_shell_open_url_registered():
    app = App()
    assert "vesper:shell:open_url" in app.registry._commands


def test_vesper_shell_reveal_registered():
    app = App()
    assert "vesper:shell:reveal" in app.registry._commands


def test_vesper_shell_open_url_via_ipc():
    app = App()
    with patch.object(shell_mod.webbrowser, "open") as mock_open:
        resp = app.ipc.handle({
            "id": "1",
            "command": "vesper:shell:open_url",
            "args": {"url": "https://example.com"},
        })
    assert resp["ok"] is True
    mock_open.assert_called_once_with("https://example.com")


def test_vesper_shell_reveal_via_ipc(monkeypatch, tmp_path):
    monkeypatch.setattr(shell_mod.sys, "platform", "darwin")
    app = App()
    with patch.object(shell_mod.subprocess, "run") as mock_run:
        resp = app.ipc.handle({
            "id": "2",
            "command": "vesper:shell:reveal",
            "args": {"path": str(tmp_path)},
        })
    assert resp["ok"] is True
    assert mock_run.called
