from __future__ import annotations

import threading
from pathlib import Path

from vesper.core.plugin import VesperPlugin


def _convert_params(sql: str, params: list) -> tuple[str, dict]:
    """
    Convert ? placeholders and a positional params list to SQLAlchemy's
    :p0, :p1, ... named-param style.

    SQLAlchemy's text() uses :name style internally and translates it to the
    correct backend syntax ($1 for PostgreSQL, %s for MySQL, ? for SQLite).
    """
    if not params:
        return sql, {}

    named: dict = {}
    parts = sql.split("?")
    result = parts[0]
    for i, part in enumerate(parts[1:]):
        key = f"p{i}"
        named[key] = params[i] if i < len(params) else None
        result += f":{key}" + part
    return result, named


class DatabasePlugin(VesperPlugin):
    """
    SQL database plugin for Vesper powered by SQLAlchemy.

    Supports SQLite, PostgreSQL (requires psycopg2), and MySQL (requires pymysql).
    SQLAlchemy must be installed: pip install sqlalchemy

    Usage:
        from vesper_db import DatabasePlugin

        # SQLite (local file — no extra driver needed)
        app = App(plugins=[DatabasePlugin(url="sqlite:///data.db")])

        # PostgreSQL  (pip install psycopg2-binary)
        app = App(plugins=[DatabasePlugin(url="postgresql://user:pass@localhost/myapp")])

        # MySQL  (pip install pymysql)
        app = App(plugins=[DatabasePlugin(url="mysql+pymysql://user:pass@localhost/myapp")])

    SQL parameters use ? placeholders regardless of the backend:
        db:query  → SELECT * FROM users WHERE id = ?   params: [1]
        db:execute → INSERT INTO users (name) VALUES (?)  params: ["Ana"]
    """

    def __init__(self, *, url: str) -> None:
        self._url = url
        self._engine = None
        self._init_lock = threading.Lock()
        # SQLite StaticPool shares one connection; this lock serializes access.
        # PostgreSQL/MySQL use pooled connections so the lock is a no-cost no-op.
        self._db_lock = threading.Lock()

    # ── Plugin interface ──────────────────────────────────────────────────────

    def register(self, app) -> None:
        _db = self

        @app.command("db:query")
        def query(sql: str, params: list = None) -> list:
            return _db._query(sql, params or [])

        @app.command("db:execute")
        def execute(sql: str, params: list = None) -> dict:
            return _db._execute(sql, params or [])

        @app.command("db:transaction")
        def transaction(statements: list) -> dict:
            return _db._transaction(statements)

    @classmethod
    def sdk_path(cls) -> Path | None:
        from importlib.resources import files
        return Path(str(files("vesper_db").joinpath("sdk/vesper-db.js")))

    # ── Engine ────────────────────────────────────────────────────────────────

    def _get_engine(self):
        with self._init_lock:
            if self._engine is None:
                try:
                    from sqlalchemy import create_engine
                except ImportError as exc:
                    raise RuntimeError(
                        "SQLAlchemy is required by vesper-db. "
                        "Install it with: pip install sqlalchemy"
                    ) from exc

                kwargs: dict = {}
                if self._url == "sqlite:///:memory:":
                    from sqlalchemy.pool import StaticPool
                    kwargs["connect_args"] = {"check_same_thread": False}
                    kwargs["poolclass"] = StaticPool

                self._engine = create_engine(self._url, **kwargs)
            return self._engine

    # ── Operations ────────────────────────────────────────────────────────────

    def _query(self, sql: str, params: list) -> list:
        from sqlalchemy import text
        converted_sql, converted_params = _convert_params(sql, params)
        with self._db_lock, self._get_engine().connect() as conn:
            result = conn.execute(text(converted_sql), converted_params)
            return [dict(row._mapping) for row in result]

    def _execute(self, sql: str, params: list) -> dict:
        from sqlalchemy import text
        converted_sql, converted_params = _convert_params(sql, params)
        with self._db_lock, self._get_engine().begin() as conn:
            result = conn.execute(text(converted_sql), converted_params)
            return {"affected": result.rowcount}

    def _transaction(self, statements: list) -> dict:
        from sqlalchemy import text
        total = 0
        with self._db_lock, self._get_engine().begin() as conn:
            for stmt in statements:
                sql = stmt.get("sql", "")
                params = stmt.get("params", [])
                converted_sql, converted_params = _convert_params(sql, params)
                result = conn.execute(text(converted_sql), converted_params)
                if result.rowcount and result.rowcount > 0:
                    total += result.rowcount
        return {"affected": total}
