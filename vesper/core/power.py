"""
Keep the machine awake while the app is doing something the user is waiting on.

macOS:   a ``caffeinate`` subprocess, killed to release the assertion
Windows: SetThreadExecutionState via ctypes
Linux:   ``systemd-inhibit`` if present, otherwise ``xdg-screensaver``

Every backend is resolved lazily and every failure degrades to a no-op: a missing
helper binary or a locked-down desktop must never take down ``app.run()``. Callers
can check the return value when they care whether the request took effect.
"""
from __future__ import annotations

import ctypes
import shutil
import subprocess
import sys
import threading

from vesper.core.logging import get_logger

logger = get_logger("power")

# SetThreadExecutionState flags (winbase.h).
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002

_lock = threading.Lock()
_process: subprocess.Popen | None = None
_active = False


def is_preventing_sleep() -> bool:
    """Whether a sleep-prevention request is currently held."""
    return _active


def prevent_sleep(reason: str = "Vesper app is busy") -> bool:
    """
    Ask the system not to sleep or blank the screen.

    Idempotent: calling it while already active keeps the existing request rather
    than stacking a second one, since only allow_sleep() releases it.

    Returns True when the request was registered.
    """
    global _process, _active

    with _lock:
        if _active:
            return True

        try:
            if sys.platform == "darwin":
                ok = _macos_prevent()
            elif sys.platform == "win32":
                ok = _windows_prevent()
            else:
                ok = _linux_prevent(reason)
        except Exception:
            logger.exception("Could not prevent sleep")
            return False

        _active = ok
        if not ok:
            logger.debug("Sleep prevention unavailable on this system")
        return ok


def allow_sleep() -> bool:
    """
    Release a previous prevent_sleep(). Safe to call when nothing is held.

    Returns True when no request remains.
    """
    global _process, _active

    with _lock:
        if not _active:
            return True

        try:
            if sys.platform == "win32":
                _windows_allow()
            elif _process is not None:
                _process.terminate()
                try:
                    _process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    _process.kill()
        except Exception:
            logger.exception("Could not release sleep prevention")
            return False
        finally:
            _process = None
            _active = False

        return True


# ── macOS ────────────────────────────────────────────────────────────────────


def _macos_prevent() -> bool:
    global _process

    if shutil.which("caffeinate") is None:
        return False

    # -d display, -i idle sleep. The assertion lives as long as the process does.
    _process = subprocess.Popen(
        ["caffeinate", "-d", "-i"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


# ── Windows ──────────────────────────────────────────────────────────────────


def _windows_prevent() -> bool:
    # ES_CONTINUOUS makes the request persist until it is cleared, rather than
    # resetting the idle timer once.
    result = ctypes.windll.kernel32.SetThreadExecutionState(
        _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED | _ES_DISPLAY_REQUIRED
    )
    return result != 0


def _windows_allow() -> None:
    ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)


# ── Linux ────────────────────────────────────────────────────────────────────


def _linux_prevent(reason: str) -> bool:
    global _process

    if shutil.which("systemd-inhibit"):
        # The inhibitor is held for as long as the child runs, so it is parked on
        # a sleep rather than given real work to do.
        _process = subprocess.Popen(
            [
                "systemd-inhibit",
                "--what=idle:sleep",
                "--who=Vesper",
                f"--why={reason}",
                "--mode=block",
                "sleep", "infinity",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True

    if shutil.which("xdg-screensaver"):
        result = subprocess.run(
            ["xdg-screensaver", "reset"], capture_output=True, check=False
        )
        # Only suspends the screensaver momentarily, so it is a weaker guarantee
        # than the systemd path — better than nothing, but not a real inhibitor.
        return result.returncode == 0

    return False
