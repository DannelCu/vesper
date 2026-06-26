"""Tests for built-in filesystem API (vesper.core.fs + vesper:fs:* IPC commands)."""
from __future__ import annotations

from pathlib import Path

import pytest

from vesper import App
from vesper.core import fs


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


# ── IPC command registration ──────────────────────────────────────────────────


def test_fs_commands_registered_in_app():
    app = App()
    for cmd in ("vesper:fs:read", "vesper:fs:write", "vesper:fs:exists", "vesper:fs:list"):
        assert cmd in app.registry._commands


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
