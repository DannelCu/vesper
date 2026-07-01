from __future__ import annotations

import os
import subprocess
import sys
import webbrowser


def open_url(url: str) -> None:
    """Open a URL in the default system browser."""
    webbrowser.open(url)


def reveal(path: str) -> None:
    """Reveal a file or folder in the native file manager."""
    if sys.platform == "win32":
        subprocess.run(["explorer", "/select,", path], check=False)
    elif sys.platform == "darwin":
        subprocess.run(["open", "-R", path], check=False)
    else:
        target = path if os.path.isdir(path) else os.path.dirname(os.path.abspath(path))
        subprocess.run(["xdg-open", target], check=False)
