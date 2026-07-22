"""
Run external binaries on behalf of the frontend, behind a declarative allowlist.

The design mirrors the filesystem sandbox: where paths pass through ``FsScope``,
process invocations pass through :class:`ShellScope`. The frontend never names an
arbitrary executable — the app declares up front which binaries (and optionally
which argument shapes) it is willing to run, and everything else is rejected
before a process is ever created. With no scope configured the API rejects
*everything*: secure by default, like an ``FsScope`` with no roots.

Commands are always argv lists and never touch a shell — there is no
``shell=True`` here and no string interpolation, so quoting bugs and shell
injection are structurally impossible rather than carefully avoided.
"""
from __future__ import annotations

import fnmatch
import itertools
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

from vesper.core.logging import get_logger

logger = get_logger("process")

# How long kill() waits for a polite terminate before escalating.
_TERMINATE_GRACE_SECONDS = 1.5


class ShellScopeError(Exception):
    """Raised when a process invocation falls outside the allowed scope."""


class ShellScope:
    """
    Allowlist of executables the app may run, with optional argument patterns.

    Accepts either a list of executables (any arguments allowed):

        ShellScope(["ffmpeg", "/usr/bin/git"])

    or a dict mapping each executable to a list of ``fnmatch`` patterns — every
    argument must match at least one pattern (``None`` allows any arguments):

        ShellScope({
            "ffmpeg": ["-i", "*.mp4", "*.webm", "-vcodec", "libvpx"],
            "git": None,
        })

    An entry given as a bare name allows invocation by that name (resolved via
    PATH at exec time). An entry given as a path allows invocation by that exact
    resolved path. The two deliberately do not cross-match: allowing ``"git"``
    must not allow running ``/tmp/evil/git`` by path.
    """

    def __init__(self, allowed: dict | list | None) -> None:
        self._by_name: dict[str, list[str] | None] = {}
        self._by_path: dict[Path, list[str] | None] = {}

        entries = (
            allowed.items() if isinstance(allowed, dict)
            else [(exe, None) for exe in (allowed or [])]
        )
        for exe, patterns in entries:
            patterns = list(patterns) if patterns is not None else None
            if Path(exe).name != exe:
                self._by_path[Path(exe).expanduser().resolve()] = patterns
            else:
                self._by_name[exe] = patterns

    def check(self, argv: list[str]) -> list[str]:
        """Validate *argv* against the scope. Returns it unchanged, or raises."""
        if not argv:
            raise ShellScopeError("Empty command.")

        exe = str(argv[0])
        if Path(exe).name != exe:
            patterns = self._by_path.get(Path(exe).expanduser().resolve(), _MISSING)
        else:
            patterns = self._by_name.get(exe, _MISSING)

        if patterns is _MISSING:
            raise ShellScopeError(f"Executable not allowed by shell scope: {exe}")

        if patterns is not None:
            for arg in argv[1:]:
                if not any(fnmatch.fnmatch(str(arg), pat) for pat in patterns):
                    raise ShellScopeError(
                        f"Argument not allowed by shell scope for {exe}: {arg}"
                    )

        return [str(a) for a in argv]


# Sentinel distinguishing "not in the allowlist" from "allowed with any args".
_MISSING = object()


def _require_scope(scope: ShellScope | None) -> ShellScope:
    if scope is None:
        raise ShellScopeError(
            "No shell scope configured. Pass shell_scope=[...] to App to allow "
            "specific executables; without one, all process execution is rejected."
        )
    return scope


def run(
    argv: list[str],
    *,
    scope: ShellScope | None,
    cwd: str | None = None,
    timeout: float | None = None,
) -> dict:
    """
    Run a command to completion and capture its output.

    Returns ``{"code": int, "stdout": str, "stderr": str}``. A nonzero exit code
    is a result, not an exception — the caller decides what failure means.

    Raises:
        ShellScopeError: no scope configured, or the invocation falls outside it.
        subprocess.TimeoutExpired: *timeout* elapsed (the process is killed).
    """
    argv = _require_scope(scope).check(argv)
    result = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
        timeout=timeout,
    )
    return {"code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


class ProcessManager:
    """
    Long-running processes with streamed output.

    ``spawn`` starts a process and returns an id; its stdout and stderr are
    emitted line by line as ``vesper:process:stdout`` / ``vesper:process:stderr``
    events (payload ``{id, line}``), and ``vesper:process:exit`` (``{id, code}``)
    fires once when it finishes. ``kill_all()`` runs at app teardown so a closed
    window never leaves orphan children behind.
    """

    def __init__(self, emit: Callable[[str, dict], None]) -> None:
        self._emit = emit
        self._procs: dict[int, subprocess.Popen] = {}
        self._lock = threading.Lock()
        self._ids = itertools.count(1)

    def spawn(
        self,
        argv: list[str],
        *,
        scope: ShellScope | None,
        cwd: str | None = None,
    ) -> int:
        argv = _require_scope(scope).check(argv)
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=cwd,
        )
        proc_id = next(self._ids)
        with self._lock:
            self._procs[proc_id] = proc

        readers = [
            threading.Thread(
                target=self._pump, args=(proc_id, proc.stdout, "process:stdout"), daemon=True
            ),
            threading.Thread(
                target=self._pump, args=(proc_id, proc.stderr, "process:stderr"), daemon=True
            ),
        ]
        for t in readers:
            t.start()

        threading.Thread(
            target=self._watch_exit, args=(proc_id, proc, readers), daemon=True
        ).start()
        return proc_id

    def _pump(self, proc_id: int, stream, event: str) -> None:
        try:
            for line in stream:
                self._safe_emit(event, {"id": proc_id, "line": line.rstrip("\r\n")})
        except ValueError:
            # The stream was closed under the reader by a kill; the exit event
            # still fires, so there is nothing to report here.
            pass

    def _watch_exit(self, proc_id: int, proc: subprocess.Popen, readers: list) -> None:
        # Drain before wait: exit must be the last event a listener sees.
        for t in readers:
            t.join()
        code = proc.wait()
        with self._lock:
            self._procs.pop(proc_id, None)
        self._safe_emit("process:exit", {"id": proc_id, "code": code})

    def _safe_emit(self, event: str, payload: dict) -> None:
        try:
            self._emit(event, payload)
        except Exception:
            # Reader threads must survive a window that is mid-teardown.
            logger.debug("Could not emit %s for a spawned process", event)

    def kill(self, proc_id: int) -> bool:
        """
        Terminate a spawned process, escalating to SIGKILL after a grace period.

        Returns False for an unknown or already-finished id.
        """
        with self._lock:
            proc = self._procs.get(proc_id)
        if proc is None:
            return False

        proc.terminate()
        try:
            proc.wait(timeout=_TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=_TERMINATE_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                logger.warning("Spawned process %d did not die after SIGKILL", proc_id)
                return False
        return True

    def kill_all(self) -> None:
        """Terminate every process still running. Called at app teardown."""
        with self._lock:
            ids = list(self._procs)
        for proc_id in ids:
            self.kill(proc_id)
