"""Tests for the vesper-db plugin."""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy", reason="sqlalchemy not installed")

from vesper import App
from vesper_db import DatabasePlugin, Plugin
from vesper_db.plugin import _convert_params


# ── _convert_params ───────────────────────────────────────────────────────────


def test_convert_params_no_placeholders():
    sql, params = _convert_params("SELECT 1", [])
    assert sql == "SELECT 1"
    assert params == {}


def test_convert_params_single_placeholder():
    sql, params = _convert_params("SELECT * FROM t WHERE id = ?", [42])
    assert ":p0" in sql
    assert "?" not in sql
    assert params == {"p0": 42}


def test_convert_params_multiple_placeholders():
    sql, params = _convert_params(
        "INSERT INTO t (a, b) VALUES (?, ?)", ["hello", 99]
    )
    assert ":p0" in sql
    assert ":p1" in sql
    assert "?" not in sql
    assert params["p0"] == "hello"
    assert params["p1"] == 99


def test_convert_params_preserves_sql_structure():
    sql, params = _convert_params(
        "UPDATE t SET x = ? WHERE y = ? AND z = ?", [1, 2, 3]
    )
    assert sql.startswith("UPDATE t SET x = :p0")
    assert params == {"p0": 1, "p1": 2, "p2": 3}


def test_convert_params_empty_list_returns_empty_dict():
    _, params = _convert_params("SELECT 1", [])
    assert params == {}


def test_convert_params_none_value():
    _, params = _convert_params("INSERT INTO t (x) VALUES (?)", [None])
    assert params["p0"] is None


# ── DatabasePlugin constructor ─────────────────────────────────────────────────


def test_constructor_stores_url():
    db = DatabasePlugin(url="sqlite:///:memory:")
    assert db._url == "sqlite:///:memory:"


def test_engine_is_none_before_first_use():
    db = DatabasePlugin(url="sqlite:///:memory:")
    assert db._engine is None


def test_plugin_alias_is_database_plugin():
    assert Plugin is DatabasePlugin


# ── Basic operations (in-memory SQLite) ───────────────────────────────────────


@pytest.fixture
def db():
    plugin = DatabasePlugin(url="sqlite:///:memory:")
    # create a table to use across tests
    plugin._execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)", [])
    return plugin


def test_execute_create_table():
    db = DatabasePlugin(url="sqlite:///:memory:")
    result = db._execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)", [])
    assert "affected" in result


def test_execute_insert_returns_affected(db):
    result = db._execute("INSERT INTO users (name, age) VALUES (?, ?)", ["Alice", 30])
    assert result == {"affected": 1}


def test_query_returns_rows(db):
    db._execute("INSERT INTO users (name, age) VALUES (?, ?)", ["Bob", 25])
    rows = db._query("SELECT name, age FROM users WHERE name = ?", ["Bob"])
    assert len(rows) == 1
    assert rows[0]["name"] == "Bob"
    assert rows[0]["age"] == 25


def test_query_empty_result(db):
    rows = db._query("SELECT * FROM users WHERE id = ?", [9999])
    assert rows == []


def test_query_multiple_rows(db):
    db._execute("INSERT INTO users (name, age) VALUES (?, ?)", ["Ana", 20])
    db._execute("INSERT INTO users (name, age) VALUES (?, ?)", ["Luis", 35])
    rows = db._query("SELECT * FROM users ORDER BY age", [])
    assert len(rows) == 2
    assert rows[0]["name"] == "Ana"
    assert rows[1]["name"] == "Luis"


def test_execute_update(db):
    db._execute("INSERT INTO users (name, age) VALUES (?, ?)", ["Carlos", 40])
    result = db._execute("UPDATE users SET age = ? WHERE name = ?", [41, "Carlos"])
    assert result["affected"] == 1


def test_execute_delete(db):
    db._execute("INSERT INTO users (name, age) VALUES (?, ?)", ["Delete Me", 1])
    result = db._execute("DELETE FROM users WHERE name = ?", ["Delete Me"])
    assert result["affected"] == 1


def test_query_no_params(db):
    db._execute("INSERT INTO users (name, age) VALUES (?, ?)", ["Solo", 50])
    rows = db._query("SELECT COUNT(*) as cnt FROM users", [])
    assert rows[0]["cnt"] == 1


def test_query_returns_dicts_with_column_names(db):
    db._execute("INSERT INTO users (name, age) VALUES (?, ?)", ["DictTest", 10])
    rows = db._query("SELECT name, age FROM users WHERE name = ?", ["DictTest"])
    assert isinstance(rows[0], dict)
    assert "name" in rows[0]
    assert "age" in rows[0]


# ── Transaction ───────────────────────────────────────────────────────────────


def test_transaction_commits_all_statements(db):
    result = db._transaction([
        {"sql": "INSERT INTO users (name, age) VALUES (?, ?)", "params": ["TxA", 1]},
        {"sql": "INSERT INTO users (name, age) VALUES (?, ?)", "params": ["TxB", 2]},
    ])
    rows = db._query("SELECT * FROM users ORDER BY name", [])
    assert len(rows) == 2
    assert result["affected"] == 2


def test_transaction_rolls_back_on_error(db):
    db._execute("INSERT INTO users (name, age) VALUES (?, ?)", ["Before", 1])
    with pytest.raises(Exception):
        db._transaction([
            {"sql": "INSERT INTO users (name, age) VALUES (?, ?)", "params": ["Good", 2]},
            {"sql": "INVALID SQL ;;;", "params": []},
        ])
    # "Good" should NOT be committed
    rows = db._query("SELECT * FROM users WHERE name = ?", ["Good"])
    assert rows == []


def test_transaction_empty_statements(db):
    result = db._transaction([])
    assert result == {"affected": 0}


def test_transaction_without_params_key(db):
    result = db._transaction([
        {"sql": "INSERT INTO users (name, age) VALUES ('NoParams', 99)"},
    ])
    rows = db._query("SELECT * FROM users WHERE name = ?", ["NoParams"])
    assert len(rows) == 1


# ── IPC integration ───────────────────────────────────────────────────────────


@pytest.fixture
def app():
    a = App(plugins=[DatabasePlugin(url="sqlite:///:memory:")])
    a.ipc.handle({
        "id": "setup",
        "command": "db:execute",
        "args": {"sql": "CREATE TABLE items (id INTEGER PRIMARY KEY, label TEXT)", "params": []},
    })
    return a


def test_ipc_commands_registered(app):
    assert "db:query" in app.registry._commands
    assert "db:execute" in app.registry._commands
    assert "db:transaction" in app.registry._commands


def test_ipc_execute_insert(app):
    resp = app.ipc.handle({
        "id": "1",
        "command": "db:execute",
        "args": {"sql": "INSERT INTO items (label) VALUES (?)", "params": ["hello"]},
    })
    assert resp["ok"] is True
    assert resp["result"]["affected"] == 1


def test_ipc_query_select(app):
    app.ipc.handle({
        "id": "1",
        "command": "db:execute",
        "args": {"sql": "INSERT INTO items (label) VALUES (?)", "params": ["ipc_item"]},
    })
    resp = app.ipc.handle({
        "id": "2",
        "command": "db:query",
        "args": {"sql": "SELECT label FROM items WHERE label = ?", "params": ["ipc_item"]},
    })
    assert resp["ok"] is True
    assert resp["result"][0]["label"] == "ipc_item"


def test_ipc_transaction(app):
    resp = app.ipc.handle({
        "id": "1",
        "command": "db:transaction",
        "args": {
            "statements": [
                {"sql": "INSERT INTO items (label) VALUES (?)", "params": ["tx1"]},
                {"sql": "INSERT INTO items (label) VALUES (?)", "params": ["tx2"]},
            ]
        },
    })
    assert resp["ok"] is True
    assert resp["result"]["affected"] == 2


def test_ipc_execute_missing_sql_arg(app):
    resp = app.ipc.handle({
        "id": "1",
        "command": "db:execute",
        "args": {},
    })
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValidationError"


def test_ipc_query_missing_sql_arg(app):
    resp = app.ipc.handle({
        "id": "1",
        "command": "db:query",
        "args": {},
    })
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValidationError"


def test_ipc_transaction_missing_statements_arg(app):
    resp = app.ipc.handle({
        "id": "1",
        "command": "db:transaction",
        "args": {},
    })
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValidationError"


def test_ipc_query_returns_empty_list_on_no_rows(app):
    resp = app.ipc.handle({
        "id": "1",
        "command": "db:query",
        "args": {"sql": "SELECT * FROM items WHERE id = ?", "params": [9999]},
    })
    assert resp["ok"] is True
    assert resp["result"] == []


def test_ipc_params_default_to_empty_list(app):
    resp = app.ipc.handle({
        "id": "1",
        "command": "db:query",
        "args": {"sql": "SELECT COUNT(*) as cnt FROM items"},
    })
    assert resp["ok"] is True
    assert isinstance(resp["result"], list)


# ── Lazy engine init ───────────────────────────────────────────────────────────


def test_engine_created_on_first_operation():
    db = DatabasePlugin(url="sqlite:///:memory:")
    assert db._engine is None
    db._execute("CREATE TABLE t (x INT)", [])
    assert db._engine is not None


def test_engine_reused_across_calls():
    db = DatabasePlugin(url="sqlite:///:memory:")
    db._execute("CREATE TABLE t (x INT)", [])
    engine1 = db._engine
    db._query("SELECT * FROM t", [])
    engine2 = db._engine
    assert engine1 is engine2


# ── Thread safety ─────────────────────────────────────────────────────────────


def test_concurrent_inserts_do_not_corrupt():
    db = DatabasePlugin(url="sqlite:///:memory:")
    db._execute("CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT)", [])
    errors = []

    def insert(val):
        try:
            for _ in range(10):
                db._execute("INSERT INTO t (val) VALUES (?)", [val])
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=insert, args=(f"v{i}",)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Thread errors: {errors}"
    rows = db._query("SELECT COUNT(*) as cnt FROM t", [])
    assert rows[0]["cnt"] == 50


def test_engine_init_thread_safety():
    """Two threads calling _get_engine() simultaneously should not double-init."""
    db = DatabasePlugin(url="sqlite:///:memory:")
    engines = []
    errors = []

    def get_engine():
        try:
            e = db._get_engine()
            engines.append(id(e))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=get_engine) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    # All threads should get the same engine instance
    assert len(set(engines)) == 1


# ── File-based SQLite ─────────────────────────────────────────────────────────


def test_file_based_sqlite_persists(tmp_path):
    db_path = tmp_path / "test.db"
    url = f"sqlite:///{db_path}"

    db1 = DatabasePlugin(url=url)
    db1._execute("CREATE TABLE t (val TEXT)", [])
    db1._execute("INSERT INTO t VALUES (?)", ["persisted"])

    db2 = DatabasePlugin(url=url)
    rows = db2._query("SELECT * FROM t", [])
    assert rows[0]["val"] == "persisted"


# ── SDK path ──────────────────────────────────────────────────────────────────


def test_sdk_path_returns_path():
    p = DatabasePlugin.sdk_path()
    assert p is not None
    assert isinstance(p, Path)


def test_sdk_path_points_to_js_file():
    p = DatabasePlugin.sdk_path()
    assert p.name == "vesper-db.js"


def test_sdk_js_file_exists():
    p = DatabasePlugin.sdk_path()
    assert p.is_file()


def test_sdk_js_contains_vesper_db():
    p = DatabasePlugin.sdk_path()
    content = p.read_text(encoding="utf-8")
    assert "vesper.db" in content


def test_sdk_js_exposes_query():
    content = DatabasePlugin.sdk_path().read_text(encoding="utf-8")
    assert "query" in content


def test_sdk_js_exposes_execute():
    content = DatabasePlugin.sdk_path().read_text(encoding="utf-8")
    assert "execute" in content


def test_sdk_js_exposes_transaction():
    content = DatabasePlugin.sdk_path().read_text(encoding="utf-8")
    assert "transaction" in content


# ── Public API ────────────────────────────────────────────────────────────────


def test_database_plugin_is_vesper_plugin():
    from vesper import VesperPlugin
    assert issubclass(DatabasePlugin, VesperPlugin)


def test_plugin_alias_exported():
    from vesper_db import Plugin
    assert Plugin is DatabasePlugin
