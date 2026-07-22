"""
Tests for vesper.core.capabilities — the single source of truth for which optional
backends exist on this machine.

Every test fakes the platform and the probes, so the result never depends on what
happens to be installed on the machine running the suite.
"""
from __future__ import annotations

import pytest

from vesper.core import capabilities

ALL_CAPABILITIES = {
    "clipboard_text",
    "clipboard_image",
    "clipboard_files",
    "notifications",
    "trash",
    "keep_awake",
    "tray",
    "badge",
    "mica",
    "nsis",
    "power_events",
    "global_shortcuts",
}

# Capabilities that are platform facts rather than missing installs: when absent
# there is honestly nothing to run, so they carry no fix line.
UNFIXABLE = {"badge", "mica"}


@pytest.fixture
def env(monkeypatch):
    """
    Control the whole detection surface: platform, PATH binaries and importability.

    Returns a setter so each test states exactly the machine it is describing.
    """

    class Env:
        def __init__(self) -> None:
            self.binaries: set[str] = set()
            self.modules: set[str] = set()

        def set(self, platform: str, *, binaries=(), modules=()) -> None:
            self.binaries = set(binaries)
            self.modules = set(modules)
            monkeypatch.setattr(capabilities.sys, "platform", platform)
            monkeypatch.setattr(
                capabilities, "_has_binary", lambda name: name in self.binaries
            )
            monkeypatch.setattr(
                capabilities, "_has_module", lambda name: name in self.modules
            )

    return Env()


# ── shape of the result ──────────────────────────────────────────────────────


def test_probe_reports_exactly_the_documented_capabilities(env):
    env.set("linux")
    assert set(capabilities.probe()) == ALL_CAPABILITIES


def test_every_entry_has_the_three_keys(env):
    env.set("linux")
    for name, entry in capabilities.probe().items():
        assert set(entry) == {"available", "detail", "fix"}, name
        assert isinstance(entry["available"], bool), name
        assert isinstance(entry["detail"], str) and entry["detail"], name


def test_an_available_capability_carries_no_fix(env):
    """A fix on a working capability would tell the user to run something pointless."""
    env.set("win32", modules={"comtypes", "pystray", "PIL", "pynput", "send2trash"})
    for name, entry in capabilities.probe().items():
        if entry["available"]:
            assert entry["fix"] is None, name


def test_a_missing_capability_carries_a_fix_or_is_unfixable(env):
    env.set("linux")
    for name, entry in capabilities.probe().items():
        if entry["available"]:
            continue
        # Platform facts (badge on Linux, mica off Windows 11) are the honest
        # "nothing you can install" cases.
        if name in UNFIXABLE:
            assert entry["fix"] is None
        else:
            assert entry["fix"], name


def test_probe_has_no_side_effects_and_is_repeatable(env):
    env.set("linux", binaries={"xclip"})
    assert capabilities.probe() == capabilities.probe()


def test_probe_does_not_import_the_backends(env, monkeypatch):
    """
    Detection must stay to find_spec, never a real import.

    A probe that imported pystray or comtypes would pay their import cost — and on
    Windows, comtypes generates code on first import — every time doctor runs.
    """
    import builtins

    real_import = builtins.__import__
    forbidden = {"pystray", "PIL", "comtypes", "AppKit", "pynput", "send2trash"}

    def guard(name, *args, **kwargs):
        assert name.split(".")[0] not in forbidden, f"probe imported {name}"
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guard)
    env.set("linux")
    capabilities.probe()


# ── clipboard ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("key", ["clipboard_text", "clipboard_image"])
@pytest.mark.parametrize("platform", ["win32", "darwin"])
def test_clipboard_is_always_available_off_linux(env, key, platform):
    """Windows and macOS ship their clipboard tools; probing PATH would be theatre."""
    env.set(platform)
    assert capabilities.probe()[key]["available"] is True


@pytest.mark.parametrize("key", ["clipboard_text", "clipboard_image"])
def test_clipboard_on_linux_needs_xclip(env, key):
    env.set("linux", binaries={"xclip"})
    assert capabilities.probe()[key]["available"] is True

    env.set("linux")
    entry = capabilities.probe()[key]
    assert entry["available"] is False
    assert "xclip" in entry["fix"]


# ── notifications ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("platform", ["win32", "darwin"])
def test_notifications_always_available_off_linux(env, platform):
    env.set(platform)
    assert capabilities.probe()["notifications"]["available"] is True


def test_notifications_on_linux_need_notify_send(env):
    env.set("linux", binaries={"notify-send"})
    assert capabilities.probe()["notifications"]["available"] is True

    env.set("linux")
    entry = capabilities.probe()["notifications"]
    assert entry["available"] is False
    assert "libnotify" in entry["fix"]


# ── trash ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("platform", ["win32", "darwin", "linux"])
def test_trash_prefers_send2trash_everywhere(env, platform):
    env.set(platform, modules={"send2trash"})
    entry = capabilities.probe()["trash"]
    assert entry["available"] is True
    assert entry["detail"] == "send2trash"


@pytest.mark.parametrize("platform", ["win32", "darwin"])
def test_trash_falls_back_to_the_shell_off_linux(env, platform):
    """Both have a native recycle bin reachable without any Python package."""
    env.set(platform)
    assert capabilities.probe()["trash"]["available"] is True


def test_trash_on_linux_accepts_gio(env):
    env.set("linux", binaries={"gio"})
    entry = capabilities.probe()["trash"]
    assert entry["available"] is True
    assert "gio" in entry["detail"]


def test_trash_on_linux_without_send2trash_or_gio(env):
    env.set("linux")
    entry = capabilities.probe()["trash"]
    assert entry["available"] is False
    assert "vesper[trash]" in entry["fix"]


# ── keep awake ───────────────────────────────────────────────────────────────


def test_keep_awake_on_windows_needs_nothing(env):
    env.set("win32")
    assert capabilities.probe()["keep_awake"]["available"] is True


def test_keep_awake_on_macos_needs_caffeinate(env):
    env.set("darwin", binaries={"caffeinate"})
    assert capabilities.probe()["keep_awake"]["available"] is True

    env.set("darwin")
    assert capabilities.probe()["keep_awake"]["available"] is False


def test_keep_awake_on_linux_prefers_systemd_inhibit(env):
    env.set("linux", binaries={"systemd-inhibit", "xdg-screensaver"})
    entry = capabilities.probe()["keep_awake"]
    assert entry["available"] is True
    assert "systemd-inhibit" in entry["detail"]


def test_keep_awake_on_linux_accepts_the_weaker_fallback(env):
    """xdg-screensaver is what prevent_sleep() would use, so it counts — but says so."""
    env.set("linux", binaries={"xdg-screensaver"})
    entry = capabilities.probe()["keep_awake"]
    assert entry["available"] is True
    assert "not a sleep inhibitor" in entry["detail"]


def test_keep_awake_on_linux_with_neither(env):
    env.set("linux")
    entry = capabilities.probe()["keep_awake"]
    assert entry["available"] is False
    assert entry["fix"]


# ── tray ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("platform", ["win32", "darwin", "linux"])
def test_tray_needs_both_packages(env, platform):
    env.set(platform, modules={"pystray", "PIL"})
    assert capabilities.probe()["tray"]["available"] is True


@pytest.mark.parametrize("present, missing", [("pystray", "PIL"), ("PIL", "pystray")])
def test_tray_reports_which_package_is_missing(env, present, missing):
    env.set("linux", modules={present})
    entry = capabilities.probe()["tray"]
    assert entry["available"] is False
    assert missing in entry["detail"]
    assert "vesper[tray]" in entry["fix"]


def test_tray_with_neither_package_names_both(env):
    env.set("linux")
    entry = capabilities.probe()["tray"]
    assert "pystray" in entry["detail"] and "PIL" in entry["detail"]


# ── badge ────────────────────────────────────────────────────────────────────


def test_badge_on_macos_needs_appkit(env):
    env.set("darwin", modules={"AppKit"})
    assert capabilities.probe()["badge"]["available"] is True

    env.set("darwin")
    entry = capabilities.probe()["badge"]
    assert entry["available"] is False
    assert "pyobjc" in entry["fix"]


def test_badge_on_windows_needs_comtypes(env):
    env.set("win32", modules={"comtypes"})
    assert capabilities.probe()["badge"]["available"] is True

    env.set("win32")
    entry = capabilities.probe()["badge"]
    assert entry["available"] is False
    assert "comtypes" in entry["fix"]


def test_badge_on_linux_is_reported_unavailable(env):
    """
    Plain GNOME does not implement Unity LauncherEntry, and there is nothing to
    install that would change it — so there is no fix to offer.
    """
    env.set("linux", modules={"dbus"}, binaries={"gio"})
    entry = capabilities.probe()["badge"]
    assert entry["available"] is False
    assert entry["fix"] is None


# ── global shortcuts ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("platform", ["win32", "darwin", "linux"])
def test_global_shortcuts_follow_pynput(env, platform):
    env.set(platform, modules={"pynput"})
    assert capabilities.probe()["global_shortcuts"]["available"] is True

    env.set(platform)
    entry = capabilities.probe()["global_shortcuts"]
    assert entry["available"] is False
    assert "vesper-shortcuts" in entry["fix"]


# ── helpers on top of probe() ────────────────────────────────────────────────


def test_is_available_matches_probe(env):
    env.set("linux", binaries={"xclip"}, modules={"pynput"})
    report = capabilities.probe()
    for name, entry in report.items():
        assert capabilities.is_available(name) is entry["available"], name


def test_is_available_is_false_for_an_unknown_capability(env):
    env.set("linux")
    assert capabilities.is_available("teleportation") is False


def test_available_map_is_booleans_only(env):
    env.set("linux", binaries={"xclip"})
    result = capabilities.available_map()
    assert set(result) == ALL_CAPABILITIES
    assert all(isinstance(v, bool) for v in result.values())


def test_available_map_hides_the_fix_strings(env):
    """Install instructions are for whoever runs the app, not for the web UI."""
    env.set("linux")
    for value in capabilities.available_map().values():
        assert isinstance(value, bool)


# ── the low-level detectors ──────────────────────────────────────────────────


def test_has_module_finds_the_stdlib():
    assert capabilities._has_module("json") is True


def test_has_module_is_false_for_a_missing_module():
    assert capabilities._has_module("definitely_not_a_real_module_xyz") is False


def test_has_module_survives_a_broken_parent_package(monkeypatch):
    """find_spec raises rather than returning None for some broken installs."""
    def boom(name):
        raise ValueError("broken parent package")

    monkeypatch.setattr(capabilities.importlib.util, "find_spec", boom)
    assert capabilities._has_module("anything") is False


def test_has_binary_uses_which(monkeypatch):
    monkeypatch.setattr(
        capabilities.shutil, "which", lambda n: "/usr/bin/x" if n == "x" else None
    )
    assert capabilities._has_binary("x") is True
    assert capabilities._has_binary("y") is False


# ── power events ─────────────────────────────────────────────────────────────


def test_power_events_on_windows_need_nothing(env):
    """The message window is plain ctypes against what ships with the OS."""
    env.set("win32")
    assert capabilities.probe()["power_events"]["available"] is True


def test_power_events_on_macos_need_pyobjc(env):
    env.set("darwin", modules={"AppKit"})
    assert capabilities.probe()["power_events"]["available"] is True

    env.set("darwin")
    entry = capabilities.probe()["power_events"]
    assert entry["available"] is False
    assert "pyobjc" in entry["fix"]


def test_power_events_on_linux_need_jeepney(env):
    env.set("linux", modules={"jeepney"})
    entry = capabilities.probe()["power_events"]
    assert entry["available"] is True
    assert "D-Bus" in entry["detail"]

    env.set("linux")
    entry = capabilities.probe()["power_events"]
    assert entry["available"] is False
    assert "jeepney" in entry["fix"]


def test_power_events_are_independent_of_keep_awake(env):
    """Different backends entirely: systemd-inhibit is a binary, jeepney a module."""
    env.set("linux", binaries={"systemd-inhibit"})
    report = capabilities.probe()
    assert report["keep_awake"]["available"] is True
    assert report["power_events"]["available"] is False
