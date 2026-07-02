"""Tests for OS info built-in (vesper:os:info)."""
from __future__ import annotations

import vesper.core.os_info as os_info_mod
from vesper import App
from vesper.core.os_info import get_info


# ── get_info() ───────────────────────────────────────────────────────────────


def test_get_info_returns_dict():
    result = get_info()
    assert isinstance(result, dict)


def test_get_info_has_platform_key(monkeypatch):
    monkeypatch.setattr(os_info_mod.sys, "platform", "win32")
    result = get_info()
    assert result["platform"] == "win32"


def test_get_info_has_version_key():
    result = get_info()
    assert "version" in result
    assert isinstance(result["version"], str)


def test_get_info_has_machine_key():
    result = get_info()
    assert "machine" in result
    assert isinstance(result["machine"], str)


def test_get_info_has_python_version_key():
    result = get_info()
    assert "python_version" in result
    assert isinstance(result["python_version"], str)


def test_get_info_platform_reflects_sys(monkeypatch):
    monkeypatch.setattr(os_info_mod.sys, "platform", "darwin")
    assert get_info()["platform"] == "darwin"


# ── IPC registration ─────────────────────────────────────────────────────────


def test_vesper_os_info_registered():
    assert "vesper:os:info" in App().registry._commands


def test_vesper_os_info_via_ipc(monkeypatch):
    monkeypatch.setattr(os_info_mod.sys, "platform", "linux")
    app = App()
    resp = app.ipc.handle({"id": "1", "command": "vesper:os:info", "args": {}})
    assert resp["ok"] is True
    assert resp["result"]["platform"] == "linux"
