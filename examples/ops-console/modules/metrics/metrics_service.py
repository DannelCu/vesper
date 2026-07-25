"""
The one place CPU/memory sampling happens.

MetricsService is constructed once in app.py (not auto-built by a module's
DI container, because it needs a plugin instance and a repo decided by what
is installed) and shared as a global DI provider — MetricsController and
AlertsService both receive this exact instance. AlertsService consuming
MetricsService is the cross-module injection the plan calls for: alerts
reads real, live samples rather than polling on its own.
"""
from __future__ import annotations

import math
import threading
import time
from collections import deque
from typing import Callable


class MetricsService:
    def __init__(
        self,
        *,
        sysinfo_plugin=None,
        emit: Callable[[str, dict], None] | None = None,
        history_repo=None,
        memory_limit: int = 600,
    ) -> None:
        # None means vesper-sysinfo is not installed — samples are synthetic.
        self._sysinfo = sysinfo_plugin
        self._emit = emit
        self._repo = history_repo
        self.source = "sysinfo" if sysinfo_plugin is not None else "synthetic"

        self._history: deque[dict] = deque(maxlen=memory_limit)
        if self._repo is not None:
            # Persisted history survives a restart; without a repo the
            # buffer starts empty and only covers this session.
            for row in self._repo.recent(memory_limit):
                self._history.append(row)

        self._subscribers: list[Callable[[dict], None]] = []
        self._interval = 2.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._tick = 0

    def on_sample(self, callback: Callable[[dict], None]) -> None:
        """Register a callback fired with every new sample — used by alerts."""
        self._subscribers.append(callback)

    def _read(self) -> dict:
        now = time.time()
        if self._sysinfo is not None:
            snap = self._sysinfo.snapshot()
            cpu = float(snap["cpu"]["percent"])
            mem = float(snap["memory"]["percent"])
        else:
            # A smooth, bounded fake wave — never flat, never a straight
            # line, so a synthetic chart still looks like something worth
            # looking at rather than an obvious placeholder.
            self._tick += 1
            cpu = 45 + 30 * math.sin(self._tick / 12) + 6 * math.sin(self._tick / 3)
            mem = 55 + 20 * math.sin(self._tick / 18 + 1)
            cpu = max(0.0, min(100.0, cpu))
            mem = max(0.0, min(100.0, mem))

        return {
            "ts": now,
            "cpu": round(cpu, 1),
            "mem": round(mem, 1),
            "synthetic": self._sysinfo is None,
        }

    def snapshot(self) -> dict:
        """One reading, on demand. Does not touch the rolling history."""
        return self._read()

    def history(self, limit: int = 120) -> list[dict]:
        return list(self._history)[-limit:]

    def subscribe(self, *, interval: float = 2.0) -> None:
        """
        Start (or retune) the sampling loop.

        One loop per app, same contract as vesper-sysinfo's own subscribe():
        calling again just changes the interval instead of stacking tickers.
        This loop is what feeds the in-memory history, the optional DB
        repo, the "metrics:tick" event for the dashboard chart, and the
        alerts evaluator — all four read from the same samples.
        """
        with self._lock:
            self._interval = max(0.5, float(interval))
            if self._thread is not None and self._thread.is_alive():
                return

            self._stop = threading.Event()
            stop = self._stop

            def _loop() -> None:
                while not stop.is_set():
                    sample = self._read()
                    self._history.append(sample)

                    if self._repo is not None:
                        try:
                            self._repo.append(sample["ts"], sample["cpu"], sample["mem"])
                        except Exception:
                            pass  # A persistence hiccup must not stop live data.

                    if self._emit is not None:
                        try:
                            self._emit("metrics:tick", sample)
                        except Exception:
                            pass

                    for callback in list(self._subscribers):
                        try:
                            callback(sample)
                        except Exception:
                            pass  # One bad subscriber (e.g. alerts) must not kill the loop.

                    stop.wait(self._interval)

            self._thread = threading.Thread(
                target=_loop, daemon=True, name="ops-console-metrics"
            )
            self._thread.start()

    def unsubscribe(self) -> bool:
        """Stop the sampling loop. False when it was not running."""
        with self._lock:
            thread = self._thread
            if thread is None:
                return False
            self._stop.set()
            self._thread = None
        thread.join(timeout=5)
        return True
