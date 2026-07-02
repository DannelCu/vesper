"""Tests for the auto-update system (vesper.core.updater + vesper:update:* IPC commands)."""
from __future__ import annotations

import json
import platform
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vesper import App
from vesper.core import updater


# ── _parse_version ─────────────────────────────────────────────────────────────


def test_parse_version_basic():
    from packaging.version import Version
    assert updater._parse_version("1.2.3") == Version("1.2.3")


def test_parse_version_strips_v_prefix():
    from packaging.version import Version
    assert updater._parse_version("v2.0.0") == Version("2.0.0")


def test_parse_version_single_segment():
    from packaging.version import Version
    assert updater._parse_version("5") == Version("5")


def test_parse_version_invalid_returns_zero():
    from packaging.version import Version
    assert updater._parse_version("not-a-version") == Version("0")


# ── _platform_key ──────────────────────────────────────────────────────────────


def test_platform_key_returns_known_value():
    key = updater._platform_key()
    assert key in ("win32", "darwin", "linux")


# ── updater.check ──────────────────────────────────────────────────────────────


def _manifest(version="2.0.0", notes="", platform_key=None, download_url="https://example.com/app"):
    key = platform_key or updater._platform_key()
    return json.dumps({
        "version": version,
        "notes": notes,
        "platforms": {key: download_url},
    }).encode()


def _mock_urlopen(body: bytes):
    resp = MagicMock()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    resp.read.return_value = body
    return resp


def test_check_returns_update_info_when_newer():
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(_manifest("2.0.0"))):
        result = updater.check("https://manifest.example.com", "1.0.0")
    assert result is not None
    assert result["version"] == "2.0.0"
    assert "download_url" in result


def test_check_returns_none_when_up_to_date():
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(_manifest("1.0.0"))):
        result = updater.check("https://manifest.example.com", "1.0.0")
    assert result is None


def test_check_returns_none_when_older():
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(_manifest("0.9.0"))):
        result = updater.check("https://manifest.example.com", "1.0.0")
    assert result is None


def test_check_returns_none_on_network_error():
    with patch("urllib.request.urlopen", side_effect=OSError("network error")):
        result = updater.check("https://manifest.example.com", "1.0.0")
    assert result is None


def test_check_returns_none_when_platform_not_listed():
    manifest = json.dumps({
        "version": "2.0.0",
        "notes": "",
        "platforms": {"other_platform": "https://example.com/app"},
    }).encode()
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(manifest)):
        result = updater.check("https://manifest.example.com", "1.0.0")
    assert result is None


def test_check_returns_none_when_url_empty():
    result = updater.check("", "1.0.0")
    assert result is None


def test_check_returns_none_when_version_empty():
    result = updater.check("https://manifest.example.com", "")
    assert result is None


def test_check_includes_notes():
    body = _manifest("2.0.0", notes="Performance improvements")
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(body)):
        result = updater.check("https://manifest.example.com", "1.0.0")
    assert result["notes"] == "Performance improvements"


# ── updater.download ───────────────────────────────────────────────────────────


def test_download_returns_file_path(tmp_path):
    fake_binary = b"fake binary content"
    dest = tmp_path / "app_new"
    dest.write_bytes(fake_binary)

    def fake_urlretrieve(url, filename, reporthook=None):
        Path(filename).write_bytes(fake_binary)

    with patch("urllib.request.urlretrieve", side_effect=fake_urlretrieve):
        path = updater.download("https://example.com/app")

    assert Path(path).exists()
    assert Path(path).read_bytes() == fake_binary
    Path(path).unlink(missing_ok=True)


def test_download_calls_on_progress(tmp_path):
    calls = []

    def fake_urlretrieve(url, filename, reporthook=None):
        Path(filename).write_bytes(b"data")
        if reporthook:
            reporthook(0, 512, 1024)
            reporthook(1, 512, 1024)
            reporthook(2, 512, 1024)

    with patch("urllib.request.urlretrieve", side_effect=fake_urlretrieve):
        path = updater.download("https://example.com/app", on_progress=calls.append)

    assert len(calls) > 0
    assert all(0 <= p <= 100 for p in calls)
    Path(path).unlink(missing_ok=True)


def test_download_preserves_file_extension(tmp_path):
    def fake_urlretrieve(url, filename, reporthook=None):
        Path(filename).write_bytes(b"exe")

    with patch("urllib.request.urlretrieve", side_effect=fake_urlretrieve):
        path = updater.download("https://example.com/myapp.exe")

    assert path.endswith(".exe")
    Path(path).unlink(missing_ok=True)


# ── updater.install (POSIX path, mocked) ──────────────────────────────────────


@pytest.mark.skipif(platform.system() == "Windows", reason="POSIX install only")
def test_install_posix_copies_and_reexecs(tmp_path):
    new_bin = tmp_path / "new_app"
    new_bin.write_bytes(b"new binary")

    with patch("shutil.copy2") as mock_copy, \
         patch("os.chmod") as mock_chmod, \
         patch("os.execv") as mock_execv:
        updater.install(str(new_bin), allow_unverified=True)

    mock_copy.assert_called_once()
    mock_chmod.assert_called_once()
    mock_execv.assert_called_once_with(sys.executable, sys.argv)


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows install only")
def test_install_windows_launches_bat_and_exits(tmp_path):
    new_bin = tmp_path / "new_app.exe"
    new_bin.write_bytes(b"new binary")

    with patch("subprocess.Popen") as mock_popen, \
         patch("sys.exit") as mock_exit:
        updater.install(str(new_bin), allow_unverified=True)

    mock_popen.assert_called_once()
    cmd = mock_popen.call_args[0][0]
    assert cmd[0] == "cmd.exe"
    mock_exit.assert_called_once_with(0)


# ── IPC registration ───────────────────────────────────────────────────────────


def test_update_commands_registered_in_app():
    app = App()
    for cmd in ("vesper:update:check", "vesper:update:download", "vesper:update:install"):
        assert cmd in app.registry._commands


# ── vesper:update:check via IPC ───────────────────────────────────────────────


def test_update_check_returns_none_when_not_configured():
    app = App()
    resp = app.ipc.handle({"id": "1", "command": "vesper:update:check", "args": {}})
    assert resp["ok"] is True
    assert resp["result"] is None


def test_update_check_returns_info_when_update_available():
    app = App(version="1.0.0", update_url="https://manifest.example.com")
    body = _manifest("2.0.0")
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(body)):
        resp = app.ipc.handle({"id": "1", "command": "vesper:update:check", "args": {}})
    assert resp["ok"] is True
    assert resp["result"]["version"] == "2.0.0"


def test_update_check_returns_none_when_up_to_date():
    app = App(version="2.0.0", update_url="https://manifest.example.com")
    body = _manifest("2.0.0")
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(body)):
        resp = app.ipc.handle({"id": "1", "command": "vesper:update:check", "args": {}})
    assert resp["ok"] is True
    assert resp["result"] is None


# ── vesper:update:download via IPC ────────────────────────────────────────────


def test_update_download_returns_path():
    app = App()

    def fake_urlretrieve(url, filename, reporthook=None):
        Path(filename).write_bytes(b"binary")

    with patch("urllib.request.urlretrieve", side_effect=fake_urlretrieve):
        resp = app.ipc.handle({
            "id": "1",
            "command": "vesper:update:download",
            "args": {"url": "https://example.com/app"},
        })

    assert resp["ok"] is True
    path = resp["result"]
    assert Path(path).exists()
    Path(path).unlink(missing_ok=True)


# ── app.check_update / download_update Python API ─────────────────────────────


def test_app_check_update_delegates_to_updater():
    app = App(version="1.0.0", update_url="https://manifest.example.com")
    body = _manifest("3.0.0")
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(body)):
        result = app.check_update()
    assert result is not None
    assert result["version"] == "3.0.0"


def test_app_download_update_calls_progress(tmp_path):
    app = App()
    progress_calls = []

    def fake_urlretrieve(url, filename, reporthook=None):
        Path(filename).write_bytes(b"data")
        if reporthook:
            reporthook(1, 100, 100)

    with patch("urllib.request.urlretrieve", side_effect=fake_urlretrieve):
        path = app.download_update("https://example.com/app", on_progress=progress_calls.append)

    assert Path(path).exists()
    assert 100 in progress_calls
    Path(path).unlink(missing_ok=True)
