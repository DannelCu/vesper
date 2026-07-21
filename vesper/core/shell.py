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

    # Always hand the helper an absolute path. A relative one starting with "-" would
    # otherwise be parsed as an option ("-R", "--version", ...) by the target binary,
    # letting frontend-supplied input change the command instead of naming a file.
    # Absolute paths cannot be mistaken for options on any of the three platforms.
    #
    # Note this is deliberately not solved with a "--" separator: xdg-open rejects any
    # argument beginning with "-" outright, including "--" itself, so adding one would
    # break reveal() on Linux rather than harden it.
    target = os.path.abspath(path)

    if sys.platform == "win32":
        subprocess.run(["explorer", "/select,", target], check=False)
    elif sys.platform == "darwin":
        subprocess.run(["open", "-R", target], check=False)
    else:
        if not os.path.isdir(target):
            target = os.path.dirname(target)
        subprocess.run(["xdg-open", target], check=False)
