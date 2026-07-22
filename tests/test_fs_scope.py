"""Tests for FsScope path allowlist."""
from __future__ import annotations

from pathlib import Path

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


# ── narrowing the scope at runtime ───────────────────────────────────────────
#
# An app whose working folder is chosen by the user cannot know its scope when
# the App is constructed. The fs commands hold a reference to the FsScope
# object, so updating that object is what reaches them — assigning a new one to
# app.fs_scope would not. Found while building examples/media-vault, which has a
# folder picker and had to enforce its own boundary on top.


def test_set_roots_narrows_an_existing_scope(tmp_path):
    wide = tmp_path
    narrow = tmp_path / "library"
    narrow.mkdir()
    (narrow / "a.txt").write_text("x")
    (wide / "b.txt").write_text("x")

    scope = FsScope([str(wide)])
    assert scope.check(str(wide / "b.txt"))          # allowed before

    scope.set_roots([str(narrow)])

    assert scope.check(str(narrow / "a.txt"))
    with pytest.raises(FsScopeError):
        scope.check(str(wide / "b.txt"))             # outside the new root


def test_set_roots_reaches_a_scope_already_handed_out(tmp_path):
    """The whole point: the object is shared, so holders see the change."""
    first = tmp_path / "one"
    second = tmp_path / "two"
    first.mkdir()
    second.mkdir()

    scope = FsScope([str(first)])
    holder = scope                                   # what a command captured

    scope.set_roots([str(second)])

    assert holder.check(str(second / "f.txt"))
    with pytest.raises(FsScopeError):
        holder.check(str(first / "f.txt"))


def test_set_roots_accepts_a_bare_string(tmp_path):
    scope = FsScope(None)
    scope.set_roots(str(tmp_path))
    assert scope.check(str(tmp_path / "x"))


def test_set_roots_to_none_denies_everything(tmp_path):
    scope = FsScope([str(tmp_path)])
    scope.set_roots(None)

    with pytest.raises(FsScopeError):
        scope.check(str(tmp_path / "x"))


def test_set_roots_can_restore_allow_all(tmp_path):
    scope = FsScope([str(tmp_path)])
    scope.set_roots("*")

    assert scope.allows_everything is True
    assert scope.check("/etc/hosts")


def test_set_roots_clears_a_previous_allow_all(tmp_path):
    """Going from "*" to a real list must actually start checking again."""
    scope = FsScope("*")
    assert scope.allows_everything is True

    scope.set_roots([str(tmp_path)])

    assert scope.allows_everything is False
    with pytest.raises(FsScopeError):
        scope.check("/etc/hosts")


def test_roots_property_reports_resolved_paths(tmp_path):
    scope = FsScope([str(tmp_path)])
    assert scope.roots == [tmp_path.resolve()]


def test_roots_property_is_a_copy(tmp_path):
    """Handing out the live list would let a caller widen the scope by accident."""
    scope = FsScope([str(tmp_path)])
    scope.roots.append(Path("/etc"))

    with pytest.raises(FsScopeError):
        scope.check("/etc/hosts")
