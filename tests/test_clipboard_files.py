"""
Tests for the file clipboard (clipboard.write_files / read_files).

Per the coverage philosophy in KNOWN-ISSUES.md: what CI can verify is that the
right platform call is constructed and that degradation works; a real
copy-in-app → paste-in-file-manager round trip is a documented manual test.
"""
from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vesper import App
from vesper.core import clipboard
from vesper.core.fs_scope import FsScope


# ── Linux: xclip text/uri-list ───────────────────────────────────────────────


def test_linux_write_builds_uri_list(monkeypatch, tmp_path):
    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        calls["input"] = kwargs.get("input", b"")
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)

    f = tmp_path / "my file.txt"
    f.write_text("")
    assert clipboard.write_files([str(f)]) is True

    assert calls["cmd"] == ["xclip", "-selection", "clipboard", "-t", "text/uri-list"]
    # Paths become percent-encoded file:// URIs, one per line.
    assert calls["input"].decode().strip() == f.resolve().as_uri()
    assert "%20" in calls["input"].decode()


def test_linux_read_parses_uri_list(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "linux")

    def fake_run(cmd, **kwargs):
        assert cmd == ["xclip", "-selection", "clipboard", "-t", "text/uri-list", "-o"]
        return subprocess.CompletedProcess(
            cmd, 0,
            stdout="# comment\nfile:///tmp/a%20b.txt\r\nfile:///tmp/c.txt\n\n",
            stderr="",
        )

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)
    assert clipboard.read_files() == ["/tmp/a b.txt", "/tmp/c.txt"]


def test_linux_missing_xclip_degrades(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "linux")

    def raise_missing(*args, **kwargs):
        raise FileNotFoundError("xclip")

    monkeypatch.setattr(clipboard.subprocess, "run", raise_missing)
    assert clipboard.read_files() == []
    assert clipboard.write_files(["/tmp/x"]) is False


# ── macOS: osascript ─────────────────────────────────────────────────────────


def test_macos_write_single_file_script(monkeypatch, tmp_path):
    monkeypatch.setattr(clipboard.sys, "platform", "darwin")
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)

    f = tmp_path / "doc.pdf"
    f.write_text("")
    assert clipboard.write_files([str(f)]) is True

    assert calls["cmd"][0] == "osascript"
    # The path goes through the AppleScript quoting — on Windows runners the
    # tmp path contains backslashes, which the quoting doubles.
    expected = clipboard._osa_quote(str(f.resolve()))
    assert calls["cmd"][2] == f'set the clipboard to POSIX file "{expected}"'


def test_macos_write_multiple_files_builds_a_list(monkeypatch, tmp_path):
    monkeypatch.setattr(clipboard.sys, "platform", "darwin")
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)

    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("")
    b.write_text("")
    clipboard.write_files([str(a), str(b)])

    script = calls["cmd"][2]
    assert script.startswith("set the clipboard to {")
    assert f'POSIX file "{clipboard._osa_quote(str(a.resolve()))}"' in script
    assert f'POSIX file "{clipboard._osa_quote(str(b.resolve()))}"' in script


def test_macos_write_escapes_quotes(monkeypatch, tmp_path):
    monkeypatch.setattr(clipboard.sys, "platform", "darwin")
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)

    tricky = tmp_path / 'we"ird.txt'
    try:
        tricky.write_text("")
    except OSError:
        pytest.skip("filesystem rejects quotes in names")

    clipboard.write_files([str(tricky)])
    assert '\\"' in calls["cmd"][2]


def test_macos_read_returns_single_path(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "darwin")

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="/Users/x/doc.pdf\n", stderr="")

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)
    assert clipboard.read_files() == ["/Users/x/doc.pdf"]


def test_macos_read_no_file_on_clipboard(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "darwin")

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="error")

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)
    assert clipboard.read_files() == []


# ── Windows: CF_HDROP payload (pure) and ctypes calls (mocked) ───────────────


def test_hdrop_payload_layout():
    payload = clipboard._hdrop_payload(["C:\\a.txt", "C:\\b c.txt"])

    # 20-byte DROPFILES header: offset 20, wide-char flag set.
    assert payload[:4] == (20).to_bytes(4, "little")
    assert payload[16:20] == (1).to_bytes(4, "little")
    # Wide, NUL-separated, double-NUL-terminated file list.
    body = payload[20:].decode("utf-16-le")
    assert body == "C:\\a.txt\0C:\\b c.txt\0\0"


def test_windows_write_builds_the_clipboard_calls(monkeypatch, tmp_path):
    monkeypatch.setattr(clipboard.sys, "platform", "win32")

    windll = MagicMock()
    windll.kernel32.GlobalAlloc.return_value = 111
    windll.kernel32.GlobalLock.return_value = 222
    windll.user32.OpenClipboard.return_value = 1
    windll.user32.SetClipboardData.return_value = 333
    monkeypatch.setattr(ctypes, "windll", windll, raising=False)
    monkeypatch.setattr(ctypes, "memmove", MagicMock(), raising=False)

    f = tmp_path / "x.txt"
    f.write_text("")
    assert clipboard.write_files([str(f)]) is True

    assert windll.user32.SetClipboardData.call_args[0][0] == clipboard._CF_HDROP
    windll.user32.EmptyClipboard.assert_called_once()
    windll.user32.CloseClipboard.assert_called_once()
    windll.kernel32.GlobalFree.assert_not_called()   # success: clipboard owns it


def test_windows_write_frees_memory_on_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(clipboard.sys, "platform", "win32")

    windll = MagicMock()
    windll.kernel32.GlobalAlloc.return_value = 111
    windll.user32.OpenClipboard.return_value = 1
    windll.user32.SetClipboardData.return_value = 0   # rejected
    monkeypatch.setattr(ctypes, "windll", windll, raising=False)
    monkeypatch.setattr(ctypes, "memmove", MagicMock(), raising=False)

    f = tmp_path / "x.txt"
    f.write_text("")
    assert clipboard.write_files([str(f)]) is False
    windll.kernel32.GlobalFree.assert_called_once_with(111)
    windll.user32.CloseClipboard.assert_called_once()


# ── shared behaviour ─────────────────────────────────────────────────────────


def test_write_files_empty_list_is_false():
    assert clipboard.write_files([]) is False


def test_read_files_filters_paths_outside_scope(monkeypatch, tmp_path):
    inside = tmp_path / "inside"
    inside.mkdir()
    in_file = inside / "ok.txt"
    in_file.write_text("")

    monkeypatch.setattr(clipboard.sys, "platform", "linux")

    def fake_run(cmd, **kwargs):
        uris = f"{in_file.resolve().as_uri()}\nfile:///etc/passwd\n"
        return subprocess.CompletedProcess(cmd, 0, stdout=uris, stderr="")

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)

    scope = FsScope([str(inside)])
    assert clipboard.read_files(scope=scope) == [str(in_file.resolve())]


def test_clipboard_files_commands_registered():
    app = App()
    assert "vesper:clipboard:write_files" in app.registry._commands
    assert "vesper:clipboard:read_files" in app.registry._commands
