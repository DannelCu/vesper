"""
Vesper - Python-first desktop framework inspired by Tauri.

Vesper allows you to build modern desktop applications using:
    - Python for backend logic
    - Web technologies (HTML/CSS/JS) for UI
    - Native system WebViews for rendering

Example:
    >>> from vesper import App
    >>> 
    >>> app = App()
    >>> 
    >>> @app.command
    ... def greet(name: str) -> str:
    ...     return f"Hello {name}!"
    ... 
    >>> app.run()

For more information, see: https://github.com/DannelCu/vesper
"""

from vesper.core.app import App
from vesper.core.guard import guard
from vesper.core.menu import MenuItem
from vesper.core.module import Module, Controller, Injectable, command
from vesper.core.plugin import VesperPlugin
from vesper.core.process import ShellScope, ShellScopeError
from vesper.core.tray import TrayMenuItem
from vesper.core.window import WindowHandle
from vesper.exceptions.errors import (
    VesperError,
    CommandNotFoundError,
    CommandAlreadyRegisteredError,
    ForbiddenError,
)

try:
    from importlib.metadata import version as _v
    __version__ = _v("vesper")
except Exception:
    __version__ = "0.1.0"

__author__ = "DannelCu"
__license__ = "MIT"

__all__ = [
    "App",
    "Module",
    "Controller",
    "Injectable",
    "command",
    "guard",
    "MenuItem",
    "VesperPlugin",
    "ShellScope",
    "ShellScopeError",
    "TrayMenuItem",
    "WindowHandle",
    "VesperError",
    "CommandNotFoundError",
    "CommandAlreadyRegisteredError",
    "ForbiddenError",
]
