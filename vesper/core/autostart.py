"""
Launch the app when the user logs in.

Windows: a value under ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``
macOS:   a LaunchAgent plist in ``~/Library/LaunchAgents``
Linux:   a ``.desktop`` file in ``~/.config/autostart``

All three are per-user locations, so nothing here needs administrator rights.

Only meaningful for a packaged app. When running from source ``sys.executable`` is
the Python interpreter, and registering that would start the interpreter — not the
app — at login. In that case every call is a no-op that logs a warning, so enabling
autostart during development fails loudly in the log rather than silently writing an
entry that does not work.
"""
from __future__ import annotations

import os
import plistlib
import shlex
import sys
from pathlib import Path

from vesper.core.logging import get_logger

logger = get_logger("autostart")

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

_DEV_WARNING = (
    "Autostart is only meaningful for a packaged app: running from source, the "
    "registered command would start the Python interpreter rather than your app. "
    "Ignoring the request."
)


def is_packaged() -> bool:
    """
    Whether this process is a frozen/packaged executable.

    PyInstaller and Nuitka both set sys.frozen; without it sys.executable is the
    interpreter and autostart cannot reference the app.
    """
    return bool(getattr(sys, "frozen", False))


def _app_command() -> str:
    """The command a login should run."""
    return str(Path(sys.executable).resolve())


def _sanitize(app_name: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_." else "-" for c in app_name).strip("-.")
    return cleaned or "vesper-app"


# ── Linux ────────────────────────────────────────────────────────────────────


def _linux_path(app_name: str) -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "autostart" / f"{_sanitize(app_name)}.desktop"


def _linux_enable(app_name: str) -> bool:
    path = _linux_path(app_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exec must be a single command line; quote it so a path with spaces survives.
    path.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={app_name}\n"
        f"Exec={shlex.quote(_app_command())}\n"
        "X-GNOME-Autostart-enabled=true\n"
        "Terminal=false\n",
        encoding="utf-8",
    )
    return True


# ── macOS ────────────────────────────────────────────────────────────────────


def _macos_label(app_name: str) -> str:
    return f"com.vesper.{_sanitize(app_name).lower()}"


def _macos_path(app_name: str) -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{_macos_label(app_name)}.plist"


def _macos_enable(app_name: str) -> bool:
    path = _macos_path(app_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "Label": _macos_label(app_name),
        "ProgramArguments": [_app_command()],
        "RunAtLoad": True,
    }
    with path.open("wb") as handle:
        plistlib.dump(payload, handle)
    return True


# ── Windows ──────────────────────────────────────────────────────────────────


def _windows_enable(app_name: str) -> bool:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        # Quoted so a path containing spaces is treated as one argument.
        winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{_app_command()}"')
    return True


def _windows_disable(app_name: str) -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, app_name)
    except FileNotFoundError:
        return True  # already absent
    return True


def _windows_is_enabled(app_name: str) -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, app_name)
            return True
    except FileNotFoundError:
        return False


# ── public API ───────────────────────────────────────────────────────────────


def enable(app_name: str) -> bool:
    """
    Register the app to start at login.

    Returns True on success, False when unsupported or when running from source.
    Never raises: autostart is a convenience, not something worth crashing over.
    """
    if not is_packaged():
        logger.warning(_DEV_WARNING)
        return False

    try:
        if sys.platform == "win32":
            return _windows_enable(app_name)
        if sys.platform == "darwin":
            return _macos_enable(app_name)
        return _linux_enable(app_name)
    except Exception:
        logger.exception("Could not enable autostart for %r", app_name)
        return False


def disable(app_name: str) -> bool:
    """
    Remove the login registration. Returns True when it is gone afterwards.

    Unlike enable(), this works when running from source too, so a stale entry left
    by a packaged build can always be cleared.
    """
    try:
        if sys.platform == "win32":
            return _windows_disable(app_name)

        path = _macos_path(app_name) if sys.platform == "darwin" else _linux_path(app_name)
        path.unlink(missing_ok=True)
        return True
    except Exception:
        logger.exception("Could not disable autostart for %r", app_name)
        return False


def is_enabled(app_name: str) -> bool:
    """Whether a login registration currently exists."""
    try:
        if sys.platform == "win32":
            return _windows_is_enabled(app_name)

        path = _macos_path(app_name) if sys.platform == "darwin" else _linux_path(app_name)
        return path.is_file()
    except Exception:
        logger.exception("Could not read autostart state for %r", app_name)
        return False
