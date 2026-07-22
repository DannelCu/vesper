"""
Windows 11 backdrop materials (Mica / Acrylic) for the app window.

A cosmetic, best-effort effect: ``set_backdrop()`` returns False anywhere it
cannot apply — non-Windows platforms, Windows 10, builds before the documented
``DWMWA_SYSTEMBACKDROP_TYPE`` attribute — rather than raising. Whether this
machine supports it is answered by ``capabilities.probe()["mica"]``.

Uses ``DwmSetWindowAttribute`` through ctypes; no dependencies. The window handle
comes from ``GetForegroundWindow``, which shares the known weakness of the badge
and progress-bar code: called from a background thread while another app has
focus, it targets the wrong window (see KNOWN-ISSUES.md). Backdrops are set once
at startup in practice, where the app's own window is the foreground one.
"""
from __future__ import annotations

import ctypes
import sys

from vesper.core.logging import get_logger

logger = get_logger("window_effects")

# Documented since Windows 11 22H2 (build 22621); earlier builds reject it.
_DWMWA_SYSTEMBACKDROP_TYPE = 38

_BACKDROPS = {
    "none": 1,      # DWMSBT_NONE
    "mica": 2,      # DWMSBT_MAINWINDOW
    "acrylic": 3,   # DWMSBT_TRANSIENTWINDOW
    "tabbed": 4,    # DWMSBT_TABBEDWINDOW
}

# The build where DWMWA_SYSTEMBACKDROP_TYPE became a documented attribute.
_MIN_BUILD = 22621


def supported() -> bool:
    """Whether this machine can apply a backdrop at all."""
    if sys.platform != "win32":
        return False
    try:
        return sys.getwindowsversion().build >= _MIN_BUILD
    except Exception:
        return False


def set_backdrop(kind: str = "mica") -> bool:
    """
    Apply a Windows 11 backdrop material to the app window.

    Args:
        kind: "mica", "acrylic", "tabbed", or "none" to remove.

    Returns:
        True when DWM accepted the attribute; False on any platform or build
        that cannot apply it, or when *kind* is unknown.
    """
    value = _BACKDROPS.get(kind)
    if value is None:
        logger.debug("Unknown backdrop kind %r", kind)
        return False

    if not supported():
        logger.debug("Backdrop materials unavailable on this system")
        return False

    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return False

    backdrop = ctypes.c_int(value)
    result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
        hwnd,
        _DWMWA_SYSTEMBACKDROP_TYPE,
        ctypes.byref(backdrop),
        ctypes.sizeof(backdrop),
    )
    # DwmSetWindowAttribute returns an HRESULT: zero is S_OK. A Windows 10 build
    # that slipped past the version gate answers E_INVALIDARG here, which is the
    # honest no rather than an error.
    return result == 0
