"""
Taskbar progress and dock badges.

    set_progress(0.4)   # 40% bar on the taskbar button / dock icon
    clear_progress()
    set_badge(3)        # "3" on the dock icon / an overlay on the taskbar
    clear_badge()

Support is uneven and this module is honest about it: every function returns a bool,
returns False where the platform cannot do it, and never raises. The native
dependencies (pyobjc, comtypes, dbus) are imported lazily inside each backend so a
missing one degrades to a no-op instead of breaking ``import vesper``.

Current support:

===========  ========================  =====================
Platform     Progress                  Badge
===========  ========================  =====================
macOS        Dock tile (pyobjc)        Dock tile (pyobjc)
Windows      ITaskbarList3 (comtypes)  Not implemented
Linux        Unity LauncherEntry       Unity LauncherEntry
===========  ========================  =====================

The Linux path needs a desktop that still implements the Unity LauncherEntry D-Bus
protocol — KDE Plasma and Dash-to-Dock do, plain GNOME does not — so it is a no-op
on most systems.

Windows badges are left unimplemented rather than half-done: an overlay icon has to
be a real HICON, so rendering a number means generating a bitmap at runtime, which
is more machinery than the feature earns.
"""
from __future__ import annotations

import sys

from vesper.core.logging import get_logger

logger = get_logger("badge")

# Set once a backend has been found to be unavailable, so a desktop without support
# logs the reason once instead of on every progress update.
_warned: set[str] = set()


def _warn_once(key: str, message: str) -> None:
    if key not in _warned:
        _warned.add(key)
        logger.debug(message)


def _clamp(fraction: float) -> float:
    try:
        value = float(fraction)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, value))


# ── macOS ────────────────────────────────────────────────────────────────────


def _macos_set_badge(text: str) -> bool:
    try:
        from AppKit import NSApplication
    except ImportError:
        _warn_once("macos", "pyobjc not available; dock badge disabled")
        return False

    tile = NSApplication.sharedApplication().dockTile()
    tile.setBadgeLabel_(text)
    tile.display()
    return True


# ── Windows ──────────────────────────────────────────────────────────────────

_TBPF_NOPROGRESS = 0x0
_TBPF_NORMAL = 0x2


def _windows_taskbar():
    """The ITaskbarList3 instance, or None when unavailable."""
    try:
        import comtypes.client
        from comtypes import GUID
    except ImportError:
        _warn_once("windows", "comtypes not available; taskbar progress disabled")
        return None

    try:
        taskbar = comtypes.client.CreateObject(
            GUID("{56FDF344-FD6D-11d0-958A-006097C9A090}"),
            interface=comtypes.client.GetModule("shell32.dll").ITaskbarList3,
        )
        taskbar.HrInit()
        return taskbar
    except Exception:
        _warn_once("windows", "Could not create ITaskbarList3; taskbar progress disabled")
        return None


def _windows_hwnd():
    """Foreground window handle, which is this app's window while it has focus."""
    try:
        import ctypes

        return ctypes.windll.user32.GetForegroundWindow()
    except Exception:
        return None


# ── Linux ────────────────────────────────────────────────────────────────────


def _linux_launcher_update(properties: dict) -> bool:
    """Broadcast a Unity LauncherEntry update over D-Bus."""
    try:
        import dbus
    except ImportError:
        _warn_once("linux", "dbus not available; launcher progress disabled")
        return False

    try:
        bus = dbus.SessionBus()
        message = dbus.lowlevel.SignalMessage(
            "/org/vesper/LauncherEntry",
            "com.canonical.Unity.LauncherEntry",
            "Update",
        )
        message.append("application://vesper.desktop", properties, signature="sa{sv}")
        bus.send_message(message)
        bus.flush()
        return True
    except Exception:
        _warn_once("linux", "Unity LauncherEntry update failed; launcher progress disabled")
        return False


# ── public API ───────────────────────────────────────────────────────────────


def set_progress(fraction: float) -> bool:
    """
    Show a progress bar on the taskbar button or dock icon.

    Args:
        fraction: 0.0 to 1.0. Values outside the range are clamped rather than
                  rejected, since a caller computing i/total can legitimately
                  produce a rounding overshoot.

    Returns:
        True when the platform applied it.
    """
    value = _clamp(fraction)

    try:
        if sys.platform == "darwin":
            # No dock progress bar exists, so the percentage goes in the badge —
            # visible in the same place and better than showing nothing.
            return _macos_set_badge(f"{int(value * 100)}%")

        if sys.platform == "win32":
            taskbar = _windows_taskbar()
            hwnd = _windows_hwnd()
            if taskbar is None or not hwnd:
                return False
            taskbar.SetProgressState(hwnd, _TBPF_NORMAL)
            taskbar.SetProgressValue(hwnd, int(value * 100), 100)
            return True

        return _linux_launcher_update({"progress": value, "progress-visible": True})
    except Exception:
        logger.exception("Could not set progress")
        return False


def clear_progress() -> bool:
    """Remove the progress indicator. Returns True when the platform applied it."""
    try:
        if sys.platform == "darwin":
            return _macos_set_badge("")

        if sys.platform == "win32":
            taskbar = _windows_taskbar()
            hwnd = _windows_hwnd()
            if taskbar is None or not hwnd:
                return False
            taskbar.SetProgressState(hwnd, _TBPF_NOPROGRESS)
            return True

        return _linux_launcher_update({"progress-visible": False})
    except Exception:
        logger.exception("Could not clear progress")
        return False


def set_badge(count: int) -> bool:
    """
    Show a count on the dock or launcher icon.

    A count of 0 clears it, matching how mail and chat apps behave.
    """
    try:
        number = max(0, int(count))
    except (TypeError, ValueError):
        return False

    if number == 0:
        return clear_badge()

    try:
        if sys.platform == "darwin":
            return _macos_set_badge(str(number))

        if sys.platform == "win32":
            # Deliberately unimplemented — see the module docstring.
            _warn_once("win-badge", "Taskbar badges are not supported on Windows")
            return False

        return _linux_launcher_update({"count": number, "count-visible": True})
    except Exception:
        logger.exception("Could not set badge")
        return False


def clear_badge() -> bool:
    """Remove the count. Returns True when the platform applied it."""
    try:
        if sys.platform == "darwin":
            return _macos_set_badge("")

        if sys.platform == "win32":
            return False

        return _linux_launcher_update({"count-visible": False})
    except Exception:
        logger.exception("Could not clear badge")
        return False
