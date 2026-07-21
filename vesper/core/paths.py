"""
Per-user directories for framework state.

Implemented here rather than with platformdirs to keep Vesper's dependency list at
pywebview + packaging. The rules below are the same ones platformdirs applies; if the
dependency is ever taken on, these become thin wrappers.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

APP_DIR_NAME = "vesper"


def _sanitize(name: str) -> str:
    """
    Reduce an app name to something safe to use as a directory name.

    App names come from user config, so they can contain separators or worse; a name
    like "../../evil" must not be able to redirect where state is written.
    """
    cleaned = "".join(c if c.isalnum() or c in "-_. " else "-" for c in name).strip(" .")
    return cleaned or "app"


def config_dir(app_name: str = APP_DIR_NAME) -> Path:
    """
    Directory for persistent per-user state (window geometry, preferences).

    Windows: %LOCALAPPDATA%\\<app>
    macOS:   ~/Library/Application Support/<app>
    Linux:   $XDG_CONFIG_HOME/<app>, or ~/.config/<app>
    """
    app = _sanitize(app_name)

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_CONFIG_HOME")
        root = Path(base) if base else Path.home() / ".config"

    return root / app


def runtime_dir(app_name: str = APP_DIR_NAME) -> Path:
    """
    Directory for transient per-user state (lock files, sockets).

    Prefers XDG_RUNTIME_DIR on Linux, which is user-private (0700) and cleared on
    logout — the right place for a lock that must not outlive the session. Falls back
    to the config directory elsewhere, and to a temp directory as a last resort.
    """
    app = _sanitize(app_name)

    if sys.platform not in ("win32", "darwin"):
        base = os.environ.get("XDG_RUNTIME_DIR")
        if base:
            return Path(base) / app

    try:
        return config_dir(app_name)
    except Exception:
        return Path(tempfile.gettempdir()) / app


def ensure_dir(path: Path) -> Path:
    """Create a directory (and parents) that only the current user can read."""
    path.mkdir(parents=True, exist_ok=True)

    if sys.platform != "win32":
        try:
            path.chmod(0o700)
        except OSError:
            # Best-effort: a directory on a filesystem without POSIX modes still
            # works, it is just not restricted.
            pass

    return path
