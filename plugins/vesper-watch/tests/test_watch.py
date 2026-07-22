"""Tests for vesper-watch — real watchdog observers over a tmpdir."""
from __future__ import annotations

import time

import pytest

from vesper import App
from vesper_watch import WatchPlugin


def _collector(app):
    events = []
    app.window.emit = lambda event, payload: events.append((event, payload))
    return events


def _wait_for(events, kind, path_fragment, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for name, payload in list(events):
            if name == "fs:changed" and payload["kind"] == kind and path_fragment in payload["path"]:
                return payload
        time.sleep(0.05)
    raise AssertionError(f"No {kind!r} event for {path_fragment!r} in {events}")


def test_commands_registered():
    app = App(plugins=[WatchPlugin()])
    try:
        assert "vesper:fs:watch" in app.registry._commands
        assert "vesper:fs:unwatch" in app.registry._commands
    finally:
        app.ipc.close()


def test_create_modify_delete_emit_events(tmp_path):
    plugin = WatchPlugin(debounce=0.0)
    app = App(plugins=[plugin])
    events = _collector(app)
    try:
        resp = app.ipc.handle({
            "id": "1", "command": "vesper:fs:watch",
            "args": {"path": str(tmp_path)},
        })
        assert resp["ok"] is True
        watch_id = resp["result"]

        target = tmp_path / "note.txt"
        target.write_text("hello")
        created = _wait_for(events, "created", "note.txt")
        assert created["id"] == watch_id
        assert created["is_dir"] is False

        target.write_text("hello again")
        _wait_for(events, "modified", "note.txt")

        target.unlink()
        _wait_for(events, "deleted", "note.txt")
    finally:
        plugin.stop_all()
        app.ipc.close()


def test_move_carries_dest_path(tmp_path):
    plugin = WatchPlugin(debounce=0.0)
    app = App(plugins=[plugin])
    events = _collector(app)
    try:
        app.ipc.handle({"id": "1", "command": "vesper:fs:watch", "args": {"path": str(tmp_path)}})

        src = tmp_path / "old.txt"
        src.write_text("x")
        _wait_for(events, "created", "old.txt")

        src.rename(tmp_path / "new.txt")
        moved = _wait_for(events, "moved", "old.txt")
        assert moved["dest_path"].endswith("new.txt")
    finally:
        plugin.stop_all()
        app.ipc.close()


def test_unwatch_stops_events(tmp_path):
    plugin = WatchPlugin(debounce=0.0)
    app = App(plugins=[plugin])
    events = _collector(app)
    try:
        resp = app.ipc.handle({"id": "1", "command": "vesper:fs:watch", "args": {"path": str(tmp_path)}})
        watch_id = resp["result"]

        assert app.ipc.handle({
            "id": "2", "command": "vesper:fs:unwatch", "args": {"id": watch_id},
        })["result"] is True

        (tmp_path / "after.txt").write_text("x")
        time.sleep(0.4)
        assert not any(p["path"].endswith("after.txt") for _, p in events)
    finally:
        plugin.stop_all()
        app.ipc.close()


def test_unwatch_unknown_id_is_false(tmp_path):
    plugin = WatchPlugin()
    app = App(plugins=[plugin])
    try:
        resp = app.ipc.handle({"id": "1", "command": "vesper:fs:unwatch", "args": {"id": 999}})
        assert resp["result"] is False
    finally:
        app.ipc.close()


def test_watch_outside_fs_scope_is_rejected(tmp_path):
    inside = tmp_path / "inside"
    outside = tmp_path / "outside"
    inside.mkdir()
    outside.mkdir()

    plugin = WatchPlugin()
    app = App(plugins=[plugin], fs_scope=[str(inside)])
    try:
        resp = app.ipc.handle({
            "id": "1", "command": "vesper:fs:watch", "args": {"path": str(outside)},
        })
        assert resp["ok"] is False
        assert resp["error"]["type"] == "FsScopeError"
        assert plugin._observers == {}
    finally:
        app.ipc.close()


def test_missing_path_is_rejected(tmp_path):
    plugin = WatchPlugin()
    app = App(plugins=[plugin])
    try:
        resp = app.ipc.handle({
            "id": "1", "command": "vesper:fs:watch", "args": {"path": str(tmp_path / "nope")},
        })
        assert resp["ok"] is False
        assert resp["error"]["type"] == "FileNotFoundError"
    finally:
        app.ipc.close()


def test_debounce_collapses_bursts(tmp_path):
    plugin = WatchPlugin()
    app = App(plugins=[plugin])
    events = _collector(app)
    try:
        app.ipc.handle({
            "id": "1", "command": "vesper:fs:watch",
            "args": {"path": str(tmp_path), "debounce": 5.0},
        })

        target = tmp_path / "burst.txt"
        target.write_text("1")
        _wait_for(events, "created", "burst.txt")

        for i in range(5):
            target.write_text(f"content {i}")
        time.sleep(0.5)

        modified = [p for _, p in events if p["kind"] == "modified" and p["path"].endswith("burst.txt")]
        assert len(modified) <= 1
    finally:
        plugin.stop_all()
        app.ipc.close()


def test_stop_all_leaves_no_observers(tmp_path):
    plugin = WatchPlugin()
    app = App(plugins=[plugin])
    try:
        app.ipc.handle({"id": "1", "command": "vesper:fs:watch", "args": {"path": str(tmp_path)}})
        app.ipc.handle({"id": "2", "command": "vesper:fs:watch", "args": {"path": str(tmp_path)}})
        assert len(plugin._observers) == 2

        plugin.stop_all()
        assert plugin._observers == {}
    finally:
        app.ipc.close()


def test_plugin_alias():
    from vesper_watch import Plugin
    from vesper_watch.plugin import WatchPlugin as Direct
    assert Plugin is Direct


def test_sdk_path_exists():
    path = WatchPlugin.sdk_path()
    assert path is not None
    assert path.name == "vesper-watch.js"
