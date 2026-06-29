"""Tests for the vesper-mongodb plugin."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pymongo", reason="pymongo not installed")
pytest.importorskip("mongomock", reason="mongomock not installed")

from vesper import App, Controller, Injectable, Module, command
from vesper.core.module import Container
from vesper_mongodb import MongoDatabase, MongoPlugin, Plugin
from vesper_mongodb.database import _serialize


# ── Plugin basics ─────────────────────────────────────────────────────────────


def test_plugin_alias_is_mongo_plugin():
    assert Plugin is MongoPlugin


def test_mongo_plugin_is_vesper_plugin():
    from vesper import VesperPlugin
    assert issubclass(MongoPlugin, VesperPlugin)


def test_sdk_path_returns_path():
    p = MongoPlugin.sdk_path()
    assert p is not None
    assert isinstance(p, Path)


def test_sdk_path_points_to_js_file():
    assert MongoPlugin.sdk_path().name == "vesper-mongodb.js"


def test_sdk_js_file_exists():
    assert MongoPlugin.sdk_path().is_file()


def test_sdk_js_contains_vesper_mongo():
    content = MongoPlugin.sdk_path().read_text(encoding="utf-8")
    assert "vesper.mongo" in content


def test_sdk_js_exposes_all_methods():
    content = MongoPlugin.sdk_path().read_text(encoding="utf-8")
    for method in ("find", "findOne", "insertOne", "insertMany",
                   "updateOne", "updateMany", "deleteOne", "deleteMany", "count"):
        assert method in content


def test_plugin_default_uri_and_database():
    plugin = MongoPlugin()
    assert plugin._uri == "mongodb://localhost:27017"
    assert plugin._database == "vesper-app"


def test_plugin_custom_uri_and_database():
    plugin = MongoPlugin(uri="mongodb://remote:27017", database="mydb")
    assert plugin._uri == "mongodb://remote:27017"
    assert plugin._database == "mydb"


# ── DI registration ───────────────────────────────────────────────────────────


def test_plugin_registers_mongo_database_globally():
    App(plugins=[MongoPlugin(database="test")])
    assert MongoDatabase in Container._global


def test_global_mongo_database_is_database_instance():
    import mongomock
    App(plugins=[MongoPlugin(database="test")])
    db = Container._global[MongoDatabase]
    assert isinstance(db, mongomock.Database)


def test_plugin_registers_all_ipc_commands():
    app = App(plugins=[MongoPlugin(database="test")])
    expected = (
        "mongo:find", "mongo:find_one", "mongo:insert_one", "mongo:insert_many",
        "mongo:update_one", "mongo:update_many", "mongo:delete_one",
        "mongo:delete_many", "mongo:count",
    )
    for cmd in expected:
        assert cmd in app.registry._commands


# ── _serialize ────────────────────────────────────────────────────────────────


def test_serialize_objectid_to_string():
    from bson import ObjectId
    oid = ObjectId()
    assert _serialize(oid) == str(oid)


def test_serialize_dict_with_objectid():
    from bson import ObjectId
    oid = ObjectId()
    doc = {"_id": oid, "name": "Alice"}
    result = _serialize(doc)
    assert result == {"_id": str(oid), "name": "Alice"}


def test_serialize_nested_dict():
    from bson import ObjectId
    oid = ObjectId()
    doc = {"user": {"_id": oid, "active": True}}
    result = _serialize(doc)
    assert result["user"]["_id"] == str(oid)
    assert result["user"]["active"] is True


def test_serialize_list_of_docs():
    from bson import ObjectId
    oid1, oid2 = ObjectId(), ObjectId()
    docs = [{"_id": oid1, "val": 1}, {"_id": oid2, "val": 2}]
    result = _serialize(docs)
    assert result[0]["_id"] == str(oid1)
    assert result[1]["_id"] == str(oid2)


def test_serialize_none_returns_none():
    assert _serialize(None) is None


def test_serialize_primitives_unchanged():
    assert _serialize(42) == 42
    assert _serialize("hello") == "hello"
    assert _serialize(True) is True
    assert _serialize(3.14) == 3.14


def test_serialize_empty_dict():
    assert _serialize({}) == {}


def test_serialize_empty_list():
    assert _serialize([]) == []


# ── IPC: insert_one ───────────────────────────────────────────────────────────


def _app():
    return App(plugins=[MongoPlugin(database="test")])


def test_ipc_insert_one_returns_id():
    app = _app()
    resp = app.ipc.handle({
        "id": "1", "command": "mongo:insert_one",
        "args": {"collection": "users", "document": {"name": "Alice"}},
    })
    assert resp["ok"] is True
    assert "id" in resp["result"]
    assert isinstance(resp["result"]["id"], str)
    assert len(resp["result"]["id"]) == 24  # ObjectId hex string


def test_ipc_insert_one_id_is_string_not_objectid():
    app = _app()
    resp = app.ipc.handle({
        "id": "1", "command": "mongo:insert_one",
        "args": {"collection": "users", "document": {"name": "Bob"}},
    })
    assert isinstance(resp["result"]["id"], str)


# ── IPC: find ─────────────────────────────────────────────────────────────────


def test_ipc_find_returns_inserted_documents():
    app = _app()
    app.ipc.handle({"id": "1", "command": "mongo:insert_one",
                    "args": {"collection": "items", "document": {"x": 1}}})
    app.ipc.handle({"id": "2", "command": "mongo:insert_one",
                    "args": {"collection": "items", "document": {"x": 2}}})
    resp = app.ipc.handle({"id": "3", "command": "mongo:find",
                           "args": {"collection": "items"}})
    assert resp["ok"] is True
    assert len(resp["result"]) == 2


def test_ipc_find_with_filter():
    app = _app()
    app.ipc.handle({"id": "1", "command": "mongo:insert_one",
                    "args": {"collection": "items", "document": {"role": "admin"}}})
    app.ipc.handle({"id": "2", "command": "mongo:insert_one",
                    "args": {"collection": "items", "document": {"role": "user"}}})
    resp = app.ipc.handle({
        "id": "3", "command": "mongo:find",
        "args": {"collection": "items", "filter": {"role": "admin"}},
    })
    assert len(resp["result"]) == 1
    assert resp["result"][0]["role"] == "admin"


def test_ipc_find_with_limit():
    app = _app()
    for i in range(5):
        app.ipc.handle({"id": str(i), "command": "mongo:insert_one",
                        "args": {"collection": "items", "document": {"n": i}}})
    resp = app.ipc.handle({
        "id": "10", "command": "mongo:find",
        "args": {"collection": "items", "limit": 3},
    })
    assert len(resp["result"]) == 3


def test_ipc_find_empty_collection_returns_empty_list():
    app = _app()
    resp = app.ipc.handle({"id": "1", "command": "mongo:find",
                           "args": {"collection": "empty"}})
    assert resp["ok"] is True
    assert resp["result"] == []


def test_ipc_find_serializes_objectid():
    app = _app()
    app.ipc.handle({"id": "1", "command": "mongo:insert_one",
                    "args": {"collection": "items", "document": {"v": 1}}})
    resp = app.ipc.handle({"id": "2", "command": "mongo:find",
                           "args": {"collection": "items"}})
    doc = resp["result"][0]
    assert isinstance(doc["_id"], str)


# ── IPC: find_one ─────────────────────────────────────────────────────────────


def test_ipc_find_one_returns_matching_document():
    app = _app()
    app.ipc.handle({"id": "1", "command": "mongo:insert_one",
                    "args": {"collection": "u", "document": {"name": "Alice"}}})
    resp = app.ipc.handle({
        "id": "2", "command": "mongo:find_one",
        "args": {"collection": "u", "filter": {"name": "Alice"}},
    })
    assert resp["ok"] is True
    assert resp["result"]["name"] == "Alice"


def test_ipc_find_one_missing_returns_none():
    app = _app()
    resp = app.ipc.handle({
        "id": "1", "command": "mongo:find_one",
        "args": {"collection": "u", "filter": {"name": "Ghost"}},
    })
    assert resp["ok"] is True
    assert resp["result"] is None


def test_ipc_find_one_serializes_objectid():
    app = _app()
    app.ipc.handle({"id": "1", "command": "mongo:insert_one",
                    "args": {"collection": "u", "document": {"name": "Carol"}}})
    resp = app.ipc.handle({"id": "2", "command": "mongo:find_one",
                           "args": {"collection": "u"}})
    assert isinstance(resp["result"]["_id"], str)


# ── IPC: insert_many ──────────────────────────────────────────────────────────


def test_ipc_insert_many_returns_ids():
    app = _app()
    resp = app.ipc.handle({
        "id": "1", "command": "mongo:insert_many",
        "args": {"collection": "items", "documents": [{"n": 1}, {"n": 2}, {"n": 3}]},
    })
    assert resp["ok"] is True
    assert len(resp["result"]["ids"]) == 3
    for id_ in resp["result"]["ids"]:
        assert isinstance(id_, str)


def test_ipc_insert_many_are_findable():
    app = _app()
    app.ipc.handle({
        "id": "1", "command": "mongo:insert_many",
        "args": {"collection": "items", "documents": [{"tag": "x"}, {"tag": "x"}]},
    })
    resp = app.ipc.handle({
        "id": "2", "command": "mongo:find",
        "args": {"collection": "items", "filter": {"tag": "x"}},
    })
    assert len(resp["result"]) == 2


# ── IPC: update_one ───────────────────────────────────────────────────────────


def test_ipc_update_one_modifies_document():
    app = _app()
    app.ipc.handle({"id": "1", "command": "mongo:insert_one",
                    "args": {"collection": "u", "document": {"name": "Alice", "active": True}}})
    app.ipc.handle({
        "id": "2", "command": "mongo:update_one",
        "args": {"collection": "u", "filter": {"name": "Alice"},
                 "update": {"$set": {"active": False}}},
    })
    resp = app.ipc.handle({
        "id": "3", "command": "mongo:find_one",
        "args": {"collection": "u", "filter": {"name": "Alice"}},
    })
    assert resp["result"]["active"] is False


def test_ipc_update_one_returns_counts():
    app = _app()
    app.ipc.handle({"id": "1", "command": "mongo:insert_one",
                    "args": {"collection": "u", "document": {"name": "Bob"}}})
    resp = app.ipc.handle({
        "id": "2", "command": "mongo:update_one",
        "args": {"collection": "u", "filter": {"name": "Bob"},
                 "update": {"$set": {"name": "Robert"}}},
    })
    assert resp["result"]["matched"] == 1
    assert resp["result"]["modified"] == 1


def test_ipc_update_one_no_match_returns_zero():
    app = _app()
    resp = app.ipc.handle({
        "id": "1", "command": "mongo:update_one",
        "args": {"collection": "u", "filter": {"name": "Nobody"},
                 "update": {"$set": {"x": 1}}},
    })
    assert resp["result"]["matched"] == 0
    assert resp["result"]["modified"] == 0


# ── IPC: update_many ─────────────────────────────────────────────────────────


def test_ipc_update_many_modifies_all_matching():
    app = _app()
    for i in range(3):
        app.ipc.handle({"id": str(i), "command": "mongo:insert_one",
                        "args": {"collection": "items", "document": {"status": "new"}}})
    resp = app.ipc.handle({
        "id": "10", "command": "mongo:update_many",
        "args": {"collection": "items", "filter": {"status": "new"},
                 "update": {"$set": {"status": "processed"}}},
    })
    assert resp["result"]["matched"] == 3
    assert resp["result"]["modified"] == 3

    count_resp = app.ipc.handle({
        "id": "11", "command": "mongo:count",
        "args": {"collection": "items", "filter": {"status": "processed"}},
    })
    assert count_resp["result"] == 3


# ── IPC: delete_one ───────────────────────────────────────────────────────────


def test_ipc_delete_one_removes_document():
    app = _app()
    app.ipc.handle({"id": "1", "command": "mongo:insert_one",
                    "args": {"collection": "u", "document": {"name": "Alice"}}})
    app.ipc.handle({"id": "2", "command": "mongo:insert_one",
                    "args": {"collection": "u", "document": {"name": "Bob"}}})
    resp = app.ipc.handle({
        "id": "3", "command": "mongo:delete_one",
        "args": {"collection": "u", "filter": {"name": "Alice"}},
    })
    assert resp["result"]["deleted"] == 1
    count = app.ipc.handle({"id": "4", "command": "mongo:count",
                            "args": {"collection": "u"}})
    assert count["result"] == 1


def test_ipc_delete_one_no_match_returns_zero():
    app = _app()
    resp = app.ipc.handle({
        "id": "1", "command": "mongo:delete_one",
        "args": {"collection": "u", "filter": {"name": "Nobody"}},
    })
    assert resp["result"]["deleted"] == 0


# ── IPC: delete_many ─────────────────────────────────────────────────────────


def test_ipc_delete_many_removes_all_matching():
    app = _app()
    for i in range(4):
        app.ipc.handle({"id": str(i), "command": "mongo:insert_one",
                        "args": {"collection": "items", "document": {"tag": "old"}}})
    resp = app.ipc.handle({
        "id": "10", "command": "mongo:delete_many",
        "args": {"collection": "items", "filter": {"tag": "old"}},
    })
    assert resp["result"]["deleted"] == 4
    count = app.ipc.handle({"id": "11", "command": "mongo:count",
                            "args": {"collection": "items"}})
    assert count["result"] == 0


# ── IPC: count ────────────────────────────────────────────────────────────────


def test_ipc_count_empty_collection():
    app = _app()
    resp = app.ipc.handle({"id": "1", "command": "mongo:count",
                           "args": {"collection": "empty"}})
    assert resp["ok"] is True
    assert resp["result"] == 0


def test_ipc_count_all_documents():
    app = _app()
    for i in range(5):
        app.ipc.handle({"id": str(i), "command": "mongo:insert_one",
                        "args": {"collection": "items", "document": {"n": i}}})
    resp = app.ipc.handle({"id": "10", "command": "mongo:count",
                           "args": {"collection": "items"}})
    assert resp["result"] == 5


def test_ipc_count_with_filter():
    app = _app()
    for role in ("admin", "admin", "user"):
        app.ipc.handle({"id": role, "command": "mongo:insert_one",
                        "args": {"collection": "users", "document": {"role": role}}})
    resp = app.ipc.handle({
        "id": "10", "command": "mongo:count",
        "args": {"collection": "users", "filter": {"role": "admin"}},
    })
    assert resp["result"] == 2


# ── Validation errors ─────────────────────────────────────────────────────────


def test_ipc_find_missing_collection():
    app = _app()
    resp = app.ipc.handle({"id": "1", "command": "mongo:find", "args": {}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValidationError"


def test_ipc_insert_one_missing_collection():
    app = _app()
    resp = app.ipc.handle({"id": "1", "command": "mongo:insert_one",
                           "args": {"document": {"x": 1}}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValidationError"


def test_ipc_insert_one_missing_document():
    app = _app()
    resp = app.ipc.handle({"id": "1", "command": "mongo:insert_one",
                           "args": {"collection": "items"}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValidationError"


def test_ipc_update_one_missing_filter():
    app = _app()
    resp = app.ipc.handle({
        "id": "1", "command": "mongo:update_one",
        "args": {"collection": "u", "update": {"$set": {"x": 1}}},
    })
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValidationError"


def test_ipc_delete_one_missing_filter():
    app = _app()
    resp = app.ipc.handle({"id": "1", "command": "mongo:delete_one",
                           "args": {"collection": "u"}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValidationError"


# ── DI injection ─────────────────────────────────────────────────────────────


def test_mongo_database_injected_into_service():
    import mongomock

    @Injectable()
    class ProductsService:
        def __init__(self, db: MongoDatabase):
            self.db = db

    App(plugins=[MongoPlugin(database="test")])
    container = Container([ProductsService])
    service = container.resolve(ProductsService)
    assert isinstance(service.db, mongomock.Database)


def test_di_service_can_query_via_injected_db():
    @Injectable()
    class ProductsService:
        def __init__(self, db: MongoDatabase):
            self._col = db["products"]

        def add(self, name: str, price: float) -> str:
            result = self._col.insert_one({"name": name, "price": price})
            return str(result.inserted_id)

        def all(self) -> list:
            return [{"name": d["name"], "price": d["price"]}
                    for d in self._col.find()]

    App(plugins=[MongoPlugin(database="test")])
    container = Container([ProductsService])
    svc = container.resolve(ProductsService)

    svc.add("Widget", 9.99)
    svc.add("Gadget", 19.99)
    products = svc.all()

    assert len(products) == 2
    assert products[0]["name"] == "Widget"


# ── Full module integration ────────────────────────────────────────────────────


@Injectable()
class NoteService:
    def __init__(self, db: MongoDatabase):
        self._col = db["notes"]

    def create(self, title: str, body: str) -> dict:
        result = self._col.insert_one({"title": title, "body": body})
        return {"id": str(result.inserted_id)}

    def list_all(self) -> list:
        return [{"title": d["title"], "body": d["body"]}
                for d in self._col.find()]

    def delete(self, title: str) -> int:
        result = self._col.delete_one({"title": title})
        return result.deleted_count


@Controller("notes")
class NotesController:
    def __init__(self, service: NoteService):
        self.service = service

    @command
    def create_note(self, title: str, body: str) -> dict:
        return self.service.create(title, body)

    @command
    def list_notes(self) -> list:
        return self.service.list_all()

    @command
    def delete_note(self, title: str) -> int:
        return self.service.delete(title)


@Module(controllers=[NotesController], providers=[NoteService])
class NotesModule:
    pass


def test_di_module_create_and_list_notes():
    app = App(plugins=[MongoPlugin(database="test")], root_module=NotesModule)
    app.ipc.handle({"id": "1", "command": "notes.create_note",
                    "args": {"title": "Hello", "body": "World"}})
    app.ipc.handle({"id": "2", "command": "notes.create_note",
                    "args": {"title": "Foo", "body": "Bar"}})
    resp = app.ipc.handle({"id": "3", "command": "notes.list_notes", "args": {}})
    assert resp["ok"] is True
    assert len(resp["result"]) == 2


def test_di_module_delete_note():
    app = App(plugins=[MongoPlugin(database="test")], root_module=NotesModule)
    app.ipc.handle({"id": "1", "command": "notes.create_note",
                    "args": {"title": "Temp", "body": "to be deleted"}})
    resp = app.ipc.handle({"id": "2", "command": "notes.delete_note",
                           "args": {"title": "Temp"}})
    assert resp["result"] == 1
    list_resp = app.ipc.handle({"id": "3", "command": "notes.list_notes", "args": {}})
    assert list_resp["result"] == []


# ── Public API exports ────────────────────────────────────────────────────────


def test_mongo_database_importable():
    from vesper_mongodb import MongoDatabase as MD
    assert MD is MongoDatabase


def test_mongo_plugin_importable():
    from vesper_mongodb import MongoPlugin as MP
    assert MP is MongoPlugin


def test_plugin_alias_exported():
    from vesper_mongodb import Plugin as P
    assert P is MongoPlugin
