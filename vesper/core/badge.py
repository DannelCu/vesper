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

===========  ========================  =================================
Platform     Progress                  Badge
===========  ========================  =================================
macOS        Dock tile (pyobjc)        Dock tile (pyobjc)
Windows      ITaskbarList3 (comtypes)  Overlay icon (ITaskbarList3 + PIL)
Linux        Unity LauncherEntry       Unity LauncherEntry
===========  ========================  =================================

The Linux path needs a desktop that still implements the Unity LauncherEntry D-Bus
protocol — KDE Plasma and Dash-to-Dock do, plain GNOME does not — so it is a no-op
on most systems.

Windows has no numeric badge; what it has is a small icon overlaid on the taskbar
button. The number is therefore rendered into an icon at runtime with Pillow, which
is an optional dependency (``vesper[tray]``) — without it the badge is a no-op while
progress, which needs no image, keeps working. Counts above 99 are drawn as a plain
dot, since three digits in a 16px circle is a smudge.
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


# Windows has no numeric badge like the macOS dock. What it has is a small icon
# drawn over the corner of the taskbar button, and the number has to be rendered
# into that icon at runtime.

_BADGE_PX = 32              # rendered once; the .ico also carries a 16px version
_BADGE_ICO_SIZES = [(16, 16), (32, 32)]
_BADGE_BG = (196, 43, 28, 255)      # the red Windows itself uses for alerts
_BADGE_FG = (255, 255, 255, 255)
_BADGE_MAX = 99             # above this a digit is unreadable at 16px; draw a dot

# Kept so the previous icon can be released when the next one replaces it. The
# taskbar copies the icon, but destroying it immediately after the call would rely
# on that; holding it one generation costs one handle and needs no assumption.
_win_overlay_icon = None


def _windows_badge_image(number: int):
    """
    Render the badge as a Pillow image, or None when Pillow is unavailable.

    Returns an image even for counts above _BADGE_MAX — a filled dot with no
    number, since three digits inside a 16px circle is a smudge, and "there is
    something" is the whole message a badge carries.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        _warn_once(
            "win-badge-pillow",
            "Pillow not available; install vesper[tray] for taskbar badges",
        )
        return None

    image = Image.new("RGBA", (_BADGE_PX, _BADGE_PX), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((0, 0, _BADGE_PX - 1, _BADGE_PX - 1), fill=_BADGE_BG)

    if number > _BADGE_MAX:
        return image

    text = str(number)
    font = _badge_font(len(text))
    if font is not None:
        # anchor="mm" centres on the glyph's own middle rather than its baseline,
        # which is what keeps a "1" and a "48" both sitting in the circle.
        draw.text(
            (_BADGE_PX / 2, _BADGE_PX / 2), text,
            fill=_BADGE_FG, font=font, anchor="mm",
        )

    return image


def _badge_font(digits: int):
    """A font sized to fit `digits` characters in the circle, or None if none loads."""
    size = 22 if digits == 1 else 17

    from PIL import ImageFont

    try:
        # Present on every Windows install; the bold weight reads better small.
        return ImageFont.truetype("arialbd.ttf", size)
    except OSError:
        pass

    try:
        return ImageFont.load_default(size=size)   # Pillow >= 10.1
    except (TypeError, AttributeError):
        # Older Pillow: a fixed tiny bitmap font. Ugly, but a legible-ish badge
        # beats no badge.
        return ImageFont.load_default()


def _windows_badge_hicon(number: int):
    """
    Build an HICON for the count, or None when it could not be produced.

    Goes through a temporary .ico file and LoadImageW rather than building a
    bitmap and calling CreateIconIndirect: Pillow already writes .ico, and this
    trades a few GDI calls that are easy to get subtly wrong for one file write.
    Badge counts change rarely, so the file is not on any hot path.
    """
    image = _windows_badge_image(number)
    if image is None:
        return None

    import ctypes
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "badge.ico"
        image.save(path, format="ICO", sizes=_BADGE_ICO_SIZES)

        hicon = ctypes.windll.user32.LoadImageW(
            None, str(path), _IMAGE_ICON, 0, 0, _LR_LOADFROMFILE | _LR_DEFAULTSIZE
        )

    return hicon or None


_IMAGE_ICON = 1
_LR_LOADFROMFILE = 0x00000010
_LR_DEFAULTSIZE = 0x00000040


def _windows_set_overlay(hicon, description: str) -> bool:
    """
    Apply (or with hicon=None, remove) the taskbar overlay icon.

    Returns True when the taskbar accepted it.
    """
    global _win_overlay_icon

    taskbar = _windows_taskbar()
    hwnd = _windows_hwnd()
    if taskbar is None or not hwnd:
        return False

    taskbar.SetOverlayIcon(hwnd, hicon, description)

    previous, _win_overlay_icon = _win_overlay_icon, hicon
    if previous:
        try:
            import ctypes

            ctypes.windll.user32.DestroyIcon(previous)
        except Exception:
            logger.debug("Could not destroy the previous overlay icon")

    return True


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
            hicon = _windows_badge_hicon(number)
            if hicon is None:
                return False
            # The description is what a screen reader announces, so it says the
            # real count even when the icon had to fall back to a dot.
            return _windows_set_overlay(hicon, f"{number} unread")

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
            # A null overlay icon is how the taskbar is told to remove it.
            return _windows_set_overlay(None, "")

        return _linux_launcher_update({"count-visible": False})
    except Exception:
        logger.exception("Could not clear badge")
        return False
