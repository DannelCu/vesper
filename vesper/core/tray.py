from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class TrayMenuItem:
    """A clickable item in the system tray context menu."""
    label: str
    action: Callable[[], None]


class Tray:
    """
    System tray icon with a context menu.

    Requires pystray and Pillow. Install with: pip install vesper[tray]
    """

    def __init__(
        self,
        icon: str,
        menu: list[TrayMenuItem | None],
        *,
        title: str = "",
    ) -> None:
        self._icon_path = icon
        self._menu = menu
        self._title = title
        self._icon = None

    def start(self) -> None:
        """Start the tray icon in a background thread."""
        try:
            import pystray
            from PIL import Image
        except ImportError:
            raise RuntimeError(
                "System tray requires pystray and Pillow. "
                "Install them with: pip install vesper[tray]"
            )

        image = Image.open(self._icon_path)

        items = []
        for item in self._menu:
            if item is None:
                items.append(pystray.Menu.SEPARATOR)
            else:
                action = item.action
                items.append(pystray.MenuItem(item.label, lambda _, a=action: a()))

        self._icon = pystray.Icon(
            name=self._title or "vesper",
            icon=image,
            title=self._title,
            menu=pystray.Menu(*items),
        )
        self._icon.run_detached()

    def stop(self) -> None:
        """Stop the tray icon."""
        if self._icon is not None:
            self._icon.stop()
            self._icon = None
