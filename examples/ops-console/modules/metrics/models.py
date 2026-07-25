"""
Optional SQLAlchemy persistence for the metrics history — only importable
when vesper-db is installed (it imports `Base` from vesper_db).

app.py imports this module only inside its `if HAS_DB:` branch, exactly like
media-vault only imports ffmpeg-dependent code paths when ffmpeg is present.
Without vesper-db, MetricsService keeps its in-memory ring buffer and this
file is simply never touched.

A second engine/sessionmaker, independent of the one vesper-db's
DatabasePlugin builds for itself, is deliberate: DatabasePlugin's DbSession is
a `scoped_session` cleaned up per IPC call (`app.add_teardown`), which fits a
request-response command but not a long-lived background thread that writes
every couple of seconds outside any IPC call. A short-lived session per write,
against a second connection to the same SQLite file, avoids stretching that
lifecycle to a use it was not built for.
"""
from __future__ import annotations

from sqlalchemy import Float
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from vesper_db import Base


class MetricSample(Base):
    __tablename__ = "ops_console_metric_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[float] = mapped_column(Float)
    cpu: Mapped[float] = mapped_column(Float)
    mem: Mapped[float] = mapped_column(Float)


class MetricsHistoryRepo:
    """Tiny persistence gateway MetricsService writes/reads through."""

    def __init__(self, engine: Engine) -> None:
        self._Session = sessionmaker(bind=engine)

    def append(self, ts: float, cpu: float, mem: float) -> None:
        with self._Session() as session:
            session.add(MetricSample(ts=ts, cpu=cpu, mem=mem))
            session.commit()

    def recent(self, limit: int = 600) -> list[dict]:
        with self._Session() as session:
            rows = (
                session.query(MetricSample)
                .order_by(MetricSample.id.desc())
                .limit(limit)
                .all()
            )
        return [
            {"ts": r.ts, "cpu": r.cpu, "mem": r.mem, "synthetic": False}
            for r in reversed(rows)
        ]
