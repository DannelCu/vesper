from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from vesper.core.fs_scope import FsScope


def read(path: str, encoding: str = "utf-8", *, scope: FsScope | None = None) -> str:
    """Read a file and return its contents as a string."""
    p = scope.check(path) if scope else Path(path)
    return Path(p).read_text(encoding=encoding)


def write(path: str, content: str, encoding: str = "utf-8", *, scope: FsScope | None = None) -> None:
    """Write a string to a file, creating parent directories as needed."""
    p = Path(scope.check(path) if scope else Path(path))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding=encoding)


def exists(path: str, *, scope: FsScope | None = None) -> bool:
    """Return True if the path exists (file or directory)."""
    p = scope.check(path) if scope else Path(path)
    return Path(p).exists()


def trash(path: str, *, scope: FsScope | None = None) -> bool:
    """
    Move a file or directory to the system trash instead of deleting it.

    Goes through send2trash when available (``pip install "vesper[trash]"``), which
    handles the platform trash specifications properly — including the .trashinfo
    metadata that makes "restore" work on Linux. Without it, falls back to the
    platform's own tool.

    Deliberately never falls back to an outright delete: silently making a
    recoverable operation permanent is worse than reporting that it is unavailable.

    Raises:
        FileNotFoundError: the path does not exist.
        RuntimeError:      no trash backend is available on this system.
    """
    p = Path(scope.check(path) if scope else Path(path))

    if not p.exists():
        raise FileNotFoundError(f"No such file or directory: {path}")

    target = str(p.resolve())

    try:
        from send2trash import send2trash as _send2trash
    except ImportError:
        return _trash_fallback(target)

    _send2trash(target)
    return True


def _trash_fallback(target: str) -> bool:
    """Platform trash without send2trash. Returns True on success."""
    if sys.platform == "darwin":
        # POSIX file paths are what the Finder scripting interface expects.
        script = f'tell application "Finder" to delete POSIX file {json.dumps(target)}'
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, check=False
        )
        if result.returncode == 0:
            return True

    elif sys.platform == "win32":
        # PowerShell's RecycleBin cmdlet ships with Windows 10+.
        script = (
            "Add-Type -AssemblyName Microsoft.VisualBasic;"
            "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("
            f"{_ps_quote(target)},'OnlyErrorDialogs','SendToRecycleBin')"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return True

    else:
        # gio is part of GLib and present on any desktop that has a trash at all.
        result = subprocess.run(
            ["gio", "trash", "--", target], capture_output=True, check=False
        )
        if result.returncode == 0:
            return True

    raise RuntimeError(
        "No trash backend available. Install it with: pip install \"vesper[trash]\""
    )


def _ps_quote(value: str) -> str:
    """Quote a string for a PowerShell single-quoted literal."""
    return "'" + value.replace("'", "''") + "'"


def list_dir(path: str, *, scope: FsScope | None = None) -> list[dict]:
    """
    List entries in a directory.

    Returns a list of dicts with ``name``, ``path``, and ``is_dir`` keys.
    """
    p = Path(scope.check(path) if scope else Path(path))
    entries = []
    for entry in sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
        entries.append({
            "name": entry.name,
            "path": str(entry),
            "is_dir": entry.is_dir(),
        })
    return entries
