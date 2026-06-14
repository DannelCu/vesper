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
from vesper.exceptions.errors import (
    VesperError,
    CommandNotFoundError,
    CommandAlreadyRegisteredError,  
)

__version__ = "0.1.0"
__author__ = "Dannel LLC"
__license__ = "MIT"

__all__ = [
    "App",
    "VesperError",
    "CommandNotFoundError",
    "CommandAlreadyRegisteredError",
]
