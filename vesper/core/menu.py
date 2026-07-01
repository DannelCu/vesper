from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class MenuItem:
    """
    A native menu bar item.

    Pass ``submenu`` to create a top-level menu with child items.
    Pass ``action`` to create a clickable leaf item.
    Insert ``None`` in a submenu list to add a separator.

    Example::

        app.menu([
            MenuItem("File", submenu=[
                MenuItem("Open", action=open_file),
                None,
                MenuItem("Quit", action=app.quit),
            ]),
        ])
    """

    label: str
    action: Callable | None = None
    submenu: list | None = None
