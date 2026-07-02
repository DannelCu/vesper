from __future__ import annotations

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
