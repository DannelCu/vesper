from __future__ import annotations

from pathlib import Path


class FsScopeError(Exception):
    """Raised when a filesystem path falls outside the allowed scope."""


class FsScope:
    """
    Validates that filesystem paths stay within an allowed set of roots.

    A scope is a list of allowed root directories. Any path resolved
    (symlinks included) outside every root is rejected. The special
    value "*" disables all checks (opt-in, explicit).
    """

    def __init__(self, roots: list[str] | str | None) -> None:
        self._allow_all = roots == "*"
        self._roots: list[Path] = []
        if not self._allow_all and roots:
            for r in (roots if isinstance(roots, list) else [roots]):
                self._roots.append(Path(r).expanduser().resolve())

    def check(self, path: str) -> Path:
        """Resolve *path* and ensure it is inside the scope. Returns the resolved Path."""
        resolved = Path(path).expanduser().resolve()
        if self._allow_all:
            return resolved
        for root in self._roots:
            try:
                resolved.relative_to(root)
                return resolved
            except ValueError:
                continue
        raise FsScopeError(f"Path outside allowed scope: {path}")
