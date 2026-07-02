from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable

from packaging.version import InvalidVersion, Version


def _parse_version(v: str) -> Version:
    try:
        return Version(v.strip().lstrip("v"))
    except InvalidVersion:
        return Version("0")


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

    platform_entry = manifest.get("platforms", {}).get(_platform_key())
    if not platform_entry:
        return None

    if isinstance(platform_entry, dict):
        download_url = platform_entry.get("url", "")
        sha256 = platform_entry.get("sha256", "")
    else:
        download_url = platform_entry
        sha256 = ""

    if not download_url:
        return None

    return {
        "version": remote_version,
        "notes": manifest.get("notes", ""),
        "download_url": download_url,
        "sha256": sha256,
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


def verify_checksum(path: str, expected_sha256: str) -> bool:
    """Return True if the file at *path* matches *expected_sha256* (hex, case-insensitive)."""
    if not expected_sha256:
        return False
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().lower() == expected_sha256.strip().lower()


def install(path: str, *, expected_sha256: str = "", allow_unverified: bool = False) -> None:
    """
    Replace the running executable with the binary at *path* and restart the app.

    Verifies the SHA-256 checksum before touching the running binary.
    Pass *expected_sha256* from the manifest ``sha256`` field.
    Set *allow_unverified=True* only for local development — never in production.

    On POSIX (macOS / Linux): copies the file in-place and re-execs the process.
    On Windows: launches a detached batch script that swaps the binary after the
    current process exits, then calls sys.exit(0).

    This is only meaningful for packaged apps (sys.executable points to the
    binary). In development (python app.py) sys.executable is the interpreter.
    """
    if not allow_unverified:
        if not expected_sha256:
            raise ValueError(
                "install() requires expected_sha256. "
                "Pass allow_unverified=True only for local development."
            )
        if not verify_checksum(path, expected_sha256):
            raise ValueError("Update binary failed checksum verification; aborting install.")

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
    fd, bat_name = tempfile.mkstemp(suffix=".bat")
    os.close(fd)
    bat = Path(bat_name)
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
