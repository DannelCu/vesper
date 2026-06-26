from __future__ import annotations

import os
from pathlib import Path


def read(path: str, encoding: str = "utf-8") -> str:
    """Read a file and return its contents as a string."""
    return Path(path).read_text(encoding=encoding)


def write(path: str, content: str, encoding: str = "utf-8") -> None:
    """Write a string to a file, creating parent directories as needed."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding=encoding)


def exists(path: str) -> bool:
    """Return True if the path exists (file or directory)."""
    return Path(path).exists()


def list_dir(path: str) -> list[dict]:
    """
    List entries in a directory.

    Returns a list of dicts with ``name``, ``path``, and ``is_dir`` keys.
    """
    p = Path(path)
    entries = []
    for entry in sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
        entries.append({
            "name": entry.name,
            "path": str(entry),
            "is_dir": entry.is_dir(),
        })
    return entries
