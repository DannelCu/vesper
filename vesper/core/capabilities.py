"""
What optional backends are actually available on this machine.

Vesper's optional features already degrade cleanly when their backend is missing —
``clipboard.read_image()`` returns None, ``badge.set_badge()`` returns False. This
module exists so that degradation is never *silent*: the same answers feed
``vesper doctor``, the ``vesper:capabilities`` command the frontend can query, and
the startup preflight warning.

It is the single source of truth for those three. Detection is deliberately dumb —
``shutil.which`` and ``importlib.util.find_spec``, nothing more. Nothing here
imports a backend, spawns a process, or builds an object; ``probe()`` is safe to
call at startup and safe to call repeatedly.

The native WebView is **not** probed here. That check lives in
``doctor._detect_webview_backend``, which has to actually import the backend module
to be meaningful, and it is a critical dependency rather than an optional one.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys


def _has_module(name: str) -> bool:
    """Whether a module could be imported, without importing it."""
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        # A namespace package with a broken parent raises rather than returning
        # None. Unimportable is unimportable.
        return False


def _has_binary(name: str) -> bool:
    return shutil.which(name) is not None


def _entry(available: bool, detail: str, fix: str | None = None) -> dict:
    # `fix` only means something when the capability is missing; carrying one on an
    # available capability would put a "run this" string in front of a user who has
    # nothing to run.
    return {
        "available": available,
        "detail": detail,
        "fix": None if available else fix,
    }


# Per-distro install lines, since "install xclip" is not actionable on its own.
_LINUX_XCLIP_FIX = "sudo apt install xclip  (Fedora: dnf install xclip, Arch: pacman -S xclip)"
_LINUX_NOTIFY_FIX = (
    "sudo apt install libnotify-bin  (Fedora: dnf install libnotify, "
    "Arch: pacman -S libnotify)"
)


def _probe_clipboard_text() -> dict:
    if sys.platform == "win32":
        return _entry(True, "PowerShell Get-Clipboard / Set-Clipboard")
    if sys.platform == "darwin":
        return _entry(True, "pbcopy / pbpaste")

    ok = _has_binary("xclip")
    return _entry(
        ok,
        "xclip" if ok else "xclip not found",
        _LINUX_XCLIP_FIX,
    )


def _probe_clipboard_image() -> dict:
    if sys.platform == "win32":
        return _entry(True, "System.Windows.Forms.Clipboard")
    if sys.platform == "darwin":
        return _entry(True, "osascript")

    # Same binary as the text clipboard, but reported separately: an app can use one
    # without the other, and the frontend asks about them independently.
    ok = _has_binary("xclip")
    return _entry(
        ok,
        "xclip" if ok else "xclip not found",
        _LINUX_XCLIP_FIX,
    )


def _probe_clipboard_files() -> dict:
    if sys.platform == "win32":
        return _entry(True, "CF_HDROP via ctypes")
    if sys.platform == "darwin":
        return _entry(True, "osascript POSIX file")

    # The same xclip that backs text and images, speaking text/uri-list — one
    # install story, reported per capability like the other two.
    ok = _has_binary("xclip")
    return _entry(
        ok,
        "xclip (text/uri-list)" if ok else "xclip not found",
        _LINUX_XCLIP_FIX,
    )


def _probe_notifications() -> dict:
    if sys.platform == "win32":
        return _entry(True, "PowerShell toast notification")
    if sys.platform == "darwin":
        return _entry(True, "osascript")

    ok = _has_binary("notify-send")
    return _entry(
        ok,
        "notify-send" if ok else "notify-send not found",
        _LINUX_NOTIFY_FIX,
    )


def _probe_trash() -> dict:
    if _has_module("send2trash"):
        return _entry(True, "send2trash")

    if sys.platform == "win32":
        return _entry(True, "PowerShell RecycleBin")
    if sys.platform == "darwin":
        return _entry(True, "Finder via osascript")

    ok = _has_binary("gio")
    return _entry(
        ok,
        "gio trash" if ok else "send2trash not installed and gio not found",
        'pip install "vesper[trash]"',
    )


def _probe_keep_awake() -> dict:
    if sys.platform == "win32":
        return _entry(True, "SetThreadExecutionState")

    if sys.platform == "darwin":
        ok = _has_binary("caffeinate")
        return _entry(
            ok,
            "caffeinate" if ok else "caffeinate not found",
            "caffeinate ships with macOS; a missing one means a damaged install",
        )

    if _has_binary("systemd-inhibit"):
        return _entry(True, "systemd-inhibit")
    if _has_binary("xdg-screensaver"):
        # Weaker than a real inhibitor — it defers the screensaver only — but it is
        # what prevent_sleep() will use, so reporting it as available is honest.
        return _entry(True, "xdg-screensaver (screensaver only, not a sleep inhibitor)")

    return _entry(
        False,
        "neither systemd-inhibit nor xdg-screensaver found",
        "sudo apt install systemd  (or xdg-utils for the weaker fallback)",
    )


def _probe_tray() -> dict:
    missing = [name for name in ("pystray", "PIL") if not _has_module(name)]
    if not missing:
        return _entry(True, "pystray + Pillow")

    return _entry(
        False,
        f"missing: {', '.join(missing)}",
        'pip install "vesper[tray]"',
    )


def _probe_badge() -> dict:
    if sys.platform == "darwin":
        ok = _has_module("AppKit")
        return _entry(
            ok,
            "dock tile via pyobjc" if ok else "pyobjc (AppKit) not importable",
            "pip install pyobjc-framework-Cocoa",
        )

    if sys.platform == "win32":
        ok = _has_module("comtypes")
        return _entry(
            ok,
            "taskbar overlay via comtypes" if ok else "comtypes not importable",
            "pip install comtypes",
        )

    # Linux speaks the Unity LauncherEntry protocol, which plain GNOME — the most
    # common desktop — does not implement. Whether the D-Bus call lands cannot be
    # known without making it, so this reports unavailable rather than claiming a
    # capability that is a no-op on most systems.
    return _entry(
        False,
        "no cross-desktop badge protocol on Linux (Unity LauncherEntry only)",
        None,
    )


def _probe_power_events() -> dict:
    """
    Whether suspend/resume/lock/unlock events can be delivered.

    Windows and macOS need nothing installed — the message window and the
    NSWorkspace observers use what ships with the OS (pyobjc arrives with
    pywebview). Linux goes through D-Bus and needs jeepney.
    """
    if sys.platform == "win32":
        return _entry(True, "WM_POWERBROADCAST + WTS session notifications")

    if sys.platform == "darwin":
        ok = _has_module("AppKit")
        return _entry(
            ok,
            "NSWorkspace notifications" if ok else "pyobjc (AppKit) not importable",
            "pip install pyobjc-framework-Cocoa",
        )

    ok = _has_module("jeepney")
    return _entry(
        ok,
        "logind + screensaver over D-Bus" if ok else "jeepney not importable",
        "pip install jeepney",
    )


def _probe_mica() -> dict:
    """
    Windows 11 backdrop materials (Mica / Acrylic).

    Purely a platform fact — there is nothing to install — so like the Linux badge
    this reports N/A without a fix everywhere it cannot work.
    """
    if sys.platform != "win32":
        return _entry(False, "backdrop materials are Windows 11 only", None)

    from vesper.core import window_effects

    ok = window_effects.supported()
    return _entry(
        ok,
        "DwmSetWindowAttribute backdrop" if ok
        else "requires Windows 11 22H2 (build 22621) or newer",
        None,
    )


def _probe_nsis() -> dict:
    """
    NSIS, for Windows installers.

    The core never drives makensis (external, non-pip tooling) — this exists so
    `vesper doctor` can say whether the recipe in
    docs/recipes/windows-installer.md is runnable on this machine.
    """
    ok = _has_binary("makensis")
    if sys.platform == "win32":
        fix = "winget install NSIS  (or download from https://nsis.sourceforge.io)"
    elif sys.platform == "darwin":
        fix = "brew install makensis"
    else:
        fix = "sudo apt install nsis  (Fedora: dnf install mingw32-nsis, Arch: pacman -S nsis)"
    return _entry(ok, "makensis" if ok else "makensis not found", fix)


def _probe_global_shortcuts() -> dict:
    # Belongs to the vesper-shortcuts plugin rather than the core, but it is
    # reported here because the frontend asking "can I offer this?" does not care
    # which distribution the answer comes from.
    ok = _has_module("pynput")
    return _entry(
        ok,
        "pynput" if ok else "pynput not importable",
        "pip install vesper-shortcuts",
    )


_PROBES = {
    "clipboard_text": _probe_clipboard_text,
    "clipboard_image": _probe_clipboard_image,
    "clipboard_files": _probe_clipboard_files,
    "notifications": _probe_notifications,
    "trash": _probe_trash,
    "keep_awake": _probe_keep_awake,
    "tray": _probe_tray,
    "badge": _probe_badge,
    "mica": _probe_mica,
    "nsis": _probe_nsis,
    "power_events": _probe_power_events,
    "global_shortcuts": _probe_global_shortcuts,
}


def probe() -> dict[str, dict]:
    """
    Report every optional capability.

    Returns a dict keyed by capability name, each value being
    ``{"available": bool, "detail": str, "fix": str | None}``.

    Not cached: a user can install xclip while the app is running, and the cost is
    a handful of PATH lookups.
    """
    return {name: check() for name, check in _PROBES.items()}


def is_available(name: str) -> bool:
    """
    Whether one capability is available. Unknown names are False.

    A convenience for the callers that need a single answer and would otherwise
    probe everything to read one key.
    """
    check = _PROBES.get(name)
    return check()["available"] if check is not None else False


def available_map() -> dict[str, bool]:
    """
    Just the booleans, for the frontend.

    The `fix` strings are deliberately left out: they are install instructions for
    whoever runs the app, not something a web UI should render.
    """
    return {name: entry["available"] for name, entry in probe().items()}
