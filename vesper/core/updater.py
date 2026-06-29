from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable


def _parse_version(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except ValueError:
        return (0,)


def _platform_key() -> str:
    system = platform.system().lower()
    return {"windows": "win32", "darwin": "darwin", "linux": "linux"}.get(system, system)


def check(manifest_url: str, current_version: str) -> dict | None:
    """
    Fetch the manifest at manifest_url and return update info if a newer
    version is available for the current platform.

    Returns None if already up to date, if the current platform is not
    listed in the manifest, or on any network / parse error.

    Manifest format:
        {
            "version": "1.2.0",
            "notes": "Bug fixes",
            "platforms": {
                "win32": "https://example.com/releases/myapp-1.2.0.exe",
                "darwin": "https://example.com/releases/myapp-1.2.0",
                "linux": "https://example.com/releases/myapp-1.2.0"
            }
        }
    """
    import json

    if not manifest_url or not current_version:
        return None

    try:
        with urllib.request.urlopen(manifest_url, timeout=10) as resp:
            manifest = json.loads(resp.read().decode())
    except Exception:
        return None

    remote_version = manifest.get("version", "")
    if not remote_version:
        return None

    if _parse_version(remote_version) <= _parse_version(current_version):
        return None

    download_url = manifest.get("platforms", {}).get(_platform_key())
    if not download_url:
        return None

    return {
        "version": remote_version,
        "notes": manifest.get("notes", ""),
        "download_url": download_url,
    }


def download(url: str, on_progress: Callable[[int], None] | None = None) -> str:
    """
    Download the file at url to a temporary location.

    Calls on_progress(percent) with integer values 0–100 during the transfer.
    Returns the local path to the downloaded file.
    """
    suffix = Path(url.split("?")[0]).suffix or ""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.close()

    def _reporthook(block_num: int, block_size: int, total_size: int) -> None:
        if total_size > 0:
            percent = min(100, int(block_num * block_size * 100 / total_size))
            on_progress(percent)

    urllib.request.urlretrieve(
        url, tmp.name, reporthook=_reporthook if on_progress else None
    )
    return tmp.name


def install(path: str) -> None:
    """
    Replace the running executable with the binary at path and restart the app.

    On POSIX (macOS / Linux): copies the file in-place and re-execs the process.
    On Windows: launches a detached batch script that swaps the binary after the
    current process exits, then calls sys.exit(0).

    This is only meaningful for packaged apps (sys.executable points to the
    binary). In development (python app.py) sys.executable is the interpreter.
    """
    current = Path(sys.executable)
    new = Path(path)

    if platform.system() == "Windows":
        _install_windows(current, new)
    else:
        _install_posix(current, new)


def _install_posix(current: Path, new: Path) -> None:
    shutil.copy2(new, current)
    os.chmod(current, 0o755)
    os.execv(str(current), sys.argv)


def _install_windows(current: Path, new: Path) -> None:
    bat = Path(tempfile.mktemp(suffix=".bat"))
    bat.write_text(
        "@echo off\n"
        ":wait\n"
        "timeout /t 1 /nobreak >nul\n"
        f'move /y "{new}" "{current}" >nul 2>&1\n'
        "if errorlevel 1 goto wait\n"
        f'start "" "{current}"\n'
        'del "%~f0"\n',
        encoding="utf-8",
    )
    subprocess.Popen(
        ["cmd.exe", "/c", str(bat)],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    sys.exit(0)
