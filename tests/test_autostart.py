"""Tests for autostart, native message dialogs, fs.trash and power management."""
from __future__ import annotations

import plistlib
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from vesper import App
from vesper.core import autostart, fs, power


@pytest.fixture
def packaged(monkeypatch):
    """Pretend to be a frozen build; autostart is a no-op otherwise."""
    monkeypatch.setattr(autostart, "is_packaged", lambda: True)
    monkeypatch.setattr(autostart, "_app_command", lambda: "/opt/MyApp/MyApp")


@pytest.fixture
def linux_home(monkeypatch, tmp_path):
    monkeypatch.setattr(autostart.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


# ── development guard ────────────────────────────────────────────────────────


def test_enable_is_a_noop_when_not_packaged(monkeypatch, linux_home, caplog):
    """From source sys.executable is the interpreter — registering it is useless."""
    monkeypatch.setattr(autostart, "is_packaged", lambda: False)

    assert autostart.enable("MyApp") is False
    assert not (linux_home / "autostart" / "MyApp.desktop").exists()


def test_disable_works_even_when_not_packaged(monkeypatch, linux_home, packaged):
    """A stale entry from a packaged build must always be removable."""
    autostart.enable("MyApp")
    monkeypatch.setattr(autostart, "is_packaged", lambda: False)

    assert autostart.disable("MyApp") is True
    assert autostart.is_enabled("MyApp") is False


# ── Linux ────────────────────────────────────────────────────────────────────


def test_linux_enable_writes_a_desktop_file(linux_home, packaged):
    assert autostart.enable("MyApp") is True

    path = linux_home / "autostart" / "MyApp.desktop"
    content = path.read_text()
    assert "[Desktop Entry]" in content
    assert "Type=Application" in content
    assert "Name=MyApp" in content
    assert "/opt/MyApp/MyApp" in content


def test_linux_round_trip(linux_home, packaged):
    assert autostart.is_enabled("MyApp") is False
    autostart.enable("MyApp")
    assert autostart.is_enabled("MyApp") is True
    autostart.disable("MyApp")
    assert autostart.is_enabled("MyApp") is False


def test_linux_disable_is_idempotent(linux_home, packaged):
    assert autostart.disable("NeverEnabled") is True


def test_linux_quotes_a_path_with_spaces(linux_home, monkeypatch):
    monkeypatch.setattr(autostart, "is_packaged", lambda: True)
    monkeypatch.setattr(autostart, "_app_command", lambda: "/opt/My App/My App")

    autostart.enable("MyApp")
    exec_line = [
        line for line in (linux_home / "autostart" / "MyApp.desktop").read_text().splitlines()
        if line.startswith("Exec=")
    ][0]
    # Unquoted, the launcher would try to run "/opt/My" with "App/My App" as args.
    assert exec_line == "Exec='/opt/My App/My App'"


def test_app_name_cannot_escape_the_autostart_directory(linux_home, packaged):
    autostart.enable("../../evil")
    written = list((linux_home / "autostart").glob("*.desktop"))
    assert len(written) == 1
    assert written[0].parent == linux_home / "autostart"


# ── macOS ────────────────────────────────────────────────────────────────────


def test_macos_enable_writes_a_launch_agent(monkeypatch, tmp_path, packaged):
    monkeypatch.setattr(autostart.sys, "platform", "darwin")
    monkeypatch.setattr(autostart.Path, "home", staticmethod(lambda: tmp_path))

    assert autostart.enable("MyApp") is True

    path = tmp_path / "Library" / "LaunchAgents" / "com.vesper.myapp.plist"
    with path.open("rb") as handle:
        payload = plistlib.load(handle)

    assert payload["Label"] == "com.vesper.myapp"
    assert payload["ProgramArguments"] == ["/opt/MyApp/MyApp"]
    assert payload["RunAtLoad"] is True


def test_macos_round_trip(monkeypatch, tmp_path, packaged):
    monkeypatch.setattr(autostart.sys, "platform", "darwin")
    monkeypatch.setattr(autostart.Path, "home", staticmethod(lambda: tmp_path))

    autostart.enable("MyApp")
    assert autostart.is_enabled("MyApp") is True
    autostart.disable("MyApp")
    assert autostart.is_enabled("MyApp") is False


# ── Windows ──────────────────────────────────────────────────────────────────


def test_windows_enable_writes_the_run_key(monkeypatch, packaged):
    monkeypatch.setattr(autostart.sys, "platform", "win32")

    winreg = MagicMock()
    with patch.dict("sys.modules", {"winreg": winreg}):
        assert autostart.enable("MyApp") is True

    args = winreg.SetValueEx.call_args[0]
    assert args[0:2][1] == "MyApp"
    # Quoted so a Program Files path is not split on its spaces.
    assert args[4] == '"/opt/MyApp/MyApp"'


def test_windows_disable_tolerates_a_missing_value(monkeypatch, packaged):
    monkeypatch.setattr(autostart.sys, "platform", "win32")

    winreg = MagicMock()
    winreg.DeleteValue.side_effect = FileNotFoundError
    with patch.dict("sys.modules", {"winreg": winreg}):
        assert autostart.disable("MyApp") is True


# ── failures degrade ─────────────────────────────────────────────────────────


def test_enable_failure_returns_false(linux_home, packaged):
    with patch("vesper.core.autostart._linux_enable", side_effect=OSError("read-only")):
        assert autostart.enable("MyApp") is False


def test_is_enabled_failure_returns_false(linux_home, packaged):
    with patch("vesper.core.autostart._linux_path", side_effect=RuntimeError("boom")):
        assert autostart.is_enabled("MyApp") is False


# ── IPC registration ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("command", [
    "vesper:autostart:enable",
    "vesper:autostart:disable",
    "vesper:autostart:is_enabled",
    "vesper:dialog:message",
    "vesper:dialog:confirm",
    "vesper:dialog:ask",
    "vesper:fs:trash",
    "vesper:power:prevent_sleep",
    "vesper:power:allow_sleep",
])
def test_command_is_registered(command):
    assert command in App().registry._commands


# ── native message dialogs ───────────────────────────────────────────────────


def test_confirm_returns_the_user_answer():
    app = App()
    app.window.window = MagicMock()
    app.window.window.create_confirmation_dialog.return_value = True

    resp = app.ipc.handle({
        "id": "1", "command": "vesper:dialog:confirm",
        "args": {"title": "Quit", "message": "Are you sure?"},
    })
    assert resp["ok"] is True
    assert resp["result"] is True


def test_confirm_returns_false_when_cancelled():
    app = App()
    app.window.window = MagicMock()
    app.window.window.create_confirmation_dialog.return_value = False

    resp = app.ipc.handle({
        "id": "1", "command": "vesper:dialog:confirm", "args": {"message": "?"},
    })
    assert resp["result"] is False


def test_ask_uses_the_same_dialog_as_confirm():
    app = App()
    app.window.window = MagicMock()
    app.window.window.create_confirmation_dialog.return_value = True

    resp = app.ipc.handle({
        "id": "1", "command": "vesper:dialog:ask", "args": {"message": "Continue?"},
    })
    assert resp["result"] is True


def test_message_dialog_discards_the_answer():
    app = App()
    app.window.window = MagicMock()
    app.window.window.create_confirmation_dialog.return_value = False

    resp = app.ipc.handle({
        "id": "1", "command": "vesper:dialog:message", "args": {"message": "Done"},
    })
    assert resp["ok"] is True
    assert resp["result"] is None


def test_dialog_before_window_creation_is_an_error():
    app = App()
    resp = app.ipc.handle({
        "id": "1", "command": "vesper:dialog:confirm", "args": {"message": "?"},
    })
    assert resp["ok"] is False


# ── fs.trash ─────────────────────────────────────────────────────────────────


def test_trash_uses_send2trash_when_available(tmp_path):
    target = tmp_path / "file.txt"
    target.write_text("x")

    sender = MagicMock()
    with patch.dict("sys.modules", {"send2trash": MagicMock(send2trash=sender)}):
        assert fs.trash(str(target)) is True

    sender.assert_called_once_with(str(target.resolve()))


def test_trash_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        fs.trash(str(tmp_path / "nope.txt"))


def test_trash_respects_the_fs_scope(tmp_path):
    from vesper.core.fs_scope import FsScope

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")

    scope = FsScope([str(allowed)])
    sender = MagicMock()

    with patch.dict("sys.modules", {"send2trash": MagicMock(send2trash=sender)}):
        with pytest.raises(Exception):
            fs.trash(str(outside), scope=scope)

    sender.assert_not_called()


def test_trash_never_falls_back_to_deleting(tmp_path, monkeypatch):
    """A failed trash must leave the file alone, not delete it permanently."""
    target = tmp_path / "file.txt"
    target.write_text("precious")

    monkeypatch.setattr(fs.sys, "platform", "linux")

    with patch.dict("sys.modules", {"send2trash": None}), \
         patch.object(fs.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)):
        with pytest.raises(RuntimeError, match="No trash backend"):
            fs.trash(str(target))

    assert target.exists(), "the file must survive a failed trash"


def test_trash_linux_uses_gio(tmp_path, monkeypatch):
    target = tmp_path / "file.txt"
    target.write_text("x")
    monkeypatch.setattr(fs.sys, "platform", "linux")

    with patch.dict("sys.modules", {"send2trash": None}), \
         patch.object(fs.subprocess, "run",
                      return_value=subprocess.CompletedProcess([], 0)) as run:
        assert fs.trash(str(target)) is True

    argv = run.call_args[0][0]
    assert argv[:3] == ["gio", "trash", "--"]
    # "--" so a filename starting with "-" is not read as an option.
    assert argv[3] == str(target.resolve())


def test_trash_macos_uses_finder(tmp_path, monkeypatch):
    target = tmp_path / "file.txt"
    target.write_text("x")
    monkeypatch.setattr(fs.sys, "platform", "darwin")

    with patch.dict("sys.modules", {"send2trash": None}), \
         patch.object(fs.subprocess, "run",
                      return_value=subprocess.CompletedProcess([], 0)) as run:
        assert fs.trash(str(target)) is True

    argv = run.call_args[0][0]
    assert argv[0] == "osascript"
    assert "Finder" in argv[2]


def test_trash_windows_uses_the_recycle_bin(tmp_path, monkeypatch):
    target = tmp_path / "file.txt"
    target.write_text("x")
    monkeypatch.setattr(fs.sys, "platform", "win32")

    with patch.dict("sys.modules", {"send2trash": None}), \
         patch.object(fs.subprocess, "run",
                      return_value=subprocess.CompletedProcess([], 0)) as run:
        assert fs.trash(str(target)) is True

    script = run.call_args[0][0][-1]
    assert "SendToRecycleBin" in script


def test_trash_windows_quotes_an_apostrophe_in_the_path(tmp_path, monkeypatch):
    """The path is interpolated into a PowerShell literal, so quoting matters."""
    target = tmp_path / "it's here.txt"
    target.write_text("x")
    monkeypatch.setattr(fs.sys, "platform", "win32")

    with patch.dict("sys.modules", {"send2trash": None}), \
         patch.object(fs.subprocess, "run",
                      return_value=subprocess.CompletedProcess([], 0)) as run:
        fs.trash(str(target))

    script = run.call_args[0][0][-1]
    assert "it''s here.txt" in script


# ── power ────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_power():
    yield
    power._active = False
    power._process = None


def test_prevent_sleep_on_linux_uses_systemd_inhibit(monkeypatch):
    monkeypatch.setattr(power.sys, "platform", "linux")
    monkeypatch.setattr(power.shutil, "which", lambda name: "/usr/bin/" + name)

    with patch.object(power.subprocess, "Popen") as popen:
        assert power.prevent_sleep("exporting") is True

    argv = popen.call_args[0][0]
    assert argv[0] == "systemd-inhibit"
    assert "--why=exporting" in argv
    assert power.is_preventing_sleep() is True


def test_prevent_sleep_on_macos_uses_caffeinate(monkeypatch):
    monkeypatch.setattr(power.sys, "platform", "darwin")
    monkeypatch.setattr(power.shutil, "which", lambda name: "/usr/bin/caffeinate")

    with patch.object(power.subprocess, "Popen") as popen:
        assert power.prevent_sleep() is True

    assert popen.call_args[0][0][0] == "caffeinate"


def test_prevent_sleep_is_idempotent(monkeypatch):
    monkeypatch.setattr(power.sys, "platform", "linux")
    monkeypatch.setattr(power.shutil, "which", lambda name: "/usr/bin/" + name)

    with patch.object(power.subprocess, "Popen") as popen:
        power.prevent_sleep()
        power.prevent_sleep()

    assert popen.call_count == 1, "a second request must not stack another inhibitor"


def test_allow_sleep_terminates_the_helper(monkeypatch):
    monkeypatch.setattr(power.sys, "platform", "linux")
    monkeypatch.setattr(power.shutil, "which", lambda name: "/usr/bin/" + name)

    proc = MagicMock()
    with patch.object(power.subprocess, "Popen", return_value=proc):
        power.prevent_sleep()

    assert power.allow_sleep() is True
    proc.terminate.assert_called_once()
    assert power.is_preventing_sleep() is False


def test_allow_sleep_without_a_request_is_fine():
    assert power.allow_sleep() is True


def test_prevent_sleep_degrades_when_no_backend(monkeypatch):
    """No helper binary must mean "unavailable", not a crash."""
    monkeypatch.setattr(power.sys, "platform", "linux")
    monkeypatch.setattr(power.shutil, "which", lambda name: None)

    assert power.prevent_sleep() is False
    assert power.is_preventing_sleep() is False


def test_prevent_sleep_survives_a_failing_backend(monkeypatch):
    monkeypatch.setattr(power.sys, "platform", "linux")
    monkeypatch.setattr(power.shutil, "which", lambda name: "/usr/bin/" + name)

    with patch.object(power.subprocess, "Popen", side_effect=OSError("no exec")):
        assert power.prevent_sleep() is False
