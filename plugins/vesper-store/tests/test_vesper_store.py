"""Tests for the vesper-store plugin."""
from __future__ import annotations

import json
import platform
import threading
from pathlib import Path

import pytest

from vesper import App
from vesper_store import Plugin, StorePlugin
from vesper_store.plugin import _default_path


# ── _default_path ─────────────────────────────────────────────────────────────


def test_default_path_contains_app_name():
    p = _default_path("my-app")
    assert "my-app" in str(p)


def test_default_path_ends_with_store_json():
    p = _default_path("my-app")
    assert p.name == "store.json"


def test_default_path_platform_specific():
    p = _default_path("my-app")
    system = platform.system()
    if system == "Windows":
        assert "AppData" in str(p) or "Roaming" in str(p)
    elif system == "Darwin":
        assert "Library" in str(p)
    else:
        assert ".config" in str(p) or "XDG" not in str(p)


def test_default_path_different_names_differ():
    assert _default_path("app-a") != _default_path("app-b")


# ── Constructor ───────────────────────────────────────────────────────────────


def test_custom_path_used_when_provided(tmp_path):
    custom = tmp_path / "custom.json"
    store = StorePlugin(path=str(custom))
    store._set("k", "v")
    assert custom.is_file()


def test_app_name_used_in_default_path():
    store = StorePlugin(app_name="test-unique-app-xyz")
    assert "test-unique-app-xyz" in str(store._path)


# ── Basic get / set ───────────────────────────────────────────────────────────


def test_set_and_get_string(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._set("theme", "dark")
    assert store._get("theme") == "dark"


def test_set_and_get_integer(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._set("count", 42)
    assert store._get("count") == 42


def test_set_and_get_float(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._set("ratio", 3.14)
    assert store._get("ratio") == 3.14


def test_set_and_get_boolean(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._set("enabled", True)
    assert store._get("enabled") is True


def test_set_and_get_list(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._set("tags", ["a", "b", "c"])
    assert store._get("tags") == ["a", "b", "c"]


def test_set_and_get_dict(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._set("config", {"debug": True, "level": 3})
    assert store._get("config") == {"debug": True, "level": 3}


def test_set_and_get_null(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._set("empty", None)
    assert store._get("empty") is None


def test_get_missing_key_returns_none(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    assert store._get("nonexistent") is None


def test_set_overwrites_existing_value(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._set("key", "first")
    store._set("key", "second")
    assert store._get("key") == "second"


# ── has ───────────────────────────────────────────────────────────────────────


def test_has_true_for_existing_key(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._set("x", 1)
    assert store._has("x") is True


def test_has_false_for_missing_key(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    assert store._has("x") is False


def test_has_false_after_delete(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._set("x", 1)
    store._delete("x")
    assert store._has("x") is False


# ── delete ────────────────────────────────────────────────────────────────────


def test_delete_removes_key(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._set("k", "v")
    store._delete("k")
    assert store._get("k") is None


def test_delete_nonexistent_key_is_noop(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._delete("ghost")  # must not raise


def test_delete_does_not_affect_other_keys(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._set("a", 1)
    store._set("b", 2)
    store._delete("a")
    assert store._get("b") == 2


# ── clear ─────────────────────────────────────────────────────────────────────


def test_clear_removes_all_keys(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._set("a", 1)
    store._set("b", 2)
    store._clear()
    assert store._keys() == []


def test_clear_on_empty_store_is_noop(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._clear()
    assert store._keys() == []


def test_clear_allows_new_writes_after(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._set("a", 1)
    store._clear()
    store._set("b", 2)
    assert store._get("b") == 2
    assert store._get("a") is None


# ── keys ──────────────────────────────────────────────────────────────────────


def test_keys_returns_all_keys(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._set("a", 1)
    store._set("b", 2)
    store._set("c", 3)
    assert set(store._keys()) == {"a", "b", "c"}


def test_keys_empty_when_store_empty(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    assert store._keys() == []


def test_keys_does_not_include_deleted(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._set("a", 1)
    store._set("b", 2)
    store._delete("a")
    assert store._keys() == ["b"]


# ── Persistence ───────────────────────────────────────────────────────────────


def test_data_persists_to_disk(tmp_path):
    path = tmp_path / "store.json"
    store = StorePlugin(path=str(path))
    store._set("color", "blue")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["color"] == "blue"


def test_data_survives_new_instance(tmp_path):
    path = str(tmp_path / "store.json")
    s1 = StorePlugin(path=path)
    s1._set("persistent", "yes")

    s2 = StorePlugin(path=path)
    assert s2._get("persistent") == "yes"


def test_creates_parent_directories(tmp_path):
    path = tmp_path / "deep" / "nested" / "store.json"
    store = StorePlugin(path=str(path))
    store._set("k", "v")
    assert path.is_file()


def test_survives_corrupt_json(tmp_path):
    path = tmp_path / "store.json"
    path.write_text("NOT VALID JSON", encoding="utf-8")
    store = StorePlugin(path=str(path))
    assert store._get("any") is None


def test_survives_empty_file(tmp_path):
    path = tmp_path / "store.json"
    path.write_text("", encoding="utf-8")
    store = StorePlugin(path=str(path))
    assert store._get("any") is None


def test_non_ascii_values_roundtrip(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._set("greeting", "こんにちは")
    assert store._get("greeting") == "こんにちは"


# ── Thread safety ─────────────────────────────────────────────────────────────


def test_concurrent_writes_do_not_corrupt(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    errors = []

    def writer(key, value):
        try:
            for _ in range(20):
                store._set(key, value)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(f"k{i}", i)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Thread errors: {errors}"


def test_concurrent_reads_and_writes(tmp_path):
    store = StorePlugin(path=str(tmp_path / "s.json"))
    store._set("shared", 0)
    errors = []

    def reader():
        try:
            for _ in range(30):
                store._get("shared")
        except Exception as e:
            errors.append(e)

    def writer():
        try:
            for i in range(30):
                store._set("shared", i)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=reader) for _ in range(3)]
    threads += [threading.Thread(target=writer) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Thread errors: {errors}"


# ── IPC commands ──────────────────────────────────────────────────────────────


def _app(tmp_path):
    return App(plugins=[StorePlugin(path=str(tmp_path / "s.json"))])


def test_all_commands_registered(tmp_path):
    app = _app(tmp_path)
    expected = {"store:get", "store:set", "store:delete", "store:has", "store:clear", "store:keys"}
    assert expected.issubset(app.registry._commands.keys())


def test_ipc_set_and_get(tmp_path):
    app = _app(tmp_path)
    app.ipc.handle({"id": "1", "command": "store:set", "args": {"key": "lang", "value": "python"}})
    resp = app.ipc.handle({"id": "2", "command": "store:get", "args": {"key": "lang"}})
    assert resp["ok"] is True
    assert resp["result"] == "python"


def test_ipc_get_missing_returns_none(tmp_path):
    app = _app(tmp_path)
    resp = app.ipc.handle({"id": "1", "command": "store:get", "args": {"key": "nope"}})
    assert resp["ok"] is True
    assert resp["result"] is None


def test_ipc_has_true(tmp_path):
    app = _app(tmp_path)
    app.ipc.handle({"id": "1", "command": "store:set", "args": {"key": "x", "value": 1}})
    resp = app.ipc.handle({"id": "2", "command": "store:has", "args": {"key": "x"}})
    assert resp["result"] is True


def test_ipc_has_false(tmp_path):
    app = _app(tmp_path)
    resp = app.ipc.handle({"id": "1", "command": "store:has", "args": {"key": "missing"}})
    assert resp["result"] is False


def test_ipc_delete(tmp_path):
    app = _app(tmp_path)
    app.ipc.handle({"id": "1", "command": "store:set", "args": {"key": "k", "value": "v"}})
    app.ipc.handle({"id": "2", "command": "store:delete", "args": {"key": "k"}})
    resp = app.ipc.handle({"id": "3", "command": "store:get", "args": {"key": "k"}})
    assert resp["result"] is None


def test_ipc_clear(tmp_path):
    app = _app(tmp_path)
    app.ipc.handle({"id": "1", "command": "store:set", "args": {"key": "a", "value": 1}})
    app.ipc.handle({"id": "2", "command": "store:clear", "args": {}})
    resp = app.ipc.handle({"id": "3", "command": "store:keys", "args": {}})
    assert resp["result"] == []


def test_ipc_keys(tmp_path):
    app = _app(tmp_path)
    app.ipc.handle({"id": "1", "command": "store:set", "args": {"key": "a", "value": 1}})
    app.ipc.handle({"id": "2", "command": "store:set", "args": {"key": "b", "value": 2}})
    resp = app.ipc.handle({"id": "3", "command": "store:keys", "args": {}})
    assert set(resp["result"]) == {"a", "b"}


def test_ipc_set_missing_key_arg_returns_error(tmp_path):
    app = _app(tmp_path)
    resp = app.ipc.handle({"id": "1", "command": "store:set", "args": {}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValidationError"


def test_ipc_set_various_value_types(tmp_path):
    app = _app(tmp_path)
    for value in ["string", 42, 3.14, True, [1, 2], {"a": 1}, None]:
        app.ipc.handle({"id": "1", "command": "store:set", "args": {"key": "v", "value": value}})
        resp = app.ipc.handle({"id": "2", "command": "store:get", "args": {"key": "v"}})
        assert resp["result"] == value


# ── SDK path ──────────────────────────────────────────────────────────────────


def test_sdk_path_returns_path():
    p = StorePlugin.sdk_path()
    assert p is not None
    assert isinstance(p, Path)


def test_sdk_path_points_to_js_file():
    p = StorePlugin.sdk_path()
    assert p.name == "vesper-store.js"


def test_sdk_js_file_exists_on_disk():
    p = StorePlugin.sdk_path()
    assert p.is_file()


def test_sdk_js_contains_vesper_store():
    p = StorePlugin.sdk_path()
    content = p.read_text(encoding="utf-8")
    assert "vesper.store" in content


# ── Public API / exports ──────────────────────────────────────────────────────


def test_plugin_alias_is_store_plugin():
    assert Plugin is StorePlugin


def test_store_plugin_is_vesper_plugin():
    from vesper import VesperPlugin
    assert issubclass(StorePlugin, VesperPlugin)
