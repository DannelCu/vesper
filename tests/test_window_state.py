"""Tests for window geometry persistence and per-user paths."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from vesper import App
from vesper.core import paths, window_state


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """
    Keep tests off the real user config directory.

    Only window_state's imported reference is redirected — patching paths.config_dir
    itself would also stub it out for the tests that exercise the real path rules.
    """
    monkeypatch.setattr(window_state, "config_dir", lambda app_name=".": tmp_path / app_name)
    return tmp_path


SCREEN_1080P = [{"x": 0, "y": 0, "width": 1920, "height": 1080}]


# ── save / load round trip ───────────────────────────────────────────────────


def test_save_then_load_round_trip():
    geometry = {"width": 1024, "height": 768, "x": 100, "y": 50}
    assert window_state.save("app", geometry) is True
    assert window_state.load("app") == geometry


def test_load_without_a_saved_file_returns_none():
    assert window_state.load("never-saved") is None


def test_save_rejects_missing_keys():
    assert window_state.save("app", {"width": 100}) is False
    assert window_state.load("app") is None


def test_save_rejects_non_positive_size():
    assert window_state.save("app", {"width": 0, "height": 10, "x": 0, "y": 0}) is False


def test_save_accepts_negative_position():
    """A monitor left of or above the primary one has negative coordinates."""
    geometry = {"width": 800, "height": 600, "x": -1920, "y": -100}
    assert window_state.save("app", geometry) is True
    assert window_state.load("app") == geometry


def test_load_ignores_a_corrupt_file(isolated_config):
    path = window_state.state_path("app")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json")
    assert window_state.load("app") is None


@pytest.mark.parametrize("payload", [
    '{"width": "wide", "height": 600, "x": 0, "y": 0}',
    '{"width": true, "height": 600, "x": 0, "y": 0}',
    '[1, 2, 3]',
    '{"width": 800}',
])
def test_load_rejects_wrong_types(isolated_config, payload):
    path = window_state.state_path("app")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload)
    assert window_state.load("app") is None


def test_save_failure_is_reported_not_raised():
    with patch("vesper.core.window_state.ensure_dir", side_effect=OSError("read-only")):
        assert window_state.save("app", {"width": 1, "height": 1, "x": 0, "y": 0}) is False


# ── on-screen detection ──────────────────────────────────────────────────────


def test_window_fully_inside_a_screen_is_on_screen():
    geometry = {"width": 800, "height": 600, "x": 100, "y": 100}
    assert window_state.is_on_screen(geometry, SCREEN_1080P) is True


def test_window_on_a_disconnected_monitor_is_off_screen():
    """The case that matters: a second monitor that is no longer attached."""
    geometry = {"width": 800, "height": 600, "x": 2500, "y": 100}
    assert window_state.is_on_screen(geometry, SCREEN_1080P) is False


def test_window_far_above_the_screen_is_off_screen():
    geometry = {"width": 800, "height": 600, "x": 0, "y": -5000}
    assert window_state.is_on_screen(geometry, SCREEN_1080P) is False


def test_window_partly_off_the_edge_is_still_on_screen():
    """A deliberately half-off window must not be relocated."""
    geometry = {"width": 800, "height": 600, "x": 1600, "y": 100}
    assert window_state.is_on_screen(geometry, SCREEN_1080P) is True


def test_window_barely_overlapping_is_off_screen():
    """A few visible pixels are not enough to grab the window back."""
    geometry = {"width": 800, "height": 600, "x": 1919, "y": 100}
    assert window_state.is_on_screen(geometry, SCREEN_1080P) is False


def test_second_monitor_position_is_accepted_when_present():
    screens = SCREEN_1080P + [{"x": 1920, "y": 0, "width": 1920, "height": 1080}]
    geometry = {"width": 800, "height": 600, "x": 2500, "y": 100}
    assert window_state.is_on_screen(geometry, screens) is True


def test_no_screen_information_allows_restore():
    """Unverifiable is not the same as invalid."""
    geometry = {"width": 800, "height": 600, "x": 5000, "y": 5000}
    assert window_state.is_on_screen(geometry, []) is True


def test_malformed_screen_entries_are_skipped():
    screens = [{"nonsense": True}, {"x": 0, "y": 0, "width": 1920, "height": 1080}]
    geometry = {"width": 800, "height": 600, "x": 10, "y": 10}
    assert window_state.is_on_screen(geometry, screens) is True


# ── restorable() ─────────────────────────────────────────────────────────────


def test_restorable_returns_full_geometry_when_on_screen():
    window_state.save("app", {"width": 1024, "height": 768, "x": 50, "y": 50})
    assert window_state.restorable("app", SCREEN_1080P) == {
        "width": 1024, "height": 768, "x": 50, "y": 50,
    }


def test_restorable_drops_position_when_off_screen():
    """Size is still the user's preference even when the position is unusable."""
    window_state.save("app", {"width": 1024, "height": 768, "x": 9000, "y": 9000})
    assert window_state.restorable("app", SCREEN_1080P) == {"width": 1024, "height": 768}


def test_restorable_without_saved_state_is_none():
    assert window_state.restorable("app", SCREEN_1080P) is None


# ── App integration ──────────────────────────────────────────────────────────


def test_remember_window_defaults_to_off():
    assert App()._remember_window is False


def test_restore_applies_saved_geometry():
    window_state.save("Vesper App", {"width": 1111, "height": 999, "x": 12, "y": 34})

    app = App(remember_window=True)
    with patch.object(app.window, "list_screens", return_value=SCREEN_1080P):
        app._restore_window_state()

    assert (app.config.width, app.config.height) == (1111, 999)
    assert (app.config.x, app.config.y) == (12, 34)


def test_restore_keeps_size_but_not_position_when_off_screen():
    window_state.save("Vesper App", {"width": 1111, "height": 999, "x": 9000, "y": 9000})

    app = App(remember_window=True)
    with patch.object(app.window, "list_screens", return_value=SCREEN_1080P):
        app._restore_window_state()

    assert (app.config.width, app.config.height) == (1111, 999)
    # Left as the default so the backend still centres the window.
    assert app.config.x is None and app.config.y is None


def test_restore_survives_a_backend_with_no_screen_list():
    """list_screens() raises before the GUI backend is up; that must not break run()."""
    window_state.save("Vesper App", {"width": 640, "height": 480, "x": 5, "y": 5})

    app = App(remember_window=True)
    with patch.object(app.window, "list_screens", side_effect=RuntimeError("no gui yet")):
        app._restore_window_state()

    assert (app.config.width, app.config.height) == (640, 480)


def test_save_window_state_writes_current_geometry():
    app = App(remember_window=True)
    geometry = {"width": 900, "height": 700, "x": 20, "y": 30}

    with patch.object(app.window, "get_geometry", return_value=geometry):
        app._save_window_state()

    assert window_state.load("Vesper App") == geometry


def test_save_window_state_ignores_a_destroyed_window():
    app = App(remember_window=True)
    with patch.object(app.window, "get_geometry", return_value=None):
        app._save_window_state()
    assert window_state.load("Vesper App") is None


def test_run_saves_geometry_on_exit():
    app = App(remember_window=True)
    geometry = {"width": 1234, "height": 567, "x": 8, "y": 9}

    with patch.object(app.window, "create"), patch.object(app.window, "show"), \
         patch.object(app.window, "get_geometry", return_value=geometry):
        app.run()

    assert window_state.load("Vesper App") == geometry


def test_run_does_not_save_when_disabled():
    app = App(remember_window=False)
    with patch.object(app.window, "create"), patch.object(app.window, "show"), \
         patch.object(app.window, "get_geometry", return_value={"width": 1, "height": 1, "x": 0, "y": 0}):
        app.run()

    assert window_state.load("Vesper App") is None


# ── Window.get_geometry ──────────────────────────────────────────────────────


def test_get_geometry_reads_the_backend_window():
    from vesper.core.window import Window

    w = Window()
    w.window = MagicMock(width=800, height=600, x=10, y=20)
    assert w.get_geometry() == {"width": 800, "height": 600, "x": 10, "y": 20}


def test_get_geometry_before_create_is_none():
    from vesper.core.window import Window

    assert Window().get_geometry() is None


def test_get_geometry_handles_a_backend_without_coordinates():
    from vesper.core.window import Window

    w = Window()
    w.window = MagicMock(width=800, height=600)
    del w.window.x
    assert w.get_geometry() is None


# ── paths ────────────────────────────────────────────────────────────────────


def test_config_dir_is_per_platform(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert paths.config_dir("myapp") == tmp_path / "myapp"


def test_app_name_cannot_escape_the_config_directory(monkeypatch, tmp_path):
    """App names come from user config, so traversal must not be possible."""
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    resolved = paths.config_dir("../../etc/evil").resolve()
    assert tmp_path.resolve() in resolved.parents


def test_empty_app_name_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert paths.config_dir("...").name == "app"


def test_ensure_dir_is_user_private(tmp_path):
    import os
    import sys as _sys

    target = paths.ensure_dir(tmp_path / "private")
    assert target.is_dir()

    if _sys.platform != "win32":
        assert os.stat(target).st_mode & 0o777 == 0o700
