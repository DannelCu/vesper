"""Tests for built-in filesystem API (vesper.core.fs + vesper:fs:* IPC commands)."""
from __future__ import annotations

import base64
from pathlib import Path

import pytest

from vesper import App
from vesper.core import fs
from vesper.core.fs_scope import FsScope, FsScopeError


# ── fs.read ──────────────────────────────────────────────────────────────────


def test_read_returns_file_contents(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("hello world", encoding="utf-8")
    assert fs.read(str(f)) == "hello world"


def test_read_respects_encoding(tmp_path):
    f = tmp_path / "latin.txt"
    f.write_bytes("café".encode("latin-1"))
    assert fs.read(str(f), encoding="latin-1") == "café"


def test_read_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        fs.read(str(tmp_path / "nope.txt"))


# ── fs.write ─────────────────────────────────────────────────────────────────


def test_write_creates_file(tmp_path):
    target = tmp_path / "out.txt"
    fs.write(str(target), "content")
    assert target.read_text() == "content"


def test_write_creates_parent_dirs(tmp_path):
    target = tmp_path / "deep" / "nested" / "file.txt"
    fs.write(str(target), "nested")
    assert target.read_text() == "nested"


def test_write_overwrites_existing(tmp_path):
    target = tmp_path / "file.txt"
    target.write_text("old")
    fs.write(str(target), "new")
    assert target.read_text() == "new"


# ── fs.exists ────────────────────────────────────────────────────────────────


def test_exists_true_for_file(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("")
    assert fs.exists(str(f)) is True


def test_exists_true_for_directory(tmp_path):
    assert fs.exists(str(tmp_path)) is True


def test_exists_false_for_missing(tmp_path):
    assert fs.exists(str(tmp_path / "nope")) is False


# ── fs.list_dir ──────────────────────────────────────────────────────────────


def test_list_dir_returns_entries(tmp_path):
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "b.txt").write_text("")
    entries = fs.list_dir(str(tmp_path))
    names = [e["name"] for e in entries]
    assert "a.txt" in names
    assert "b.txt" in names


def test_list_dir_entry_has_required_keys(tmp_path):
    (tmp_path / "file.txt").write_text("")
    entries = fs.list_dir(str(tmp_path))
    assert len(entries) == 1
    e = entries[0]
    assert "name" in e
    assert "path" in e
    assert "is_dir" in e


def test_list_dir_directory_flagged(tmp_path):
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    entries = fs.list_dir(str(tmp_path))
    assert entries[0]["is_dir"] is True


def test_list_dir_dirs_before_files(tmp_path):
    (tmp_path / "z.txt").write_text("")
    (tmp_path / "adir").mkdir()
    entries = fs.list_dir(str(tmp_path))
    assert entries[0]["is_dir"] is True
    assert entries[1]["is_dir"] is False


def test_list_dir_missing_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        fs.list_dir(str(tmp_path / "nope"))


# ── fs.mkdir ─────────────────────────────────────────────────────────────────


def test_mkdir_creates_directory(tmp_path):
    target = tmp_path / "newdir"
    fs.mkdir(str(target))
    assert target.is_dir()


def test_mkdir_without_parents_fails_on_missing_ancestor(tmp_path):
    with pytest.raises(FileNotFoundError):
        fs.mkdir(str(tmp_path / "a" / "b"))


def test_mkdir_with_parents_creates_ancestors(tmp_path):
    target = tmp_path / "a" / "b" / "c"
    fs.mkdir(str(target), parents=True)
    assert target.is_dir()


def test_mkdir_existing_raises(tmp_path):
    with pytest.raises(FileExistsError):
        fs.mkdir(str(tmp_path))


# ── fs.copy / fs.move ────────────────────────────────────────────────────────


def test_copy_file(tmp_path):
    src = tmp_path / "src.txt"
    src.write_text("data")
    dst = tmp_path / "dst.txt"
    fs.copy(str(src), str(dst))
    assert dst.read_text() == "data"
    assert src.exists()


def test_copy_directory_tree(tmp_path):
    src = tmp_path / "srcdir"
    (src / "nested").mkdir(parents=True)
    (src / "nested" / "f.txt").write_text("deep")
    dst = tmp_path / "dstdir"
    fs.copy(str(src), str(dst))
    assert (dst / "nested" / "f.txt").read_text() == "deep"


def test_move_renames_file(tmp_path):
    src = tmp_path / "old.txt"
    src.write_text("payload")
    dst = tmp_path / "new.txt"
    fs.move(str(src), str(dst))
    assert not src.exists()
    assert dst.read_text() == "payload"


def test_move_directory(tmp_path):
    src = tmp_path / "srcdir"
    src.mkdir()
    (src / "f.txt").write_text("x")
    dst = tmp_path / "moved"
    fs.move(str(src), str(dst))
    assert not src.exists()
    assert (dst / "f.txt").read_text() == "x"


# ── fs.remove ────────────────────────────────────────────────────────────────


def test_remove_deletes_file(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("")
    fs.remove(str(f))
    assert not f.exists()


def test_remove_directory_without_flag_raises(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    with pytest.raises(IsADirectoryError):
        fs.remove(str(d))
    assert d.exists()


def test_remove_directory_recursive(tmp_path):
    d = tmp_path / "d"
    (d / "sub").mkdir(parents=True)
    (d / "sub" / "f.txt").write_text("")
    fs.remove(str(d), recursive=True)
    assert not d.exists()


def test_remove_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        fs.remove(str(tmp_path / "nope.txt"))


# ── fs.stat ──────────────────────────────────────────────────────────────────


def test_stat_file(tmp_path):
    f = tmp_path / "f.bin"
    f.write_bytes(b"12345")
    info = fs.stat(str(f))
    assert info["size"] == 5
    assert info["is_dir"] is False
    assert info["type"] == "file"
    assert info["mtime"] == pytest.approx(f.stat().st_mtime)


def test_stat_directory(tmp_path):
    info = fs.stat(str(tmp_path))
    assert info["is_dir"] is True
    assert info["type"] == "dir"


def test_stat_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        fs.stat(str(tmp_path / "nope"))


# ── fs.read_bytes / fs.write_bytes ───────────────────────────────────────────


def test_binary_round_trip_preserves_exact_data(tmp_path):
    # Every byte value, twice, so nothing about encoding or line endings can hide.
    payload = bytes(range(256)) * 2
    target = tmp_path / "blob.bin"

    fs.write_bytes(str(target), base64.b64encode(payload).decode("ascii"))
    assert base64.b64decode(fs.read_bytes(str(target))) == payload
    assert target.read_bytes() == payload


def test_write_bytes_creates_parent_dirs(tmp_path):
    target = tmp_path / "deep" / "blob.bin"
    fs.write_bytes(str(target), base64.b64encode(b"x").decode("ascii"))
    assert target.read_bytes() == b"x"


def test_write_bytes_rejects_invalid_base64(tmp_path):
    target = tmp_path / "blob.bin"
    with pytest.raises(Exception):
        fs.write_bytes(str(target), "not!!valid@@base64")
    assert not target.exists()


# ── scope enforcement on the new operations ──────────────────────────────────


def _scoped(tmp_path) -> tuple[FsScope, Path, Path]:
    inside = tmp_path / "inside"
    outside = tmp_path / "outside"
    inside.mkdir()
    outside.mkdir()
    return FsScope([str(inside)]), inside, outside


def test_copy_with_destination_outside_scope_raises_like_read(tmp_path):
    scope, inside, outside = _scoped(tmp_path)
    src = inside / "src.txt"
    src.write_text("data")

    with pytest.raises(FsScopeError):
        fs.copy(str(src), str(outside / "dst.txt"), scope=scope)
    # Same error type the rest of the fs API raises for an out-of-scope read.
    with pytest.raises(FsScopeError):
        fs.read(str(outside / "dst.txt"), scope=scope)
    assert not (outside / "dst.txt").exists()


def test_copy_with_source_outside_scope_raises(tmp_path):
    scope, inside, outside = _scoped(tmp_path)
    src = outside / "src.txt"
    src.write_text("secret")

    with pytest.raises(FsScopeError):
        fs.copy(str(src), str(inside / "dst.txt"), scope=scope)


def test_move_outside_scope_raises_and_leaves_source(tmp_path):
    scope, inside, outside = _scoped(tmp_path)
    src = inside / "src.txt"
    src.write_text("data")

    with pytest.raises(FsScopeError):
        fs.move(str(src), str(outside / "dst.txt"), scope=scope)
    assert src.exists()


@pytest.mark.parametrize("op", [
    lambda p, s: fs.mkdir(str(p / "d"), scope=s),
    lambda p, s: fs.remove(str(p / "f"), scope=s),
    lambda p, s: fs.stat(str(p), scope=s),
    lambda p, s: fs.read_bytes(str(p / "f"), scope=s),
    lambda p, s: fs.write_bytes(str(p / "f"), "eA==", scope=s),
])
def test_new_operations_reject_out_of_scope_paths(tmp_path, op):
    scope, inside, outside = _scoped(tmp_path)
    with pytest.raises(FsScopeError):
        op(outside, scope)


# ── IPC command registration ──────────────────────────────────────────────────


def test_fs_commands_registered_in_app():
    app = App()
    for cmd in (
        "vesper:fs:read", "vesper:fs:write", "vesper:fs:exists", "vesper:fs:list",
        "vesper:fs:mkdir", "vesper:fs:copy", "vesper:fs:move", "vesper:fs:remove",
        "vesper:fs:stat", "vesper:fs:read_bytes", "vesper:fs:write_bytes",
    ):
        assert cmd in app.registry._commands


def test_app_exposes_fs_scope(tmp_path):
    assert App().fs_scope is None
    scoped = App(fs_scope=[str(tmp_path)])
    assert isinstance(scoped.fs_scope, FsScope)


def test_fs_read_via_ipc(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("ipc content")
    app = App()
    resp = app.ipc.handle({"id": "1", "command": "vesper:fs:read", "args": {"path": str(f)}})
    assert resp["ok"] is True
    assert resp["result"] == "ipc content"


def test_fs_write_via_ipc(tmp_path):
    target = tmp_path / "written.txt"
    app = App()
    resp = app.ipc.handle({
        "id": "1",
        "command": "vesper:fs:write",
        "args": {"path": str(target), "content": "hello"},
    })
    assert resp["ok"] is True
    assert target.read_text() == "hello"


def test_fs_exists_via_ipc(tmp_path):
    f = tmp_path / "present.txt"
    f.write_text("")
    app = App()
    resp = app.ipc.handle({"id": "1", "command": "vesper:fs:exists", "args": {"path": str(f)}})
    assert resp["ok"] is True
    assert resp["result"] is True


def test_fs_list_via_ipc(tmp_path):
    (tmp_path / "item.txt").write_text("")
    app = App()
    resp = app.ipc.handle({"id": "1", "command": "vesper:fs:list", "args": {"path": str(tmp_path)}})
    assert resp["ok"] is True
    assert len(resp["result"]) == 1
    assert resp["result"][0]["name"] == "item.txt"
