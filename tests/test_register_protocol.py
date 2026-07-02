"""Tests for vesper register-protocol CLI command."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from vesper.commands.register_protocol import (
    handle_register_protocol,
    _register_windows,
    _register_linux,
    _register_macos,
)


def _args(scheme="myapp"):
    a = argparse.Namespace()
    a.command = "register-protocol"
    a.scheme = scheme
    return a


# ── handle_register_protocol routing ─────────────────────────────────────────


def test_handle_ignores_other_commands():
    a = _args()
    a.command = "build"
    assert handle_register_protocol(a) is False


def test_handle_returns_true_for_own_command(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert handle_register_protocol(_args()) is True


def test_handle_missing_scheme_prints_usage(monkeypatch, capsys):
    monkeypatch.setattr(sys, "platform", "linux")
    a = _args(scheme=None)
    handle_register_protocol(a)
    out = capsys.readouterr().out
    assert "Usage" in out


# ── Windows registration ──────────────────────────────────────────────────────


def test_register_windows_creates_registry_keys(monkeypatch):
    mock_winreg = MagicMock()
    mock_key = MagicMock()
    mock_winreg.CreateKey.return_value.__enter__ = lambda self: mock_key
    mock_winreg.CreateKey.return_value.__exit__ = lambda *a: None
    mock_winreg.HKEY_CURRENT_USER = "HKCU"
    mock_winreg.REG_SZ = 1

    monkeypatch.setitem(sys.modules, "winreg", mock_winreg)

    import importlib
    import vesper.commands.register_protocol as rp_mod
    monkeypatch.setattr(rp_mod.sys, "platform", "win32")
    monkeypatch.setattr(rp_mod.sys, "executable", "C:\\app.exe")

    _register_windows.__globals__["winreg"] = mock_winreg

    with patch.dict("sys.modules", {"winreg": mock_winreg}):
        from vesper.commands import register_protocol as rp
        rp._register_windows("myapp")

    assert mock_winreg.CreateKey.called


def test_handle_dispatches_to_windows(monkeypatch, capsys):
    monkeypatch.setattr(sys, "platform", "win32")
    mock_winreg = MagicMock()
    mock_winreg.HKEY_CURRENT_USER = "HKCU"
    mock_winreg.REG_SZ = 1
    mock_winreg.CreateKey.return_value.__enter__ = lambda self: MagicMock()
    mock_winreg.CreateKey.return_value.__exit__ = lambda *a: None

    with patch.dict("sys.modules", {"winreg": mock_winreg}):
        handle_register_protocol(_args("myapp"))

    assert mock_winreg.CreateKey.called


# ── macOS registration (prints instructions) ──────────────────────────────────


def test_register_macos_prints_plist_snippet(capsys):
    _register_macos("myapp")
    out = capsys.readouterr().out
    assert "CFBundleURLTypes" in out
    assert "myapp" in out


def test_register_macos_includes_official_docs_link(capsys):
    _register_macos("myapp")
    out = capsys.readouterr().out
    assert "developer.apple.com" in out


def test_handle_dispatches_to_macos(monkeypatch, capsys):
    monkeypatch.setattr(sys, "platform", "darwin")
    handle_register_protocol(_args("myapp"))
    out = capsys.readouterr().out
    assert "CFBundleURLTypes" in out


# ── Linux registration ────────────────────────────────────────────────────────


def test_register_linux_creates_desktop_file(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    with patch("vesper.commands.register_protocol.subprocess.run"):
        _register_linux("myapp")

    desktop = tmp_path / ".local" / "share" / "applications" / "myapp.desktop"
    assert desktop.exists()
    content = desktop.read_text()
    assert "x-scheme-handler/myapp" in content


def test_register_linux_desktop_file_contains_exec(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    with patch("vesper.commands.register_protocol.subprocess.run"):
        _register_linux("myapp")

    desktop = tmp_path / ".local" / "share" / "applications" / "myapp.desktop"
    assert "Exec=" in desktop.read_text()


def test_register_linux_calls_xdg_mime(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    with patch("vesper.commands.register_protocol.subprocess.run") as mock_run:
        _register_linux("myapp")

    cmds = [call[0][0] for call in mock_run.call_args_list]
    assert any("xdg-mime" in str(c) for c in cmds)
