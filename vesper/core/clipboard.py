from __future__ import annotations

import subprocess
import sys


def read() -> str:
    """Read text from the system clipboard."""
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


def write(text: str) -> None:
    """Write text to the system clipboard."""
    if sys.platform == "win32":
        escaped = text.replace("'", "''")
        subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command", f"Set-Clipboard -Value '{escaped}'"],
            capture_output=True, check=False,
        )
    elif sys.platform == "darwin":
        subprocess.run(["pbcopy"], input=text.encode(), capture_output=True, check=False)
    else:
        subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text.encode(), capture_output=True, check=False,
        )
