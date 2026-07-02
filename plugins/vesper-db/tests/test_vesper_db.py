"""Tests for the redesigned vesper-db plugin (DI-based session management)."""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy", reason="sqlalchemy not installed")

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vesper import App, Controller, Injectable, Module, command
from vesper.core.module import Container
from vesper_db import Base, DatabasePlugin, DbSession, Plugin


# ── Test models (defined once at module level) ────────────────────────────────

class User(Base):
    __tablename__ = "db_test_users"
    id:    Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    name:  Mapped[str]
    profile: Mapped["Profile"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )

class Profile(Base):
    __tablename__ = "db_test_profiles"
    id:      Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("db_test_users.id"), unique=True)
    bio:     Mapped[str | None]
    user:    Mapped["User"] = relationship(back_populates="profile")


# ── DI-wired service and module ───────────────────────────────────────────────

@Injectable()
class UserService:
    def __init__(self, db: DbSession):
        self.db = db

    def get_all(self) -> list[dict]:
        return [{"id": u.id, "email": u.email, "name": u.name}
                for u in self.db.query(User).all()]

    def create(self, email: str, name: str, bio: str = "") -> dict:
        user = User(email=email, name=name, profile=Profile(bio=bio))
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return {"id": user.id, "email": user.email, "name": user.name}

    def delete(self, user_id: int) -> None:
        user = self.db.get(User, user_id)
        if user:
            self.db.delete(user)
            self.db.commit()


@Controller("users")
class UserController:
    def __init__(self, service: UserService):
        self.service = service

    @command
    def list(self) -> list:
        return self.service.get_all()

    @command
    def create(self, email: str, name: str, bio: str = "") -> dict:
        return self.service.create(email, name, bio)

    @command
    def delete(self, user_id: int) -> None:
        self.service.delete(user_id)


@Module(controllers=[UserController], providers=[UserService])
class UserModule:
    pass


def make_app() -> App:
    return App(plugins=[DatabasePlugin(url="sqlite:///:memory:")], root_module=UserModule)


# ── Container global registry ─────────────────────────────────────────────────

def test_register_global_makes_type_resolvable():
    sentinel = object()
    Container.register_global(DbSession, sentinel)
    container = Container([])
    assert container.resolve(DbSession) is sentinel


def test_clear_global_removes_all():
    sentinel = object()
    Container.register_global(DbSession, sentinel)
    Container.clear_global()
    assert DbSession not in Container._global
    # resolve() now falls through to instantiate a fresh DbSession(),
    # NOT the sentinel — confirming the global was cleared
    container = Container([])
    result = container.resolve(DbSession)
    assert result is not sentinel


def test_global_provider_injected_into_service():
    sentinel = object()
    Container.register_global(DbSession, sentinel)

    @Injectable()
    class MyService:
        def __init__(self, db: DbSession):
            self.db = db

    container = Container([MyService])
    service = container.resolve(MyService)
    assert service.db is sentinel


# ── Plugin basics ─────────────────────────────────────────────────────────────

def test_plugin_alias_is_database_plugin():
    assert Plugin is DatabasePlugin


def test_database_plugin_is_vesper_plugin():
    from vesper import VesperPlugin
    assert issubclass(DatabasePlugin, VesperPlugin)


def test_sdk_path_returns_none():
    assert DatabasePlugin.sdk_path() is None


def test_plugin_registers_db_session_globally():
    app = App()
    DatabasePlugin(url="sqlite:///:memory:").register(app)
    assert DbSession in app._global_providers


def test_plugin_adds_teardown_to_ipc():
    app = App(plugins=[DatabasePlugin(url="sqlite:///:memory:")])
    assert len(app.ipc._teardown) == 1


# ── Base and models ───────────────────────────────────────────────────────────

def test_base_is_declarative_base():
    from sqlalchemy.orm import DeclarativeBase
    assert issubclass(Base, DeclarativeBase)


def test_user_model_has_correct_tablename():
    assert User.__tablename__ == "db_test_users"


def test_profile_model_has_correct_tablename():
    assert Profile.__tablename__ == "db_test_profiles"


def test_models_registered_in_base_metadata():
    assert "db_test_users" in Base.metadata.tables
    assert "db_test_profiles" in Base.metadata.tables


# ── DI injection + IPC integration ───────────────────────────────────────────

def test_db_session_injected_into_service():
    app = make_app()
    # UserService receives a scoped_session proxy via DI
    container = Container([UserService], global_providers=app._global_providers)
    service = container.resolve(UserService)
    assert service.db is app._global_providers[DbSession]


def test_create_user_via_ipc(tmp_path):
    app = make_app()
    resp = app.ipc.handle({
        "id": "1",
        "command": "users.create",
        "args": {"email": "alice@test.com", "name": "Alice"},
    })
    assert resp["ok"] is True
    assert resp["result"]["email"] == "alice@test.com"
    assert resp["result"]["id"] is not None


def test_list_users_via_ipc():
    app = make_app()
    app.ipc.handle({"id": "1", "command": "users.create",
                    "args": {"email": "bob@test.com", "name": "Bob"}})
    resp = app.ipc.handle({"id": "2", "command": "users.list", "args": {}})
    assert resp["ok"] is True
    assert len(resp["result"]) == 1
    assert resp["result"][0]["name"] == "Bob"


def test_list_empty_initially():
    app = make_app()
    resp = app.ipc.handle({"id": "1", "command": "users.list", "args": {}})
    assert resp["ok"] is True
    assert resp["result"] == []


def test_create_with_profile():
    app = make_app()
    resp = app.ipc.handle({
        "id": "1",
        "command": "users.create",
        "args": {"email": "carol@test.com", "name": "Carol", "bio": "Hello!"},
    })
    assert resp["ok"] is True
    assert resp["result"]["name"] == "Carol"


def test_delete_user_via_ipc():
    app = make_app()
    create = app.ipc.handle({"id": "1", "command": "users.create",
                              "args": {"email": "del@test.com", "name": "Del"}})
    user_id = create["result"]["id"]

    app.ipc.handle({"id": "2", "command": "users.delete", "args": {"user_id": user_id}})

    resp = app.ipc.handle({"id": "3", "command": "users.list", "args": {}})
    assert resp["result"] == []


def test_missing_required_arg_returns_validation_error():
    app = make_app()
    resp = app.ipc.handle({"id": "1", "command": "users.create", "args": {}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValidationError"


def test_multiple_users_created_and_listed():
    app = make_app()
    for i in range(3):
        app.ipc.handle({"id": str(i), "command": "users.create",
                        "args": {"email": f"u{i}@test.com", "name": f"User{i}"}})
    resp = app.ipc.handle({"id": "10", "command": "users.list", "args": {}})
    assert len(resp["result"]) == 3


# ── Session lifecycle (teardown) ──────────────────────────────────────────────

def test_teardown_runs_after_successful_command():
    teardown_calls = []
    app = App()

    @app.command("ping")
    def ping() -> str:
        return "pong"

    app.add_teardown(lambda: teardown_calls.append(1))
    app.ipc.handle({"id": "1", "command": "ping", "args": {}})
    assert teardown_calls == [1]


def test_teardown_runs_after_failed_command():
    teardown_calls = []
    app = App()

    @app.command("boom")
    def boom() -> None:
        raise RuntimeError("oops")

    app.add_teardown(lambda: teardown_calls.append(1))
    resp = app.ipc.handle({"id": "1", "command": "boom", "args": {}})
    assert resp["ok"] is False
    assert teardown_calls == [1]


def test_teardown_does_not_affect_response_on_error():
    app = App()

    @app.command("ok_cmd")
    def ok_cmd() -> str:
        return "fine"

    app.add_teardown(lambda: (_ for _ in ()).throw(RuntimeError("teardown error")))
    resp = app.ipc.handle({"id": "1", "command": "ok_cmd", "args": {}})
    assert resp["ok"] is True
    assert resp["result"] == "fine"


def test_teardown_called_once_per_ipc_call():
    counts = []
    app = App()

    @app.command("noop")
    def noop() -> None:
        pass

    app.add_teardown(lambda: counts.append(1))
    for _ in range(5):
        app.ipc.handle({"id": "x", "command": "noop", "args": {}})
    assert len(counts) == 5


# ── Session isolation between calls ──────────────────────────────────────────

def test_each_ipc_call_uses_fresh_session():
    """Commit in one call should not bleed into the next call's view."""
    app = make_app()

    app.ipc.handle({"id": "1", "command": "users.create",
                    "args": {"email": "iso@test.com", "name": "Iso"}})

    resp1 = app.ipc.handle({"id": "2", "command": "users.list", "args": {}})
    resp2 = app.ipc.handle({"id": "3", "command": "users.list", "args": {}})

    assert resp1["result"] == resp2["result"]


# ── File-based SQLite ─────────────────────────────────────────────────────────

def test_file_based_sqlite_creates_db_file(tmp_path):
    db_file = tmp_path / "test.db"
    App(plugins=[DatabasePlugin(url=f"sqlite:///{db_file}")], root_module=UserModule)
    assert db_file.exists()


def test_file_based_sqlite_persists_data(tmp_path):
    db_file = tmp_path / "persist.db"
    url = f"sqlite:///{db_file}"

    app1 = App(plugins=[DatabasePlugin(url=url)], root_module=UserModule)
    app1.ipc.handle({"id": "1", "command": "users.create",
                     "args": {"email": "persist@test.com", "name": "Persist"}})

    Container.clear_global()
    app2 = App(plugins=[DatabasePlugin(url=url)], root_module=UserModule)
    resp = app2.ipc.handle({"id": "2", "command": "users.list", "args": {}})
    assert resp["result"][0]["email"] == "persist@test.com"


# ── Thread safety ─────────────────────────────────────────────────────────────

def test_concurrent_ipc_calls_do_not_corrupt(tmp_path):
    # File-based SQLite with WAL mode supports concurrent writes across threads.
    # in-memory + StaticPool shares one connection and cannot handle simultaneous writes.
    db_file = tmp_path / "concurrent.db"
    url = f"sqlite:///{db_file}?check_same_thread=false"
    app = App(plugins=[DatabasePlugin(url=url)], root_module=UserModule)

    # Enable WAL mode so readers don't block writers
    session = app._global_providers[DbSession]
    with session() as s:
        s.execute(__import__("sqlalchemy").text("PRAGMA journal_mode=WAL"))
        s.commit()
    session.remove()

    errors = []

    def create_user(i):
        try:
            resp = app.ipc.handle({
                "id": str(i),
                "command": "users.create",
                "args": {"email": f"thread{i}@test.com", "name": f"Thread{i}"},
            })
            if not resp["ok"]:
                errors.append(resp["error"])
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=create_user, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Errors: {errors}"
    resp = app.ipc.handle({"id": "100", "command": "users.list", "args": {}})
    assert len(resp["result"]) == 5


# ── DbSession exports ─────────────────────────────────────────────────────────

def test_db_session_importable_from_package():
    from vesper_db import DbSession as DS
    assert DS is DbSession


def test_base_importable_from_package():
    from vesper_db import Base as B
    assert B is Base
