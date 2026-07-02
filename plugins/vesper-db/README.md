# vesper-db

SQLAlchemy ORM integration for Vesper. Provides a scoped database session injectable into controllers and services via dependency injection.

---

## Install

```bash
pip install vesper-db
```

Supports SQLite, PostgreSQL, and MySQL. Database-specific drivers:

```bash
pip install psycopg2-binary   # PostgreSQL
pip install pymysql           # MySQL
```

---

## Setup

```python
from vesper import App
from vesper_db import DatabasePlugin, Base

app = App(
    title="My App",
    frontend="dist/index.html",
    plugins=[DatabasePlugin(url="sqlite:///app.db")],
    root_module=AppModule,
)
```

`Base.metadata.create_all()` is called automatically on plugin registration — all models that inherit from `Base` have their tables created at startup.

---

## Defining models

```python
# models.py
from vesper_db import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer

class User(Base):
    __tablename__ = "users"

    id:   Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True)
```

Import models before `app.run()` so they are registered with `Base.metadata` before `create_all()` runs:

```python
# app.py
import models   # noqa: F401 — ensures Base.metadata is populated
from vesper_db import DatabasePlugin, Base
```

---

## Injecting the session

```python
from vesper import Injectable, Controller, command
from vesper_db import DbSession
from models import User

@Injectable()
class UserService:
    def __init__(self, db: DbSession):
        self.db = db   # scoped_session injected by DatabasePlugin

    def list(self) -> list[dict]:
        return [{"id": u.id, "name": u.name} for u in self.db.query(User).all()]

    def create(self, name: str, email: str) -> dict:
        user = User(name=name, email=email)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return {"id": user.id, "name": user.name}
```

```python
@Controller("users")
class UsersController:
    def __init__(self, svc: UserService):
        self.svc = svc

    @command
    def list_users(self) -> list[dict]:
        return self.svc.list()

    @command
    def create_user(self, name: str, email: str) -> dict:
        return self.svc.create(name, email)
```

---

## Session lifecycle

`DbSession` is a SQLAlchemy `scoped_session`. A new session scope is created per thread. The plugin registers `session.remove()` as a teardown hook — the session is released automatically after every IPC call, regardless of success or failure.

You do not need to call `session.close()` manually.

---

## Database URLs

| Database | URL format |
|---|---|
| SQLite (file) | `sqlite:///relative/path.db` or `sqlite:////abs/path.db` |
| SQLite (memory) | `sqlite:///:memory:` |
| PostgreSQL | `postgresql://user:pass@host/dbname` |
| MySQL | `mysql+pymysql://user:pass@host/dbname` |

### SQLite WAL mode (concurrent writes)

For apps that write to SQLite from multiple threads:

```python
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3

@event.listens_for(Engine, "connect")
def set_wal(dbapi_conn, connection_record):
    if isinstance(dbapi_conn, sqlite3.Connection):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
```

Add this before `app.run()`. WAL mode allows one writer and multiple concurrent readers.

### In-memory SQLite for tests

```python
from sqlalchemy.pool import StaticPool
from vesper_db import DatabasePlugin

plugin = DatabasePlugin(
    url="sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
```

`StaticPool` ensures all connections share the same in-memory database (required for `:memory:` under concurrent access).

---

## Alembic migrations

For schema migrations in production, use [Alembic](https://alembic.sqlalchemy.org/en/latest/):

```bash
pip install alembic
alembic init alembic
```

In `alembic/env.py`, import your `Base` and set `target_metadata = Base.metadata`.

Vesper's `DatabasePlugin` calls `create_all()` on startup — for production apps with Alembic, disable this by passing `create_tables=False` and let Alembic manage schema:

```python
DatabasePlugin(url="postgresql://...", create_tables=False)
```
