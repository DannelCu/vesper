"""
Window geometry persistence.

Saves the main window's size and position on close and restores them on the next
run. Opt-in via ``App(remember_window=True)``.

The awkward part is not storing the numbers, it is deciding whether they are still
usable. A window saved on a second monitor that is no longer attached would be
restored off-screen, where it is invisible and cannot be dragged back — so a stored
position is only honoured when it still lands on a screen that currently exists.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vesper.core.logging import get_logger
from vesper.core.paths import config_dir, ensure_dir

logger = get_logger("window_state")

STATE_FILENAME = "window-state.json"

# A window counts as on-screen when at least this much of its title bar area is
# visible. Requiring the whole window to fit would reject a window the user had
# deliberately placed half off the edge.
_MIN_VISIBLE_PX = 80


def state_path(app_name: str) -> Path:
    return config_dir(app_name) / STATE_FILENAME


def save(app_name: str, geometry: dict[str, int]) -> bool:
    """
    Persist window geometry. Returns True when it was written.

    Never raises: failing to save a window position must not stop an app closing.
    """
    try:
        payload = {key: int(geometry[key]) for key in ("width", "height", "x", "y")}
    except (KeyError, TypeError, ValueError):
        logger.debug("Refusing to save malformed geometry: %r", geometry)
        return False

    if payload["width"] <= 0 or payload["height"] <= 0:
        logger.debug("Refusing to save non-positive window size: %r", payload)
        return False

    try:
        path = state_path(app_name)
        ensure_dir(path.parent)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return True
    except OSError:
        logger.exception("Could not save window state")
        return False


def load(app_name: str) -> dict[str, int] | None:
    """Read stored geometry, or None when absent or unusable."""
    try:
        raw = state_path(app_name).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.debug("Ignoring corrupt window state file")
        return None

    if not isinstance(data, dict):
        return None

    result: dict[str, int] = {}
    for key in ("width", "height", "x", "y"):
        value = data.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            return None
        result[key] = value

    if result["width"] <= 0 or result["height"] <= 0:
        return None

    return result


def is_on_screen(geometry: dict[str, int], screens: list[dict[str, Any]]) -> bool:
    """
    Whether the geometry overlaps any currently connected screen.

    With no screen information available, the answer is yes: refusing to restore
    would be worse than restoring onto a layout we could not verify.
    """
    if not screens:
        return True

    x, y = geometry["x"], geometry["y"]
    width, height = geometry["width"], geometry["height"]

    for screen in screens:
        try:
            sx = int(screen.get("x", 0))
            sy = int(screen.get("y", 0))
            sw = int(screen["width"])
            sh = int(screen["height"])
        except (KeyError, TypeError, ValueError):
            continue

        overlap_w = min(x + width, sx + sw) - max(x, sx)
        overlap_h = min(y + height, sy + sh) - max(y, sy)

        if overlap_w >= _MIN_VISIBLE_PX and overlap_h >= _MIN_VISIBLE_PX:
            return True

    return False


def restorable(app_name: str, screens: list[dict[str, Any]]) -> dict[str, int] | None:
    """
    Stored geometry that is safe to apply, or None.

    When the position is no longer on any screen the size is still returned, with the
    position dropped — the caller then keeps its default centring, which is nicer
    than discarding the user's preferred window size along with it.
    """
    geometry = load(app_name)
    if geometry is None:
        return None

    if is_on_screen(geometry, screens):
        return geometry

    logger.debug(
        "Stored window position %r is off-screen; keeping size only",
        (geometry["x"], geometry["y"]),
    )
    return {"width": geometry["width"], "height": geometry["height"]}
