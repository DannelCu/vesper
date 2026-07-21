"""
Real autostart round-trips on Windows and macOS.

The tests in test_autostart.py mock winreg and redirect Path.home to a tmp_path, so
they prove the code calls the right APIs but not that the registry value or the plist
is one the platform accepts. Both backends are just stdlib — winreg and plistlib — so
a GitHub runner can do the real thing.

Safety, since these touch the user's actual login items:

  * The app name carries the process id, so a run can never collide with a real
    entry, with another test, or with a parallel job.
  * Cleanup is in fixture teardown, so it happens even when the test fails midway.
  * The macOS plist is written but never `launchctl load`ed, so nothing is actually
    registered to launch — the file is what `is_enabled()` reads.

Each test is skipped off its native platform: there is no registry to write on Linux.
"""
from __future__ import annotations

import os
import plistlib
import sys
from pathlib import Path

import pytest

from vesper.core import autostart

windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="writes a real HKCU registry value"
)
macos_only = pytest.mark.skipif(
    sys.platform != "darwin", reason="writes a real LaunchAgents plist"
)


@pytest.fixture
def app_name():
    """A name no real installation could be using."""
    return f"vesper-selftest-{os.getpid()}"


@pytest.fixture
def packaged(monkeypatch):
    """
    Pretend to be a frozen build.

    enable() refuses to register an unpackaged app, since the command would start
    the interpreter rather than the app. The write path under test is the same.
    """
    monkeypatch.setattr(autostart, "is_packaged", lambda: True)
    monkeypatch.setattr(autostart, "_app_command", lambda: sys.executable)


@pytest.fixture
def cleanup_registry(app_name):
    """Remove the value however the test ends."""
    yield
    if sys.platform != "win32":
        return
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, autostart._RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, app_name)
    except FileNotFoundError:
        pass


@pytest.fixture
def cleanup_plist(app_name):
    yield
    if sys.platform != "darwin":
        return
    autostart._macos_path(app_name).unlink(missing_ok=True)


# ── Windows ──────────────────────────────────────────────────────────────────


@windows_only
def test_windows_round_trip(app_name, packaged, cleanup_registry):
    assert autostart.is_enabled(app_name) is False

    assert autostart.enable(app_name) is True
    assert autostart.is_enabled(app_name) is True

    assert autostart.disable(app_name) is True
    assert autostart.is_enabled(app_name) is False


@windows_only
def test_windows_writes_a_readable_run_value(app_name, packaged, cleanup_registry):
    """The value has to be REG_SZ and quoted, or a path with spaces breaks login."""
    import winreg

    autostart.enable(app_name)

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, autostart._RUN_KEY) as key:
        value, value_type = winreg.QueryValueEx(key, app_name)

    assert value_type == winreg.REG_SZ
    assert value == f'"{sys.executable}"'


@windows_only
def test_windows_enable_is_idempotent(app_name, packaged, cleanup_registry):
    assert autostart.enable(app_name) is True
    assert autostart.enable(app_name) is True
    assert autostart.is_enabled(app_name) is True


@windows_only
def test_windows_disable_is_idempotent(app_name, packaged, cleanup_registry):
    """Disabling something never enabled must not raise."""
    assert autostart.disable(app_name) is True
    assert autostart.disable(app_name) is True
    assert autostart.is_enabled(app_name) is False


@windows_only
def test_windows_does_not_disturb_other_entries(app_name, packaged, cleanup_registry):
    """enable()/disable() must touch exactly one value in a shared registry key."""
    import winreg

    def value_names():
        names = []
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, autostart._RUN_KEY) as key:
            index = 0
            while True:
                try:
                    names.append(winreg.EnumValue(key, index)[0])
                except OSError:
                    return set(names)
                index += 1

    before = value_names()
    autostart.enable(app_name)
    assert value_names() - before == {app_name}

    autostart.disable(app_name)
    assert value_names() == before


# ── macOS ────────────────────────────────────────────────────────────────────


@macos_only
def test_macos_round_trip(app_name, packaged, cleanup_plist):
    assert autostart.is_enabled(app_name) is False

    assert autostart.enable(app_name) is True
    assert autostart.is_enabled(app_name) is True

    assert autostart.disable(app_name) is True
    assert autostart.is_enabled(app_name) is False


@macos_only
def test_macos_writes_a_launchd_readable_plist(app_name, packaged, cleanup_plist):
    """launchd rejects a plist missing Label or ProgramArguments."""
    autostart.enable(app_name)

    path = autostart._macos_path(app_name)
    assert path.is_file()

    with path.open("rb") as handle:
        payload = plistlib.load(handle)

    assert payload["Label"] == autostart._macos_label(app_name)
    assert payload["ProgramArguments"] == [sys.executable]
    assert payload["RunAtLoad"] is True


@macos_only
def test_macos_plist_lands_in_the_user_launchagents_dir(
    app_name, packaged, cleanup_plist
):
    autostart.enable(app_name)

    path = autostart._macos_path(app_name)
    assert path.parent == Path.home() / "Library" / "LaunchAgents"
    assert path.suffix == ".plist"


@macos_only
def test_macos_enable_is_idempotent(app_name, packaged, cleanup_plist):
    assert autostart.enable(app_name) is True
    assert autostart.enable(app_name) is True
    assert autostart.is_enabled(app_name) is True


@macos_only
def test_macos_disable_is_idempotent(app_name, packaged, cleanup_plist):
    assert autostart.disable(app_name) is True
    assert autostart.disable(app_name) is True
    assert autostart.is_enabled(app_name) is False


@macos_only
def test_macos_disable_removes_the_file(app_name, packaged, cleanup_plist):
    autostart.enable(app_name)
    path = autostart._macos_path(app_name)
    assert path.exists()

    autostart.disable(app_name)
    assert not path.exists()
