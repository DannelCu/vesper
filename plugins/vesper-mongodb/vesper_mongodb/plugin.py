from __future__ import annotations

from pathlib import Path

from vesper.core.plugin import VesperPlugin
from vesper.core.module import Container
from vesper_mongodb.database import MongoDatabase, _serialize


class MongoPlugin(VesperPlugin):
    def __init__(
        self,
        *,
        uri: str = "mongodb://localhost:27017",
        database: str = "vesper-app",
    ) -> None:
        self._uri = uri
        self._database = database

    def register(self, app) -> None:
        import pymongo

        client = pymongo.MongoClient(self._uri)
        db = client[self._database]
        Container.register_global(MongoDatabase, db)

        @app.command("mongo:find")
        def find(collection: str, filter: dict = None, limit: int = 0) -> list:
            cursor = db[collection].find(filter or {})
            if limit:
                cursor = cursor.limit(limit)
            return [_serialize(doc) for doc in cursor]

        @app.command("mongo:find_one")
        def find_one(collection: str, filter: dict = None) -> dict | None:
            return _serialize(db[collection].find_one(filter or {}))

        @app.command("mongo:insert_one")
        def insert_one(collection: str, document: dict) -> dict:
            result = db[collection].insert_one(document)
            return {"id": str(result.inserted_id)}

        @app.command("mongo:insert_many")
        def insert_many(collection: str, documents: list) -> dict:
            result = db[collection].insert_many(documents)
            return {"ids": [str(oid) for oid in result.inserted_ids]}

        @app.command("mongo:update_one")
        def update_one(collection: str, filter: dict, update: dict) -> dict:
            result = db[collection].update_one(filter, update)
            return {"matched": result.matched_count, "modified": result.modified_count}

        @app.command("mongo:update_many")
        def update_many(collection: str, filter: dict, update: dict) -> dict:
            result = db[collection].update_many(filter, update)
            return {"matched": result.matched_count, "modified": result.modified_count}

        @app.command("mongo:delete_one")
        def delete_one(collection: str, filter: dict) -> dict:
            result = db[collection].delete_one(filter)
            return {"deleted": result.deleted_count}

        @app.command("mongo:delete_many")
        def delete_many(collection: str, filter: dict) -> dict:
            result = db[collection].delete_many(filter)
            return {"deleted": result.deleted_count}

        @app.command("mongo:count")
        def count(collection: str, filter: dict = None) -> int:
            return db[collection].count_documents(filter or {})

    @classmethod
    def sdk_path(cls) -> Path | None:
        return Path(__file__).parent / "sdk" / "vesper-mongodb.js"
