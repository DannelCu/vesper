"""Tests for the vesper-store plugin."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vesper import App
from vesper_store import StorePlugin
from vesper_store.plugin import _default_path


# ── _default_path ─────────────────────────────────────────────────────────────


def test_default_path_contains_app_name():
    p = _default_path("my-app")
    assert "my-app" in str(p)


def test_default_path_ends_with_store_json():
    p = _default_path("my-app")
    assert p.name == "store.json"


# ── StorePlugin internal operations ──────────────────────────────────────────


def test_store_set_and_get(tmp_path):
    store = StorePlugin(path=str(tmp_path / "store.json"))
    store._set("theme", "dark")
    assert store._get("theme") == "dark"


def test_store_get_missing_key_returns_none(tmp_path):
    store = StorePlugin(path=str(tmp_path / "store.json"))
    assert store._get("missing") is None


def test_store_has_true_when_key_exists(tmp_path):
    store = StorePlugin(path=str(tmp_path / "store.json"))
    store._set("x", 1)
    assert store._has("x") is True


def test_store_has_false_when_key_missing(tmp_path):
    store = StorePlugin(path=str(tmp_path / "store.json"))
    assert store._has("missing") is False


def test_store_delete_removes_key(tmp_path):
    store = StorePlugin(path=str(tmp_path / "store.json"))
    store._set("key", "val")
    store._delete("key")
    assert store._get("key") is None


def test_store_delete_nonexistent_key_is_noop(tmp_path):
    store = StorePlugin(path=str(tmp_path / "store.json"))
    store._delete("ghost")  # should not raise


def test_store_clear_removes_all_keys(tmp_path):
    store = StorePlugin(path=str(tmp_path / "store.json"))
    store._set("a", 1)
    store._set("b", 2)
    store._clear()
    assert store._keys() == []


def test_store_keys_returns_all_keys(tmp_path):
    store = StorePlugin(path=str(tmp_path / "store.json"))
    store._set("a", 1)
    store._set("b", 2)
    assert set(store._keys()) == {"a", "b"}


def test_store_persists_to_disk(tmp_path):
    path = tmp_path / "store.json"
    store = StorePlugin(path=str(path))
    store._set("color", "blue")

    data = json.loads(path.read_text())
    assert data["color"] == "blue"


def test_store_creates_parent_dirs(tmp_path):
    path = tmp_path / "deep" / "nested" / "store.json"
    store = StorePlugin(path=str(path))
    store._set("k", "v")
    assert path.is_file()


def test_store_survives_corrupt_json(tmp_path):
    path = tmp_path / "store.json"
    path.write_text("NOT JSON")
    store = StorePlugin(path=str(path))
    assert store._get("key") is None


def test_store_accepts_various_value_types(tmp_path):
    store = StorePlugin(path=str(tmp_path / "store.json"))
    store._set("string", "hello")
    store._set("number", 42)
    store._set("float", 3.14)
    store._set("bool", True)
    store._set("list", [1, 2, 3])
    store._set("dict", {"nested": True})
    store._set("null", None)

    assert store._get("string") == "hello"
    assert store._get("number") == 42
    assert store._get("float") == 3.14
    assert store._get("bool") is True
    assert store._get("list") == [1, 2, 3]
    assert store._get("dict") == {"nested": True}
    assert store._get("null") is None


# ── Plugin registration + IPC ─────────────────────────────────────────────────


def test_store_commands_registered_in_app(tmp_path):
    app = App(plugins=[StorePlugin(path=str(tmp_path / "s.json"))])
    for cmd in ("store:get", "store:set", "store:delete", "store:has", "store:clear", "store:keys"):
        assert cmd in app.registry._commands


def test_store_set_and_get_via_ipc(tmp_path):
    app = App(plugins=[StorePlugin(path=str(tmp_path / "s.json"))])

    app.ipc.handle({"id": "1", "command": "store:set", "args": {"key": "lang", "value": "python"}})
    resp = app.ipc.handle({"id": "2", "command": "store:get", "args": {"key": "lang"}})

    assert resp["ok"] is True
    assert resp["result"] == "python"


def test_store_has_via_ipc(tmp_path):
    app = App(plugins=[StorePlugin(path=str(tmp_path / "s.json"))])
    app.ipc.handle({"id": "1", "command": "store:set", "args": {"key": "x", "value": 1}})

    resp = app.ipc.handle({"id": "2", "command": "store:has", "args": {"key": "x"}})
    assert resp["result"] is True

    resp2 = app.ipc.handle({"id": "3", "command": "store:has", "args": {"key": "missing"}})
    assert resp2["result"] is False


def test_store_delete_via_ipc(tmp_path):
    app = App(plugins=[StorePlugin(path=str(tmp_path / "s.json"))])
    app.ipc.handle({"id": "1", "command": "store:set", "args": {"key": "k", "value": "v"}})
    app.ipc.handle({"id": "2", "command": "store:delete", "args": {"key": "k"}})

    resp = app.ipc.handle({"id": "3", "command": "store:get", "args": {"key": "k"}})
    assert resp["result"] is None


def test_store_clear_via_ipc(tmp_path):
    app = App(plugins=[StorePlugin(path=str(tmp_path / "s.json"))])
    app.ipc.handle({"id": "1", "command": "store:set", "args": {"key": "a", "value": 1}})
    app.ipc.handle({"id": "2", "command": "store:clear", "args": {}})

    resp = app.ipc.handle({"id": "3", "command": "store:keys", "args": {}})
    assert resp["result"] == []


def test_store_keys_via_ipc(tmp_path):
    app = App(plugins=[StorePlugin(path=str(tmp_path / "s.json"))])
    app.ipc.handle({"id": "1", "command": "store:set", "args": {"key": "a", "value": 1}})
    app.ipc.handle({"id": "2", "command": "store:set", "args": {"key": "b", "value": 2}})

    resp = app.ipc.handle({"id": "3", "command": "store:keys", "args": {}})
    assert set(resp["result"]) == {"a", "b"}


# ── sdk_path ──────────────────────────────────────────────────────────────────


def test_store_sdk_path_returns_path():
    p = StorePlugin.sdk_path()
    assert p is not None
    assert p.name == "vesper-store.js"


def test_store_sdk_js_file_exists():
    p = StorePlugin.sdk_path()
    assert p.is_file()


# ── Plugin alias convention ───────────────────────────────────────────────────


def test_store_plugin_exported_as_plugin():
    from vesper_store import Plugin
    assert Plugin is StorePlugin
