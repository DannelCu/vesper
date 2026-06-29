from __future__ import annotations

from pathlib import Path

from vesper.core.plugin import VesperPlugin
from vesper.core.module import Container
from vesper_db.base import Base
from vesper_db.session import DbSession


class DatabasePlugin(VesperPlugin):
    """
    SQLAlchemy database integration plugin for Vesper.

    Initializes the database engine, creates all tables, and wires the
    session into the Vesper DI system so services can declare db: DbSession
    in their __init__ and receive the session automatically.

    Usage:
        from vesper import App
        from vesper_db import DatabasePlugin

        app = App(
            root_module=AppModule,
            plugins=[DatabasePlugin(url="sqlite:///myapp.db")],
        )

    Services declare the session via type annotation:
        from vesper import Injectable
        from vesper_db import DbSession

        @Injectable()
        class UsersService:
            def __init__(self, db: DbSession):
                self.db = db

            def create(self, email: str, name: str) -> dict:
                user = User(email=email, name=name)
                self.db.add(user)
                self.db.commit()
                return {"id": user.id}

    Supported databases:
        - SQLite:     "sqlite:///myapp.db"   (no extra driver needed)
        - PostgreSQL: "postgresql://user:pass@localhost/db"  (pip install psycopg2-binary)
        - MySQL:      "mysql+pymysql://user:pass@localhost/db"  (pip install pymysql)
    """

    def __init__(self, *, url: str) -> None:
        self._url = url

    def register(self, app) -> None:
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import scoped_session, sessionmaker
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

        engine = create_engine(self._url, **kwargs)

        # All models inheriting from Base are already imported by the time
        # App() is constructed (Python imports happen at module load time).
        Base.metadata.create_all(engine)

        # scoped_session gives each thread its own session proxy.
        # IPC calls run on the calling thread, so each call gets an isolated session.
        session_factory = scoped_session(sessionmaker(bind=engine))

        # Register the session in the global DI registry.
        # Services that declare db: DbSession will receive this proxy.
        Container.register_global(DbSession, session_factory)

        # Remove the thread-local session after every IPC call.
        app.add_teardown(session_factory.remove)

    @classmethod
    def sdk_path(cls) -> Path | None:
        return None
