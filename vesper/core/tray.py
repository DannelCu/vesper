from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger("vesper.tray")


@dataclass
class TrayMenuItem:
    """A clickable item in the system tray context menu."""
    label: str
    action: Callable[[], None]


def _run_action(action: Callable[[], None]) -> None:
    try:
        action()
    except Exception:
        # The thread is ours, so an exception here would otherwise vanish into
        # a stderr traceback with no hint that a tray click caused it.
        logger.exception("Tray menu action raised")


def _handler(action: Callable[[], None]) -> Callable[[], None]:
    """
    Wrap a zero-argument app callback for pystray's menu-item protocol.

    Two traps, both of which have bitten:

    **Argument count.** pystray inspects the callback's ``__code__.co_argcount``
    and treats 0 as "call with nothing", 1 as "call with the icon", 2 as "call
    with (icon, item)" and anything more as an error. *Parameters with defaults
    are counted*, so the obvious ``lambda _, a=action: a()`` reads as taking one
    argument but counts as two: pystray passed ``(icon, menu_item)``, the
    MenuItem landed in ``a``, and every tray click raised "MenuItem.__call__()
    missing 1 required positional argument: 'icon'". Capturing the action in a
    closure keeps the count at zero and binds each item to its own callback
    rather than to the loop variable.

    **Which thread the action runs on.** pystray does not have one answer:
    the win32 backend pumps its own message loop on a thread it owns, while the
    AppIndicator and GTK backends attach to whatever GLib main loop is already
    running — which, under Vesper, is PyWebView's, on the main thread. Anything
    the action does that waits on that loop then deadlocks it permanently:
    ``app.emit()`` is ``evaluate_js``, which schedules the script with
    ``glib.idle_add`` and blocks on a semaphore until it completes, and the idle
    callback cannot run while the loop is blocked waiting for it. One tray click
    froze the whole GUI — window unresponsive, no further tray action, not even
    Quit.

    Running the action on a short-lived thread gives every backend the same
    contract, the one the tray docs already state: **tray actions run on a
    background thread**. It also keeps a slow action (an HTTP call, a
    subprocess) from stalling the UI, and window methods stay safe to call
    because the backends marshal those onto the GUI thread themselves.
    """
    def run() -> None:
        threading.Thread(
            target=_run_action,
            args=(action,),
            name="vesper-tray-action",
            daemon=True,
        ).start()

    return run


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
                items.append(pystray.MenuItem(item.label, _handler(item.action)))

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
