from __future__ import annotations

import json
import os
import platform
import threading
from pathlib import Path

from vesper.core.plugin import VesperPlugin


class StorePlugin(VesperPlugin):
    """
    Persistent key-value store plugin for Vesper.

    Stores data as JSON in the user's application data directory.
    Thread-safe — safe to call from multiple IPC commands concurrently.

    Usage:
        from vesper_store import StorePlugin
        app = App(plugins=[StorePlugin(app_name="my-app")])

    Storage locations:
        Windows : %APPDATA%\\<app_name>\\store.json
        macOS   : ~/Library/Application Support/<app_name>/store.json
        Linux   : ~/.config/<app_name>/store.json  (or $XDG_CONFIG_HOME)
    """

    def __init__(self, *, app_name: str = "vesper-app", path: str | None = None) -> None:
        self._path = Path(path) if path else _default_path(app_name)
        self._lock = threading.Lock()

    def register(self, app) -> None:
        _store = self

        @app.command("store:get")
        def get(key: str):
            return _store._get(key)

        @app.command("store:set")
        def set_(key: str, value=None) -> None:
            _store._set(key, value)

        @app.command("store:delete")
        def delete(key: str) -> None:
            _store._delete(key)

        @app.command("store:has")
        def has(key: str) -> bool:
            return _store._has(key)

        @app.command("store:clear")
        def clear() -> None:
            _store._clear()

        @app.command("store:keys")
        def keys() -> list:
            return _store._keys()

    @classmethod
    def sdk_path(cls) -> Path | None:
        from importlib.resources import files
        return Path(str(files("vesper_store").joinpath("sdk/vesper-store.js")))

    # ── Internal store operations ─────────────────────────────────────────────

    def _load(self) -> dict:
        if not self._path.is_file():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _get(self, key: str):
        with self._lock:
            return self._load().get(key)

    def _set(self, key: str, value) -> None:
        with self._lock:
            data = self._load()
            data[key] = value
            self._save(data)

    def _delete(self, key: str) -> None:
        with self._lock:
            data = self._load()
            data.pop(key, None)
            self._save(data)

    def _has(self, key: str) -> bool:
        with self._lock:
            return key in self._load()

    def _clear(self) -> None:
        with self._lock:
            self._save({})

    def _keys(self) -> list[str]:
        with self._lock:
            return list(self._load().keys())


def _default_path(app_name: str) -> Path:
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / app_name / "store.json"
