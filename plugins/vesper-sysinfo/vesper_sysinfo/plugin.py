from __future__ import annotations

import threading
import time
from pathlib import Path

from vesper.core.plugin import VesperPlugin


class SysinfoPlugin(VesperPlugin):
    """
    System information for Vesper via psutil: CPU, memory, per-partition disks,
    network counters, battery (when present) and uptime.

    Two modes:

    - **Snapshot** on demand: ``vesper.sysinfo.snapshot()``.
    - **Subscription**: ``vesper.sysinfo.subscribe({interval})`` emits
      ``vesper:sysinfo:tick`` events until unsubscribed. One subscription per
      app — a second subscribe just retunes the interval. The ticker thread
      stops cleanly when the app closes; no orphan threads.

    Usage::

        from vesper_sysinfo import SysinfoPlugin

        app = App(plugins=[SysinfoPlugin()])
    """

    def __init__(self) -> None:
        self._app = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._interval = 2.0
        self._lock = threading.Lock()

    def register(self, app) -> None:
        self._app = app

        def _snapshot() -> dict:
            return self.snapshot()

        def _subscribe(interval: float = 2.0) -> bool:
            self.subscribe(interval=interval)
            return True

        def _unsubscribe() -> bool:
            return self.unsubscribe()

        app.registry.register(_snapshot, name="vesper:sysinfo:snapshot")
        app.registry.register(_subscribe, name="vesper:sysinfo:subscribe")
        app.registry.register(_unsubscribe, name="vesper:sysinfo:unsubscribe")

        app.on("close")(self.unsubscribe)

    def snapshot(self) -> dict:
        """One reading of everything. Safe to call at any rate the UI needs."""
        import psutil

        memory = psutil.virtual_memory()
        net = psutil.net_io_counters()

        disks = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                # Unreadable mounts (cdroms, restricted fuse) are not the
                # caller's problem; report the disks that answer.
                continue
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "total": usage.total,
                "used": usage.used,
                "percent": usage.percent,
            })

        battery = None
        sensors = getattr(psutil, "sensors_battery", None)
        if sensors is not None:
            try:
                reading = sensors()
            except Exception:
                reading = None
            if reading is not None:
                battery = {
                    "percent": reading.percent,
                    "plugged": bool(reading.power_plugged),
                }

        return {
            "cpu": {
                # interval=None: non-blocking, measured since the previous call.
                "percent": psutil.cpu_percent(interval=None),
                "count": psutil.cpu_count(),
            },
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
            },
            "disks": disks,
            "net": {
                "bytes_sent": net.bytes_sent,
                "bytes_recv": net.bytes_recv,
            },
            "battery": battery,
            "uptime": time.time() - psutil.boot_time(),
        }

    def subscribe(self, *, interval: float = 2.0) -> None:
        """Start (or retune) the tick stream. Emits ``sysinfo:tick`` events."""
        with self._lock:
            self._interval = max(0.1, float(interval))
            if self._thread is not None and self._thread.is_alive():
                return

            self._stop = threading.Event()
            stop = self._stop
            emit = self._app.emit

            def _ticker() -> None:
                while not stop.is_set():
                    try:
                        emit("sysinfo:tick", self.snapshot())
                    except Exception:
                        # A window mid-teardown must not kill the ticker; the
                        # stop event ends it.
                        pass
                    stop.wait(self._interval)

            self._thread = threading.Thread(target=_ticker, daemon=True, name="vesper-sysinfo")
            self._thread.start()

    def unsubscribe(self) -> bool:
        """Stop the tick stream and join the thread. False when none ran."""
        with self._lock:
            thread = self._thread
            if thread is None:
                return False
            self._stop.set()
            self._thread = None
        thread.join(timeout=5)
        return True

    @classmethod
    def sdk_path(cls) -> Path | None:
        from importlib.resources import files
        return Path(str(files("vesper_sysinfo").joinpath("sdk/vesper-sysinfo.js")))
