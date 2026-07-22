from __future__ import annotations

import base64
import struct
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from vesper.core.fs_scope import FsScope
from vesper.core.logging import get_logger

logger = get_logger("clipboard")


def read() -> str:
    """
    Read text from the system clipboard.

    Returns "" when the clipboard is empty *or* when the platform tool is missing.
    The caller cannot act on the difference, and an exception crossing the IPC
    bridge for a machine without xclip is exactly the kind of surprise this API
    should not produce. Whether the backend exists is answered by
    ``vesper.capabilities()`` and by ``vesper doctor``, where it is actionable.
    """
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["powershell", "-WindowStyle", "Hidden", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, check=False,
            )
            return result.stdout.rstrip("\r\n")
        elif sys.platform == "darwin":
            result = subprocess.run(["pbpaste"], capture_output=True, text=True, check=False)
            return result.stdout
        else:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, text=True, check=False,
            )
            return result.stdout
    except FileNotFoundError:
        # Same contract as read_image(): a configuration fact, logged at debug so an
        # app polling the clipboard does not produce a traceback per poll.
        logger.debug("Clipboard tool not available")
        return ""


def write(text: str) -> None:
    """
    Write text to the system clipboard.

    A no-op when the platform tool is missing, matching read(). Returns nothing —
    callers that need to know whether the clipboard is usable should ask
    ``vesper.capabilities()`` rather than infer it from a failure here.
    """
    try:
        _write(text)
    except FileNotFoundError:
        logger.debug("Clipboard tool not available")


def _write(text: str) -> None:
    if sys.platform == "win32":
        # Pipe via stdin to avoid any injection through string interpolation.
        subprocess.run(
            [
                "powershell", "-WindowStyle", "Hidden", "-NoProfile", "-Command",
                "[Console]::InputEncoding=[System.Text.Encoding]::UTF8;"
                "$s=[Console]::In.ReadToEnd();"
                "Set-Clipboard -Value $s",
            ],
            input=text.encode("utf-8"),
            capture_output=True, check=False,
        )
    elif sys.platform == "darwin":
        subprocess.run(["pbcopy"], input=text.encode(), capture_output=True, check=False)
    else:
        subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text.encode(), capture_output=True, check=False,
        )


# ── images ───────────────────────────────────────────────────────────────────
#
# Images cross the IPC bridge as base64 PNG data URLs, since the bridge is JSON and
# cannot carry raw bytes. That is also directly usable as an <img src>.


_PNG_MIME = "image/png"
_DATA_URL_PREFIX = f"data:{_PNG_MIME};base64,"


def read_image() -> str | None:
    """
    Read an image from the clipboard as a PNG data URL.

    Returns None when the clipboard holds no image, or when the platform tool is
    unavailable — the caller cannot act on the difference, and an app polling the
    clipboard should not have to catch an exception for the ordinary empty case.
    """
    try:
        if sys.platform == "darwin":
            data = _macos_read_image()
        elif sys.platform == "win32":
            data = _windows_read_image()
        else:
            data = _linux_read_image()
    except FileNotFoundError:
        # The helper binary is not installed. That is a configuration fact, not a
        # failure, and apps poll the clipboard — an ERROR traceback per poll would
        # bury the log.
        logger.debug("Clipboard image tool not available")
        return None
    except Exception:
        logger.exception("Could not read image from clipboard")
        return None

    if not data:
        return None

    return _DATA_URL_PREFIX + base64.b64encode(data).decode("ascii")


def write_image(data_url: str) -> bool:
    """
    Put a PNG on the clipboard.

    Args:
        data_url: A ``data:image/png;base64,...`` URL, or bare base64 PNG data.

    Returns:
        True when the platform accepted it.
    """
    payload = data_url or ""
    if payload.startswith("data:"):
        _, _, payload = payload.partition(",")

    try:
        raw = base64.b64decode(payload, validate=True)
    except Exception:
        logger.debug("write_image called with data that is not valid base64")
        return False

    if not raw:
        return False

    try:
        if sys.platform == "darwin":
            return _macos_write_image(raw)
        if sys.platform == "win32":
            return _windows_write_image(raw)
        return _linux_write_image(raw)
    except Exception:
        logger.exception("Could not write image to clipboard")
        return False


def _linux_read_image() -> bytes | None:
    result = subprocess.run(
        ["xclip", "-selection", "clipboard", "-t", _PNG_MIME, "-o"],
        capture_output=True, check=False,
    )
    return result.stdout if result.returncode == 0 and result.stdout else None


def _linux_write_image(raw: bytes) -> bool:
    result = subprocess.run(
        ["xclip", "-selection", "clipboard", "-t", _PNG_MIME],
        input=raw, capture_output=True, check=False,
    )
    return result.returncode == 0


def _macos_read_image() -> bytes | None:
    # osascript writes the PNG to a temp file; the clipboard cannot be piped as
    # binary through pbpaste.
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "clipboard.png"
        script = (
            'set png to (the clipboard as «class PNGf»)\n'
            f'set f to open for access POSIX file "{path}" with write permission\n'
            "write png to f\n"
            "close access f"
        )
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, check=False
        )
        if result.returncode != 0 or not path.exists():
            return None
        return path.read_bytes()


def _macos_write_image(raw: bytes) -> bool:
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "clipboard.png"
        path.write_bytes(raw)
        script = f'set the clipboard to (read POSIX file "{path}" as «class PNGf»)'
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, check=False
        )
        return result.returncode == 0


def _windows_read_image() -> bytes | None:
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "clipboard.png"
        script = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$img=[System.Windows.Forms.Clipboard]::GetImage();"
            "if ($img -eq $null) { exit 1 };"
            f"$img.Save({_ps_quote(str(path))}, "
            "[System.Drawing.Imaging.ImageFormat]::Png)"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-STA", "-Command", script],
            capture_output=True, check=False,
        )
        if result.returncode != 0 or not path.exists():
            return None
        return path.read_bytes()


def _windows_write_image(raw: bytes) -> bool:
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "clipboard.png"
        path.write_bytes(raw)
        script = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            f"$img=[System.Drawing.Image]::FromFile({_ps_quote(str(path))});"
            "[System.Windows.Forms.Clipboard]::SetImage($img);"
            "$img.Dispose()"
        )
        # -STA is required: the Windows clipboard API is single-threaded apartment.
        result = subprocess.run(
            ["powershell", "-NoProfile", "-STA", "-Command", script],
            capture_output=True, check=False,
        )
        return result.returncode == 0


def _ps_quote(value: str) -> str:
    """Quote a string for a PowerShell single-quoted literal."""
    return "'" + value.replace("'", "''") + "'"


# ── files ────────────────────────────────────────────────────────────────────
#
# The OS clipboard's *file object* — what Explorer/Finder/file managers put there
# on Copy and read back on Paste. Distinct from copying a path as text: pasting
# these into a file manager copies the files themselves.


def write_files(paths: list[str]) -> bool:
    """
    Put files on the clipboard as the OS file object.

    After this, Paste in Explorer/Finder/the file manager copies the files.
    Returns True when the platform accepted them; False (with a debug log) when
    the platform tool is missing, matching the text clipboard's contract.
    """
    resolved = [str(Path(p).expanduser().resolve()) for p in paths]
    if not resolved:
        return False

    try:
        if sys.platform == "win32":
            return _windows_write_files(resolved)
        if sys.platform == "darwin":
            return _macos_write_files(resolved)
        return _linux_write_files(resolved)
    except FileNotFoundError:
        logger.debug("Clipboard tool not available")
        return False
    except Exception:
        logger.exception("Could not write files to clipboard")
        return False


def read_files(*, scope: FsScope | None = None) -> list[str]:
    """
    File paths currently on the clipboard, e.g. after Copy in the file manager.

    With a scope configured, paths outside it are silently dropped (logged at
    debug): the clipboard's content is the *user's* doing, not the frontend's,
    so an out-of-scope entry is filtered rather than punished with an error.

    Returns [] when the clipboard holds no files or the platform tool is
    missing. On macOS at most one path is returned — the scripting interface
    only exposes the first file object; see docs/clipboard.md.
    """
    try:
        if sys.platform == "win32":
            paths = _windows_read_files()
        elif sys.platform == "darwin":
            paths = _macos_read_files()
        else:
            paths = _linux_read_files()
    except FileNotFoundError:
        logger.debug("Clipboard tool not available")
        return []
    except Exception:
        logger.exception("Could not read files from clipboard")
        return []

    if scope is None:
        return paths

    allowed = []
    for p in paths:
        try:
            scope.check(p)
            allowed.append(p)
        except Exception:
            logger.debug("Dropping clipboard path outside fs scope: %s", p)
    return allowed


_CF_HDROP = 15


def _hdrop_payload(paths: list[str]) -> bytes:
    """
    The CF_HDROP clipboard payload: a DROPFILES header followed by a
    double-NUL-terminated list of wide paths.

    Pure so it can be tested for real off Windows. Header layout (20 bytes):
    DWORD pFiles (offset of the list), POINT pt, BOOL fNC, BOOL fWide.
    """
    file_list = "\0".join(paths) + "\0\0"
    header = struct.pack("<IiiII", 20, 0, 0, 0, 1)  # pFiles=20, pt=(0,0), fNC=0, fWide=1
    return header + file_list.encode("utf-16-le")


def _windows_write_files(paths: list[str]) -> bool:
    import ctypes

    payload = _hdrop_payload(paths)

    GMEM_MOVEABLE = 0x0002
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(payload))
    if not handle:
        return False
    locked = kernel32.GlobalLock(handle)
    ctypes.memmove(locked, payload, len(payload))
    kernel32.GlobalUnlock(handle)

    if not user32.OpenClipboard(None):
        kernel32.GlobalFree(handle)
        return False
    try:
        user32.EmptyClipboard()
        # On success the clipboard owns the memory; only free it on failure.
        if not user32.SetClipboardData(_CF_HDROP, handle):
            kernel32.GlobalFree(handle)
            return False
        return True
    finally:
        user32.CloseClipboard()


def _windows_read_files() -> list[str]:
    import ctypes

    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32

    if not user32.OpenClipboard(None):
        return []
    try:
        hdrop = user32.GetClipboardData(_CF_HDROP)
        if not hdrop:
            return []
        count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
        paths = []
        for i in range(count):
            length = shell32.DragQueryFileW(hdrop, i, None, 0)
            buffer = ctypes.create_unicode_buffer(length + 1)
            shell32.DragQueryFileW(hdrop, i, buffer, length + 1)
            paths.append(buffer.value)
        return paths
    finally:
        user32.CloseClipboard()


def _osa_quote(value: str) -> str:
    """Escape a string for an AppleScript double-quoted literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _macos_write_files(paths: list[str]) -> bool:
    items = ", ".join(f'POSIX file "{_osa_quote(p)}"' for p in paths)
    script = f"set the clipboard to {{{items}}}" if len(paths) > 1 else (
        f'set the clipboard to POSIX file "{_osa_quote(paths[0])}"'
    )
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, check=False
    )
    return result.returncode == 0


def _macos_read_files() -> list[str]:
    # The scripting interface coerces the clipboard to a single furl — there is
    # no way to enumerate every file object through osascript, so multi-file
    # reads return only the first. Documented in docs/clipboard.md.
    result = subprocess.run(
        ["osascript", "-e", "POSIX path of (the clipboard as «class furl»)"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return []
    path = result.stdout.strip()
    return [path.rstrip("/") or "/"] if path else []


def _linux_write_files(paths: list[str]) -> bool:
    uris = "\n".join(Path(p).as_uri() for p in paths) + "\n"
    result = subprocess.run(
        ["xclip", "-selection", "clipboard", "-t", "text/uri-list"],
        input=uris.encode(), capture_output=True, check=False,
    )
    return result.returncode == 0


def _linux_read_files() -> list[str]:
    result = subprocess.run(
        ["xclip", "-selection", "clipboard", "-t", "text/uri-list", "-o"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return []

    paths = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("file://"):
            parsed = urllib.parse.urlparse(line)
            paths.append(urllib.request.url2pathname(parsed.path))
    return paths
