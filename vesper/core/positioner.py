"""
Semantic window positioning: "top-right of monitor 2" instead of raw pixels.

The arithmetic is pure and works from the screen list `Window.list_screens()`
already provides, so multi-monitor layouts — including monitors left of or above
the primary, whose coordinates are negative — fall out of the same code path.

The target monitor can be picked by index or by where the cursor is. Cursor
lookup uses only what the platform already ships (ctypes on Windows, pyobjc —
a pywebview dependency — on macOS); on Linux there is no dependency-free way to
ask, so "cursor" degrades to the primary monitor. What this module deliberately
does **not** offer is positioning relative to the tray icon itself: pystray does
not expose the icon's coordinates on any platform. The supported pattern for
menubar/tray apps is "corner of the active monitor", which is what most of the
ecosystem ships — see docs/window-controls.md.
"""
from __future__ import annotations

import sys

from vesper.core.logging import get_logger

logger = get_logger("positioner")

POSITIONS = frozenset({
    "top-left", "top-center", "top-right",
    "center-left", "center", "center-right",
    "bottom-left", "bottom-center", "bottom-right",
})


def compute(
    position: str,
    window_size: tuple[int, int],
    screens: list[dict],
    screen_index: int | None = None,
    offset: tuple[int, int] = (0, 0),
) -> tuple[int, int]:
    """
    The (x, y) that places a window of *window_size* at *position* on a screen.

    Args:
        position:     One of :data:`POSITIONS`.
        window_size:  (width, height) of the window being placed.
        screens:      As returned by ``Window.list_screens()`` — dicts with
                      ``width``, ``height``, ``x``, ``y``.
        screen_index: Which screen; None means the primary (index 0).
        offset:       Added to the result as-is. Use negative values to pull a
                      bottom/right-anchored window away from the edge.

    Raises:
        ValueError: unknown position name, no screens, or index out of range.
    """
    if position not in POSITIONS:
        raise ValueError(
            f"Unknown position {position!r}. Valid: {', '.join(sorted(POSITIONS))}"
        )
    if not screens:
        raise ValueError("No screens reported by the backend.")

    index = 0 if screen_index is None else screen_index
    if not 0 <= index < len(screens):
        raise ValueError(f"Screen index {index} out of range (0..{len(screens) - 1}).")

    screen = screens[index]
    sx, sy = int(screen.get("x", 0)), int(screen.get("y", 0))
    sw, sh = int(screen["width"]), int(screen["height"])
    ww, wh = window_size

    vertical, _, horizontal = (
        ("center", "", "center") if position == "center" else position.partition("-")
    )

    x = {
        "left": sx,
        "center": sx + (sw - ww) // 2,
        "right": sx + sw - ww,
    }[horizontal]
    y = {
        "top": sy,
        "center": sy + (sh - wh) // 2,
        "bottom": sy + sh - wh,
    }[vertical]

    return x + offset[0], y + offset[1]


def cursor_position() -> tuple[int, int] | None:
    """
    The cursor's global position, or None where it cannot be asked without
    dependencies (Linux, or any platform failure).
    """
    try:
        if sys.platform == "win32":
            import ctypes
            import ctypes.wintypes

            point = ctypes.wintypes.POINT()
            if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
                return int(point.x), int(point.y)
            return None

        if sys.platform == "darwin":
            from AppKit import NSEvent, NSScreen

            location = NSEvent.mouseLocation()
            # Cocoa's origin is the bottom-left of the primary screen; the
            # coordinates the rest of the stack uses grow downward from the
            # top-left, so y has to be flipped against the primary height.
            primary_height = NSScreen.screens()[0].frame().size.height
            return int(location.x), int(primary_height - location.y)
    except Exception:
        logger.debug("Could not read the cursor position")
        return None

    # Linux: X11 needs a display connection and Wayland does not answer at all;
    # neither is reachable without dependencies, so the caller degrades to the
    # primary monitor.
    return None


def screen_index_at(point: tuple[int, int], screens: list[dict]) -> int:
    """The index of the screen containing *point*; the primary when none does."""
    px, py = point
    for i, screen in enumerate(screens):
        sx, sy = int(screen.get("x", 0)), int(screen.get("y", 0))
        if sx <= px < sx + int(screen["width"]) and sy <= py < sy + int(screen["height"]):
            return i
    return 0


def resolve_screen_index(screen: int | str | None, screens: list[dict]) -> int | None:
    """
    Turn the user-facing ``screen`` argument (index, "cursor", or None) into an
    index compute() accepts. "cursor" degrades to the primary monitor where the
    cursor cannot be asked.
    """
    if screen == "cursor":
        point = cursor_position()
        return screen_index_at(point, screens) if point is not None else 0
    return screen
