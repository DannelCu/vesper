"""Tests for vesper.core.net — generic scoped download with progress."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from vesper import App
from vesper.core import net, updater
from vesper.core.fs_scope import FsScope, FsScopeError


@pytest.fixture
def fake_fetch(monkeypatch):
    """Replace the network with a local write; records the requested URL."""
    calls = {}

    def _fetch(url, dest, on_progress=None):
        calls["url"] = url
        Path(dest).write_bytes(b"payload")
        if on_progress:
            on_progress(50)
            on_progress(100)

    monkeypatch.setattr(net, "fetch", _fetch)
    return calls


def test_download_writes_to_dest_and_reports_progress(fake_fetch, tmp_path):
    seen = []
    dest = tmp_path / "sub" / "file.bin"

    result = net.download("http://example.test/f", str(dest), on_progress=seen.append)

    assert result == str(dest)
    assert dest.read_bytes() == b"payload"
    assert seen == [50, 100]
    assert fake_fetch["url"] == "http://example.test/f"


def test_download_validates_dest_against_scope(fake_fetch, tmp_path):
    inside = tmp_path / "inside"
    inside.mkdir()
    scope = FsScope([str(inside)])

    with pytest.raises(FsScopeError):
        net.download("http://example.test/f", str(tmp_path / "out.bin"), scope=scope)

    assert net.download("http://example.test/f", str(inside / "ok.bin"), scope=scope)


def test_download_verifies_checksum(fake_fetch, tmp_path):
    dest = tmp_path / "file.bin"
    good = hashlib.sha256(b"payload").hexdigest()
    assert net.download("http://example.test/f", str(dest), expected_sha256=good)


def test_download_checksum_mismatch_deletes_file(fake_fetch, tmp_path):
    dest = tmp_path / "file.bin"
    with pytest.raises(ValueError):
        net.download("http://example.test/f", str(dest), expected_sha256="0" * 64)
    # A failed verification must not leave the bad artifact behind.
    assert not dest.exists()


def test_updater_download_delegates_to_net(monkeypatch):
    """The updater keeps its temp-file contract on top of net.fetch."""
    calls = {}

    def _fetch(url, dest, on_progress=None):
        calls["url"] = url
        Path(dest).write_bytes(b"binary")

    monkeypatch.setattr(net, "fetch", _fetch)

    path = updater.download("http://example.test/app.exe")
    try:
        assert calls["url"] == "http://example.test/app.exe"
        assert Path(path).read_bytes() == b"binary"
        assert path.endswith(".exe")
    finally:
        Path(path).unlink(missing_ok=True)


def test_net_download_command_registered():
    assert "vesper:net:download" in App().registry._commands


def test_net_download_via_ipc_respects_scope(monkeypatch, tmp_path):
    monkeypatch.setattr(net, "fetch", lambda url, dest, on_progress=None: Path(dest).write_bytes(b"x"))

    inside = tmp_path / "inside"
    inside.mkdir()
    app = App(fs_scope=[str(inside)])

    denied = app.ipc.handle({
        "id": "1", "command": "vesper:net:download",
        "args": {"url": "http://example.test/f", "dest": str(tmp_path / "no.bin")},
    })
    assert denied["ok"] is False
    assert denied["error"]["type"] == "FsScopeError"

    allowed = app.ipc.handle({
        "id": "2", "command": "vesper:net:download",
        "args": {"url": "http://example.test/f", "dest": str(inside / "yes.bin")},
    })
    assert allowed["ok"] is True
    assert (inside / "yes.bin").read_bytes() == b"x"
