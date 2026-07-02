"""Tests for FsScope path allowlist."""
from __future__ import annotations

import pytest

from vesper.core.fs_scope import FsScope, FsScopeError


def test_path_inside_scope_allowed(tmp_path):
    scope = FsScope([str(tmp_path)])
    f = tmp_path / "a.txt"
    f.write_text("hi")
    assert scope.check(str(f)).name == "a.txt"


def test_path_outside_scope_rejected(tmp_path):
    scope = FsScope([str(tmp_path)])
    with pytest.raises(FsScopeError):
        scope.check("/etc/passwd")


def test_traversal_rejected(tmp_path):
    scope = FsScope([str(tmp_path)])
    with pytest.raises(FsScopeError):
        scope.check(str(tmp_path / ".." / ".." / "etc" / "passwd"))


def test_wildcard_allows_any_path():
    scope = FsScope("*")
    assert scope.check("/etc/passwd") is not None


def test_multiple_roots(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir(); b.mkdir()
    scope = FsScope([str(a), str(b)])
    assert scope.check(str(a / "f.txt")).parent == a
    assert scope.check(str(b / "f.txt")).parent == b
    with pytest.raises(FsScopeError):
        scope.check(str(tmp_path / "c" / "f.txt"))


def test_none_scope_has_no_roots():
    scope = FsScope(None)
    assert scope._roots == []
    assert not scope._allow_all


def test_fs_read_honors_scope(tmp_path):
    from vesper.core import fs
    scope = FsScope([str(tmp_path)])
    f = tmp_path / "b.txt"
    f.write_text("data")
    assert fs.read(str(f), scope=scope) == "data"
    with pytest.raises(FsScopeError):
        fs.read(str(tmp_path / ".." / "other.txt"), scope=scope)


def test_fs_write_honors_scope(tmp_path):
    from vesper.core import fs
    scope = FsScope([str(tmp_path)])
    dest = tmp_path / "out.txt"
    fs.write(str(dest), "hello", scope=scope)
    assert dest.read_text() == "hello"
    with pytest.raises(FsScopeError):
        fs.write("/tmp/evil.txt", "bad", scope=scope)


def test_fs_exists_honors_scope(tmp_path):
    from vesper.core import fs
    scope = FsScope([str(tmp_path)])
    assert fs.exists(str(tmp_path), scope=scope) is True
    with pytest.raises(FsScopeError):
        fs.exists("/etc/passwd", scope=scope)


def test_fs_list_honors_scope(tmp_path):
    from vesper.core import fs
    scope = FsScope([str(tmp_path)])
    (tmp_path / "f.txt").write_text("x")
    entries = fs.list_dir(str(tmp_path), scope=scope)
    assert any(e["name"] == "f.txt" for e in entries)
    with pytest.raises(FsScopeError):
        fs.list_dir("/etc", scope=scope)


def test_app_fs_scope_restricts_ipc(tmp_path):
    from vesper import App
    app = App(fs_scope=[str(tmp_path)])
    f = tmp_path / "ok.txt"
    f.write_text("safe")
    resp = app.ipc.handle({"id": 1, "command": "vesper:fs:read", "args": {"path": str(f)}})
    assert resp["ok"] is True
    resp2 = app.ipc.handle({"id": 2, "command": "vesper:fs:read", "args": {"path": "/etc/passwd"}})
    assert resp2["ok"] is False
    assert "FsScopeError" in resp2["error"]["type"] or "scope" in resp2["error"]["message"].lower()


def test_app_without_fs_scope_allows_all(tmp_path):
    from vesper import App
    app = App()
    f = tmp_path / "x.txt"
    f.write_text("open")
    resp = app.ipc.handle({"id": 1, "command": "vesper:fs:read", "args": {"path": str(f)}})
    assert resp["ok"] is True
