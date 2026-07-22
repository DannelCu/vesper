"""Tests for semantic window positioning (vesper.core.positioner)."""
from __future__ import annotations

import pytest

from vesper import App
from vesper.core import positioner
from vesper.core.positioner import compute, resolve_screen_index, screen_index_at

PRIMARY = {"width": 1920, "height": 1080, "x": 0, "y": 0}
# A monitor arranged to the left of and above the primary: negative coordinates.
LEFT_ABOVE = {"width": 1280, "height": 1024, "x": -1280, "y": -200}
RIGHT = {"width": 2560, "height": 1440, "x": 1920, "y": 0}

WINDOW = (400, 300)


# ── every corner on the primary ──────────────────────────────────────────────


@pytest.mark.parametrize("position,expected", [
    ("top-left", (0, 0)),
    ("top-center", (760, 0)),
    ("top-right", (1520, 0)),
    ("center-left", (0, 390)),
    ("center", (760, 390)),
    ("center-right", (1520, 390)),
    ("bottom-left", (0, 780)),
    ("bottom-center", (760, 780)),
    ("bottom-right", (1520, 780)),
])
def test_every_position_on_primary(position, expected):
    assert compute(position, WINDOW, [PRIMARY]) == expected


# ── multi-monitor, negative coordinates ──────────────────────────────────────


def test_positions_on_negative_coordinate_monitor():
    screens = [PRIMARY, LEFT_ABOVE]
    assert compute("top-left", WINDOW, screens, screen_index=1) == (-1280, -200)
    assert compute("bottom-right", WINDOW, screens, screen_index=1) == (-1280 + 1280 - 400, -200 + 1024 - 300)


def test_positions_on_secondary_monitor_to_the_right():
    screens = [PRIMARY, RIGHT]
    assert compute("top-right", WINDOW, screens, screen_index=1) == (1920 + 2560 - 400, 0)


def test_offset_is_added_verbatim():
    assert compute("bottom-right", WINDOW, [PRIMARY], offset=(-12, -12)) == (1508, 768)


# ── honest failures ──────────────────────────────────────────────────────────


def test_unknown_position_raises():
    with pytest.raises(ValueError):
        compute("upper-left", WINDOW, [PRIMARY])


def test_no_screens_raises():
    with pytest.raises(ValueError):
        compute("center", WINDOW, [])


def test_out_of_range_screen_raises():
    with pytest.raises(ValueError):
        compute("center", WINDOW, [PRIMARY], screen_index=3)


# ── cursor and screen resolution ─────────────────────────────────────────────


def test_screen_index_at_finds_containing_screen():
    screens = [PRIMARY, LEFT_ABOVE, RIGHT]
    assert screen_index_at((100, 100), screens) == 0
    assert screen_index_at((-640, 300), screens) == 1
    assert screen_index_at((3000, 700), screens) == 2


def test_screen_index_at_falls_back_to_primary():
    assert screen_index_at((99999, 99999), [PRIMARY, RIGHT]) == 0


def test_resolve_cursor_uses_cursor_position(monkeypatch):
    monkeypatch.setattr(positioner, "cursor_position", lambda: (2000, 500))
    assert resolve_screen_index("cursor", [PRIMARY, RIGHT]) == 1


def test_resolve_cursor_degrades_to_primary(monkeypatch):
    # Linux: no dependency-free way to ask, cursor_position returns None.
    monkeypatch.setattr(positioner, "cursor_position", lambda: None)
    assert resolve_screen_index("cursor", [PRIMARY, RIGHT]) == 0


def test_resolve_passes_indices_through():
    assert resolve_screen_index(1, [PRIMARY, RIGHT]) == 1
    assert resolve_screen_index(None, [PRIMARY, RIGHT]) is None


def test_cursor_position_is_none_on_linux(monkeypatch):
    monkeypatch.setattr(positioner.sys, "platform", "linux")
    assert positioner.cursor_position() is None


# ── App wiring ───────────────────────────────────────────────────────────────


def test_position_command_registered():
    assert "vesper:window:position" in App().registry._commands


def test_position_command_moves_the_window(monkeypatch):
    from vesper.core.window import Window

    app = App()
    moved = {}
    monkeypatch.setattr(Window, "get_geometry", lambda self: {"width": 400, "height": 300, "x": 0, "y": 0})
    monkeypatch.setattr(Window, "list_screens", lambda self: [PRIMARY])
    monkeypatch.setattr(Window, "move", lambda self, x, y: moved.update(x=x, y=y))

    resp = app.ipc.handle({
        "id": "1", "command": "vesper:window:position",
        "args": {"position": "top-right"},
    })
    assert resp["ok"] is True
    assert moved == {"x": 1520, "y": 0}
