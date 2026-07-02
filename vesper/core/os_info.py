from __future__ import annotations

import platform
import sys


def get_info() -> dict:
    """Return OS platform, version, machine architecture, and Python version."""
    return {
        "platform": sys.platform,
        "version": platform.version(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
    }
