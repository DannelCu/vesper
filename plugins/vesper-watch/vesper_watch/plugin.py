from __future__ import annotations

import itertools
import threading
import time
from pathlib import Path

from vesper.core.plugin import VesperPlugin


class WatchPlugin(VesperPlugin):
    """
    File watching for Vesper, backed by watchdog (inotify / FSEvents /
    ReadDirectoryChangesW).

    The frontend asks to watch a path and receives ``vesper:fs:changed`` events:

        const watcher = await vesper.watch.watch("/data/projects", {
            onChange: ({ kind, path }) => refresh(),
        })
        // later: await watcher.unwatch()

    Event payloads: ``{id, kind, path, dest_path?, is_dir}`` where kind is
    ``created | modified | deleted | moved`` (moved carries ``dest_path``).

    Watched paths are validated against the app's ``fs_scope``, so a sandboxed
    frontend cannot observe directories it cannot read. Bursts are debounced:
    repeats of the same (kind, path) within the debounce window are dropped.

    Usage::

        from vesper_watch import WatchPlugin

        app = App(plugins=[WatchPlugin()])
    """

    def __init__(self, *, debounce: float = 0.2) -> None:
        self._default_debounce = debounce
        self._app = None
        self._observers: dict[int, object] = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def register(self, app) -> None:
        self._app = app

        def _watch(path: str, recursive: bool = True, debounce: float = -1) -> int:
            return self.watch(
                path,
                recursive=recursive,
                debounce=self._default_debounce if debounce < 0 else debounce,
            )

        def _unwatch(id: int) -> bool:
            return self.unwatch(id)

        app.registry.register(_watch, name="vesper:fs:watch")
        app.registry.register(_unwatch, name="vesper:fs:unwatch")

        # Observer threads must not outlive the window.
        app.on("close")(self.stop_all)

    def watch(self, path: str, *, recursive: bool = True, debounce: float = 0.2) -> int:
        """Start watching *path*. Returns the watch id used in events."""
        scope = getattr(self._app, "fs_scope", None)
        target = Path(scope.check(path)) if scope is not None else Path(path)
        if not target.exists():
            raise FileNotFoundError(f"No such path: {path}")

        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        watch_id = next(self._ids)
        emit = self._app.emit
        last_emitted: dict[tuple[str, str], float] = {}

        class _Handler(FileSystemEventHandler):
            def _report(self, kind: str, event, dest_path: str | None = None) -> None:
                now = time.monotonic()
                key = (kind, event.src_path)
                if debounce > 0 and now - last_emitted.get(key, -debounce) < debounce:
                    return
                last_emitted[key] = now

                payload = {
                    "id": watch_id,
                    "kind": kind,
                    "path": str(event.src_path),
                    "is_dir": bool(event.is_directory),
                }
                if dest_path is not None:
                    payload["dest_path"] = str(dest_path)
                try:
                    emit("fs:changed", payload)
                except Exception:
                    # The observer thread must survive a window mid-teardown.
                    pass

            def on_created(self, event):
                self._report("created", event)

            def on_modified(self, event):
                self._report("modified", event)

            def on_deleted(self, event):
                self._report("deleted", event)

            def on_moved(self, event):
                self._report("moved", event, dest_path=event.dest_path)

        observer = Observer()
        observer.schedule(_Handler(), str(target), recursive=recursive)
        observer.daemon = True
        observer.start()

        with self._lock:
            self._observers[watch_id] = observer
        return watch_id

    def unwatch(self, watch_id: int) -> bool:
        """Stop a watch. Returns False for an unknown id."""
        with self._lock:
            observer = self._observers.pop(watch_id, None)
        if observer is None:
            return False
        observer.stop()
        observer.join(timeout=2)
        return True

    def stop_all(self) -> None:
        with self._lock:
            ids = list(self._observers)
        for watch_id in ids:
            self.unwatch(watch_id)

    @classmethod
    def sdk_path(cls) -> Path | None:
        from importlib.resources import files
        return Path(str(files("vesper_watch").joinpath("sdk/vesper-watch.js")))
