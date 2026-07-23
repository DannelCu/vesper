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

    def _fetch(url, dest, on_progress=None, *, timeout=None):
        calls["url"] = url
        calls["timeout"] = timeout
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


def test_download_passes_timeout_to_fetch(fake_fetch, tmp_path):
    net.download("http://example.test/f", str(tmp_path / "f.bin"), timeout=5.0)
    assert fake_fetch["timeout"] == 5.0


def test_download_uses_default_timeout_when_unset(fake_fetch, tmp_path):
    net.download("http://example.test/f", str(tmp_path / "f.bin"))
    assert fake_fetch["timeout"] == net.DEFAULT_TIMEOUT


# ── fetch(): real streaming behaviour with a stubbed urlopen ──────────────────


class _FakeResponse:
    """Minimal stand-in for the urlopen context manager."""
    def __init__(self, chunks, content_length):
        self._chunks = list(chunks)
        self.headers = {"Content-Length": str(content_length)} if content_length else {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, _size):
        return self._chunks.pop(0) if self._chunks else b""


def test_fetch_streams_to_dest_and_reports_progress(monkeypatch, tmp_path):
    body = [b"a" * 50, b"b" * 50]  # 100 bytes total
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["timeout"] = timeout
        return _FakeResponse(body, content_length=100)

    monkeypatch.setattr(net.urllib.request, "urlopen", fake_urlopen)

    seen = []
    dest = tmp_path / "out.bin"
    net.fetch("http://example.test/f", str(dest), on_progress=seen.append, timeout=7.0)

    assert dest.read_bytes() == b"a" * 50 + b"b" * 50
    assert captured["timeout"] == 7.0
    assert seen[-1] == 100          # always ends at 100
    assert seen == sorted(seen)     # monotonic


def test_fetch_reports_100_even_without_content_length(monkeypatch, tmp_path):
    def fake_urlopen(request, timeout=None):
        return _FakeResponse([b"data"], content_length=0)

    monkeypatch.setattr(net.urllib.request, "urlopen", fake_urlopen)

    seen = []
    net.fetch("http://example.test/f", str(tmp_path / "o.bin"), on_progress=seen.append)
    assert seen == [100]


def test_fetch_propagates_a_stalled_connection(monkeypatch, tmp_path):
    # A timeout on connect/read must raise, not hang — the whole reason the
    # timeout exists. urlopen raising TimeoutError stands in for the stall.
    def fake_urlopen(request, timeout=None):
        raise TimeoutError("timed out")

    monkeypatch.setattr(net.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(TimeoutError):
        net.fetch("http://example.test/f", str(tmp_path / "o.bin"))


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

    def _fetch(url, dest, on_progress=None, *, timeout=None):
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
    monkeypatch.setattr(net, "fetch", lambda url, dest, on_progress=None, **_: Path(dest).write_bytes(b"x"))

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
