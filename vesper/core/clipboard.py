from __future__ import annotations

import base64
import subprocess
import sys

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
