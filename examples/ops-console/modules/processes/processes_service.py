"""
The process table's data source.

psutil is an ordinary optional dependency of this *example app*, not a
Vesper plugin — the same relationship media-vault has with ffmpeg (see
CONTRIBUTING.md's four-level tree, which is about the framework's own core
and plugins, not what an example imports for itself). Importing it
defensively and degrading the whole module honestly when it is absent keeps
the app usable without it, per the plan's rule that nothing plugin-shaped
may block the app from opening.

Note psutil is unrelated to vesper.core.process / ShellScope: that machinery
runs and tracks processes *this app spawned*, addressed by an internal id —
not arbitrary OS PIDs. Listing and signalling processes system-wide needs a
real per-PID API, which is exactly what psutil provides and what neither
vesper's core nor any of its plugins expose today (see the friction report
in the README).
"""
from __future__ import annotations

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    psutil = None
    HAS_PSUTIL = False


class ProcessNotFoundError(Exception):
    """The PID no longer exists — it likely exited between list and terminate."""


class ProcessTerminationError(Exception):
    """psutil raised something other than "gone" — permissions, usually."""


_SORT_KEYS = {"pid", "name", "username", "cpu_percent", "memory_percent", "status"}


class ProcessesService:
    def available(self) -> bool:
        return HAS_PSUTIL

    def list(
        self,
        *,
        search: str = "",
        sort_by: str = "cpu_percent",
        sort_dir: str = "desc",
        page: int = 1,
        page_size: int = 25,
    ) -> dict:
        if not HAS_PSUTIL:
            return {
                "available": False,
                "items": [],
                "total": 0,
                "page": 1,
                "page_size": page_size,
            }

        sort_key = sort_by if sort_by in _SORT_KEYS else "cpu_percent"
        needle = search.strip().lower()

        rows: list[dict] = []
        for proc in psutil.process_iter(
            ["pid", "name", "username", "cpu_percent", "memory_percent", "status", "create_time"]
        ):
            try:
                info = proc.info
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue  # Exited or unreadable between iteration and read — skip it.

            name = info.get("name") or ""
            if needle and needle not in name.lower():
                continue

            rows.append(
                {
                    "pid": info.get("pid"),
                    "name": name,
                    "username": info.get("username") or "",
                    "cpu_percent": round(info.get("cpu_percent") or 0.0, 1),
                    "memory_percent": round(info.get("memory_percent") or 0.0, 1),
                    "status": info.get("status") or "",
                    "create_time": info.get("create_time") or 0,
                }
            )

        rows.sort(key=lambda r: r.get(sort_key) or 0, reverse=(sort_dir == "desc"))

        total = len(rows)
        start = max(0, (page - 1) * page_size)
        page_items = rows[start : start + page_size]

        return {
            "available": True,
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def terminate(self, pid: int) -> bool:
        """
        Ask a process to exit, escalating to a hard kill if it ignores SIGTERM.

        Raises ProcessNotFoundError / ProcessTerminationError rather than
        returning False — this is the command-failure phase of the IPC
        contract (docs/guards.md), distinct from the guard's ForbiddenError
        when a viewer tries this at all. The frontend tells the two apart.
        """
        if not HAS_PSUTIL:
            raise RuntimeError(
                "psutil is not installed; process termination is unavailable."
            )

        try:
            proc = psutil.Process(pid)
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                proc.kill()
        except psutil.NoSuchProcess as exc:
            raise ProcessNotFoundError(f"No such process: PID {pid}") from exc
        except psutil.AccessDenied as exc:
            raise ProcessTerminationError(
                f"The OS denied permission to terminate PID {pid}."
            ) from exc

        return True
