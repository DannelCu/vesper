"""Tests for taskbar/dock badges and clipboard image support."""
from __future__ import annotations

import base64
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from vesper import App
from vesper.core import badge, clipboard

# A 1x1 PNG — small enough to inline, real enough to round-trip.
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
PNG_DATA_URL = "data:image/png;base64," + base64.b64encode(PNG_BYTES).decode()


@pytest.fixture(autouse=True)
def reset_badge_warnings():
    badge._warned.clear()
    yield
    badge._warned.clear()


# ── clamping ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("value,expected", [
    (0.5, 0.5), (0, 0.0), (1, 1.0),
    (-0.5, 0.0), (1.5, 1.0),          # a caller computing i/total can overshoot
    ("nonsense", 0.0), (None, 0.0),
])
def test_progress_fraction_is_clamped(value, expected):
    assert badge._clamp(value) == expected


# ── Linux ────────────────────────────────────────────────────────────────────


def test_linux_progress_sends_a_launcher_update(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "linux")
    with patch.object(badge, "_linux_launcher_update", return_value=True) as update:
        assert badge.set_progress(0.42) is True

    assert update.call_args[0][0] == {"progress": 0.42, "progress-visible": True}


def test_linux_clear_progress_hides_it(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "linux")
    with patch.object(badge, "_linux_launcher_update", return_value=True) as update:
        badge.clear_progress()

    assert update.call_args[0][0] == {"progress-visible": False}


def test_linux_badge_sets_a_count(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "linux")
    with patch.object(badge, "_linux_launcher_update", return_value=True) as update:
        badge.set_badge(7)

    assert update.call_args[0][0] == {"count": 7, "count-visible": True}


def test_missing_dbus_degrades_to_a_noop(monkeypatch):
    """Most desktops no longer implement LauncherEntry; that must be a no-op."""
    monkeypatch.setattr(badge.sys, "platform", "linux")
    with patch.dict("sys.modules", {"dbus": None}):
        assert badge.set_progress(0.5) is False


# ── macOS ────────────────────────────────────────────────────────────────────


def test_macos_badge_uses_the_dock_tile(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "darwin")
    with patch.object(badge, "_macos_set_badge", return_value=True) as set_badge:
        assert badge.set_badge(3) is True
    set_badge.assert_called_once_with("3")


def test_macos_progress_shows_a_percentage(monkeypatch):
    """There is no dock progress bar, so the percentage goes in the badge."""
    monkeypatch.setattr(badge.sys, "platform", "darwin")
    with patch.object(badge, "_macos_set_badge", return_value=True) as set_badge:
        badge.set_progress(0.42)
    set_badge.assert_called_once_with("42%")


def test_macos_without_pyobjc_degrades(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "darwin")
    with patch.dict("sys.modules", {"AppKit": None}):
        assert badge.set_badge(1) is False


# ── Windows ──────────────────────────────────────────────────────────────────


def test_windows_progress_uses_itaskbarlist3(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "win32")
    taskbar = MagicMock()

    with patch.object(badge, "_windows_taskbar", return_value=taskbar), \
         patch.object(badge, "_windows_hwnd", return_value=1234):
        assert badge.set_progress(0.5) is True

    taskbar.SetProgressValue.assert_called_once_with(1234, 50, 100)


def test_windows_without_comtypes_degrades(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "win32")
    with patch.object(badge, "_windows_taskbar", return_value=None):
        assert badge.set_progress(0.5) is False


# ── Windows badge — the taskbar overlay icon ─────────────────────────────────
#
# Windows exposes no numeric badge, so the count is rendered into an icon and
# applied with ITaskbarList3::SetOverlayIcon. Two halves are tested separately:
# turning a number into a picture (real Pillow, no Windows), and handing a handle
# to the taskbar (mocked comtypes and ctypes, no GUI).


@pytest.fixture
def fake_taskbar(monkeypatch):
    """A mocked ITaskbarList3 bound to a window handle, on a faked win32."""
    monkeypatch.setattr(badge.sys, "platform", "win32")
    monkeypatch.setattr(badge, "_win_overlay_icon", None)
    taskbar = MagicMock()
    monkeypatch.setattr(badge, "_windows_taskbar", lambda: taskbar)
    monkeypatch.setattr(badge, "_windows_hwnd", lambda: 1234)
    return taskbar


def test_windows_badge_sets_an_overlay_icon(fake_taskbar, monkeypatch):
    monkeypatch.setattr(badge, "_windows_badge_hicon", lambda n: 0xBEEF)

    assert badge.set_badge(3) is True

    hwnd, hicon, description = fake_taskbar.SetOverlayIcon.call_args[0]
    assert hwnd == 1234
    assert hicon == 0xBEEF, "the overlay must receive a real icon handle"
    assert "3" in description


def test_windows_clear_badge_passes_a_null_icon(fake_taskbar):
    assert badge.clear_badge() is True

    hwnd, hicon, _ = fake_taskbar.SetOverlayIcon.call_args[0]
    assert hwnd == 1234
    assert hicon is None, "a null icon is how the taskbar is told to remove it"


def test_windows_zero_count_clears_the_overlay(fake_taskbar, monkeypatch):
    monkeypatch.setattr(badge, "_windows_badge_hicon", lambda n: 0xBEEF)

    assert badge.set_badge(0) is True

    assert fake_taskbar.SetOverlayIcon.call_args[0][1] is None


def test_windows_badge_describes_the_real_count_even_when_drawn_as_a_dot(
    fake_taskbar, monkeypatch
):
    """The icon degrades to a dot above 99; the accessible name must not."""
    monkeypatch.setattr(badge, "_windows_badge_hicon", lambda n: 0xBEEF)

    badge.set_badge(1234)

    assert "1234" in fake_taskbar.SetOverlayIcon.call_args[0][2]


def test_windows_badge_degrades_when_the_icon_cannot_be_built(fake_taskbar, monkeypatch):
    monkeypatch.setattr(badge, "_windows_badge_hicon", lambda n: None)

    assert badge.set_badge(3) is False
    fake_taskbar.SetOverlayIcon.assert_not_called()


def test_windows_badge_degrades_without_a_taskbar(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "win32")
    monkeypatch.setattr(badge, "_windows_badge_hicon", lambda n: 0xBEEF)
    monkeypatch.setattr(badge, "_windows_taskbar", lambda: None)

    assert badge.set_badge(3) is False


def test_windows_badge_releases_the_previous_icon(fake_taskbar, monkeypatch):
    """Setting a new badge must not leak the handle the old one used."""
    monkeypatch.setattr(badge, "_windows_badge_hicon", lambda n: 0xBEEF)
    destroyed = []
    fake_user32 = MagicMock()
    fake_user32.DestroyIcon.side_effect = lambda h: destroyed.append(h)
    monkeypatch.setattr(
        badge, "_win_overlay_icon", 0xC0FFEE
    )

    with patch("ctypes.windll", MagicMock(user32=fake_user32), create=True):
        badge.set_badge(3)

    assert destroyed == [0xC0FFEE]
    assert badge._win_overlay_icon == 0xBEEF


def test_windows_badge_has_nothing_to_release_on_the_first_call(fake_taskbar, monkeypatch):
    monkeypatch.setattr(badge, "_windows_badge_hicon", lambda n: 0xBEEF)
    fake_user32 = MagicMock()

    with patch("ctypes.windll", MagicMock(user32=fake_user32), create=True):
        badge.set_badge(3)

    fake_user32.DestroyIcon.assert_not_called()


# ── Windows badge — rendering the number into an image ───────────────────────


@pytest.mark.parametrize("count", [1, 9, 42, 99])
def test_badge_image_is_a_square_rgba_icon(count):
    image = badge._windows_badge_image(count)
    assert image is not None
    assert image.mode == "RGBA"
    assert image.size == (badge._BADGE_PX, badge._BADGE_PX)


def test_badge_image_corners_are_transparent():
    """It is a circle on a taskbar button, so the corners must not be painted."""
    image = badge._windows_badge_image(5)
    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((badge._BADGE_PX - 1, badge._BADGE_PX - 1))[3] == 0


def test_badge_image_centre_is_filled():
    image = badge._windows_badge_image(5)
    assert image.getpixel((badge._BADGE_PX // 2, 2))[3] > 0


def _glyph_pixels(image):
    """
    Count pixels in the text colour.

    Uses load() rather than getdata(): getdata() is deprecated in Pillow 12 and
    its replacement does not exist in the Pillow 9 that pyproject still allows,
    so this is the one accessor that works across the supported range.
    """
    pixels = image.load()
    return sum(
        1
        for x in range(image.width)
        for y in range(image.height)
        if pixels[x, y][:3] == badge._BADGE_FG[:3]
    )


@pytest.mark.parametrize("count", [1, 42])
def test_badge_image_draws_the_number(count):
    """A digit means foreground-coloured pixels the empty dot does not have."""
    assert _glyph_pixels(badge._windows_badge_image(count)) > 0


def test_badge_image_above_the_maximum_is_a_plain_dot():
    image = badge._windows_badge_image(badge._BADGE_MAX + 1)
    assert image is not None
    assert _glyph_pixels(image) == 0


def test_badge_image_without_pillow_degrades(monkeypatch):
    with patch.dict("sys.modules", {"PIL": None}):
        assert badge._windows_badge_image(3) is None
    assert "win-badge-pillow" in badge._warned


def test_badge_hicon_loads_the_rendered_icon(monkeypatch, tmp_path):
    """The .ico must reach LoadImageW with the load-from-file flags."""
    fake_user32 = MagicMock()
    fake_user32.LoadImageW.return_value = 0xABCD

    with patch("ctypes.windll", MagicMock(user32=fake_user32), create=True):
        assert badge._windows_badge_hicon(7) == 0xABCD

    _, path, image_type, _, _, flags = fake_user32.LoadImageW.call_args[0]
    assert path.endswith(".ico")
    assert image_type == badge._IMAGE_ICON
    assert flags & badge._LR_LOADFROMFILE


def test_badge_hicon_is_none_when_windows_refuses(monkeypatch):
    """LoadImageW returns 0 on failure, which must not become a bogus handle."""
    fake_user32 = MagicMock()
    fake_user32.LoadImageW.return_value = 0

    with patch("ctypes.windll", MagicMock(user32=fake_user32), create=True):
        assert badge._windows_badge_hicon(7) is None


def test_badge_hicon_is_none_without_pillow():
    with patch.dict("sys.modules", {"PIL": None}):
        assert badge._windows_badge_hicon(7) is None


def test_badge_ico_carries_both_taskbar_sizes(tmp_path):
    """Windows picks a size by DPI, so the file has to offer more than one."""
    from PIL import Image

    image = badge._windows_badge_image(4)
    path = tmp_path / "badge.ico"
    image.save(path, format="ICO", sizes=badge._BADGE_ICO_SIZES)

    with Image.open(path) as ico:
        assert set(badge._BADGE_ICO_SIZES).issubset(set(ico.info["sizes"]))


# ── shared behaviour ─────────────────────────────────────────────────────────


def test_zero_count_clears_the_badge(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "linux")
    with patch.object(badge, "_linux_launcher_update", return_value=True) as update:
        badge.set_badge(0)

    assert update.call_args[0][0] == {"count-visible": False}


def test_negative_count_is_treated_as_zero(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "linux")
    with patch.object(badge, "_linux_launcher_update", return_value=True) as update:
        badge.set_badge(-5)
    assert update.call_args[0][0] == {"count-visible": False}


def test_a_failing_backend_never_raises(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "linux")
    with patch.object(badge, "_linux_launcher_update", side_effect=RuntimeError("bus down")):
        assert badge.set_progress(0.5) is False
        assert badge.clear_progress() is False
        assert badge.set_badge(2) is False


def test_unavailability_is_logged_once(monkeypatch, caplog):
    """A progress bar updated in a loop must not flood the log."""
    monkeypatch.setattr(badge.sys, "platform", "linux")
    with patch.dict("sys.modules", {"dbus": None}):
        for _ in range(10):
            badge.set_progress(0.5)

    assert len(badge._warned) == 1


# ── clipboard images ─────────────────────────────────────────────────────────


def test_read_image_returns_a_data_url(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    with patch.object(clipboard, "_linux_read_image", return_value=PNG_BYTES):
        result = clipboard.read_image()

    assert result.startswith("data:image/png;base64,")
    assert base64.b64decode(result.split(",", 1)[1]) == PNG_BYTES


def test_read_image_without_an_image_returns_none(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    with patch.object(clipboard, "_linux_read_image", return_value=None):
        assert clipboard.read_image() is None


def test_read_image_survives_a_missing_tool(monkeypatch, caplog):
    """
    A missing helper is a configuration fact, not an error.

    Apps poll the clipboard, so logging a traceback per call would bury the log.
    """
    import logging

    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    with caplog.at_level(logging.DEBUG, logger="vesper.clipboard"), \
         patch.object(clipboard, "_linux_read_image", side_effect=FileNotFoundError("no xclip")):
        assert clipboard.read_image() is None

    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_read_image_reports_a_real_failure(monkeypatch, caplog):
    """An unexpected failure still surfaces, unlike a missing binary."""
    import logging

    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    with caplog.at_level(logging.ERROR, logger="vesper.clipboard"), \
         patch.object(clipboard, "_linux_read_image", side_effect=RuntimeError("bus error")):
        assert clipboard.read_image() is None

    assert any(r.levelno >= logging.ERROR for r in caplog.records)


def test_write_image_accepts_a_data_url(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    with patch.object(clipboard, "_linux_write_image", return_value=True) as writer:
        assert clipboard.write_image(PNG_DATA_URL) is True

    writer.assert_called_once_with(PNG_BYTES)


def test_write_image_accepts_bare_base64(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    with patch.object(clipboard, "_linux_write_image", return_value=True) as writer:
        assert clipboard.write_image(base64.b64encode(PNG_BYTES).decode()) is True

    writer.assert_called_once_with(PNG_BYTES)


@pytest.mark.parametrize("bad", ["", "not base64!!", "data:image/png;base64,@@@"])
def test_write_image_rejects_invalid_data(bad):
    assert clipboard.write_image(bad) is False


def test_round_trip_through_the_data_url_format(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    stored: dict = {}

    with patch.object(clipboard, "_linux_write_image", side_effect=lambda raw: stored.update(raw=raw) or True):
        clipboard.write_image(PNG_DATA_URL)

    with patch.object(clipboard, "_linux_read_image", return_value=stored["raw"]):
        assert clipboard.read_image() == PNG_DATA_URL


def test_linux_image_uses_the_png_mime_type(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    with patch.object(clipboard.subprocess, "run",
                      return_value=subprocess.CompletedProcess([], 0)) as run:
        clipboard._linux_write_image(PNG_BYTES)

    argv = run.call_args[0][0]
    assert argv[:2] == ["xclip", "-selection"]
    assert "image/png" in argv


def test_windows_image_uses_sta_mode(monkeypatch):
    """The Windows clipboard API requires a single-threaded apartment."""
    monkeypatch.setattr(clipboard.sys, "platform", "win32")
    with patch.object(clipboard.subprocess, "run",
                      return_value=subprocess.CompletedProcess([], 0)) as run:
        clipboard._windows_write_image(PNG_BYTES)

    assert "-STA" in run.call_args[0][0]


# ── IPC registration ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("command", [
    "vesper:badge:set_progress",
    "vesper:badge:clear_progress",
    "vesper:badge:set_badge",
    "vesper:badge:clear_badge",
    "vesper:clipboard:read_image",
    "vesper:clipboard:write_image",
])
def test_command_is_registered(command):
    assert command in App().registry._commands


def test_progress_over_ipc(monkeypatch):
    monkeypatch.setattr(badge.sys, "platform", "linux")
    app = App()

    with patch.object(badge, "_linux_launcher_update", return_value=True):
        resp = app.ipc.handle({
            "id": "1", "command": "vesper:badge:set_progress", "args": {"fraction": 0.5},
        })

    assert resp["ok"] is True
    assert resp["result"] is True


# ── clipboard text: degradation when the tool is missing ─────────────────────
#
# read_image() has always returned None for a missing xclip while read()/write() let
# FileNotFoundError escape — an exception crossing the IPC bridge for a machine that
# simply lacks a package. These pin the now-consistent behaviour.


@pytest.fixture
def no_clipboard_tool(monkeypatch):
    """Every clipboard subprocess behaves as if its binary is not installed."""
    def missing(cmd, *args, **kwargs):
        raise FileNotFoundError(cmd[0] if cmd else "?")

    monkeypatch.setattr(clipboard.subprocess, "run", missing)


@pytest.mark.parametrize("platform", ["linux", "darwin", "win32"])
def test_read_returns_empty_when_the_tool_is_missing(
    monkeypatch, no_clipboard_tool, platform
):
    monkeypatch.setattr(clipboard.sys, "platform", platform)
    assert clipboard.read() == ""


@pytest.mark.parametrize("platform", ["linux", "darwin", "win32"])
def test_write_is_a_noop_when_the_tool_is_missing(
    monkeypatch, no_clipboard_tool, platform
):
    monkeypatch.setattr(clipboard.sys, "platform", platform)
    assert clipboard.write("hello") is None


def test_read_matches_read_image_on_a_missing_tool(monkeypatch, no_clipboard_tool):
    """Both halves of the clipboard API degrade; neither raises."""
    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    assert clipboard.read() == ""
    assert clipboard.read_image() is None


def test_missing_tool_logs_at_debug_not_error(monkeypatch, no_clipboard_tool, caplog):
    """An app polling the clipboard must not produce a traceback per poll."""
    import logging

    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    with caplog.at_level(logging.DEBUG, logger="vesper.clipboard"):
        clipboard.read()
        clipboard.write("x")

    assert "not available" in caplog.text
    assert all(r.levelno <= logging.DEBUG for r in caplog.records)


def test_a_real_clipboard_error_is_not_swallowed(monkeypatch):
    """Only a missing binary degrades — a broken tool must still surface."""
    monkeypatch.setattr(clipboard.sys, "platform", "linux")

    def boom(cmd, *args, **kwargs):
        raise OSError("xclip exploded")

    monkeypatch.setattr(clipboard.subprocess, "run", boom)

    with pytest.raises(OSError):
        clipboard.read()
    with pytest.raises(OSError):
        clipboard.write("x")


def test_read_still_returns_clipboard_contents(monkeypatch):
    """The degradation must not have broken the normal path."""
    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    result = MagicMock(stdout="hello world")
    monkeypatch.setattr(clipboard.subprocess, "run", lambda *a, **k: result)

    assert clipboard.read() == "hello world"


def test_write_still_pipes_the_text(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["input"] = kwargs.get("input")
        return MagicMock(returncode=0)

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)
    clipboard.write("hello")

    assert captured["cmd"][0] == "xclip"
    assert captured["input"] == b"hello"
