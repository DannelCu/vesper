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

    The roots can be replaced while the app runs — see :meth:`set_roots`.
    """

    def __init__(self, roots: list[str] | str | None) -> None:
        self._allow_all = False
        self._roots: list[Path] = []
        self.set_roots(roots)

    def set_roots(self, roots: list[str] | str | None) -> None:
        """
        Replace the allowed roots in place.

        For apps whose working directory is chosen by the user — a folder
        picker, a "recent project" list — the scope worth enforcing is not known
        when the ``App`` is constructed. The commands registered on the App hold
        a reference to *this object*, so updating it here is what reaches them;
        assigning a new ``FsScope`` to ``app.fs_scope`` would not, since the
        commands captured the original.

        Narrowing is the intended use. Widening works too, and is the caller's
        decision to justify: this is a Python-side API, never reachable from the
        frontend, so the app always chooses its own boundary.

            app.fs_scope.set_roots([chosen_folder])
        """
        self._allow_all = roots == "*"
        self._roots = []
        if not self._allow_all and roots:
            for r in (roots if isinstance(roots, list) else [roots]):
                self._roots.append(Path(r).expanduser().resolve())

    @property
    def roots(self) -> list[Path]:
        """The resolved roots currently allowed. Empty when everything is denied."""
        return list(self._roots)

    @property
    def allows_everything(self) -> bool:
        """Whether this scope was built with "*" and checks nothing."""
        return self._allow_all

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
