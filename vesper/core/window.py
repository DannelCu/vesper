import json
import os
from collections.abc import Callable
from pathlib import Path

import webview

from vesper.core.config import WindowConfig
from vesper.core.ipc import IPC

# Maps Vesper hook names → PyWebView window.events attribute names
_HOOK_TO_EVENT: dict[str, str] = {
    "close":    "closed",
    "minimize": "minimized",
    "restore":  "restored",
    "focus":    "focused",
    "blur":     "blurred",
    "loaded":   "loaded",
}


class WindowHandle:
    """
    Handle for a secondary window returned by ``app.register_window()``.

    The underlying PyWebView window is created when ``app.run()`` is called.
    Calling ``show()`` / ``hide()`` / ``close()`` before that is a no-op.
    """

    def __init__(self, config: "WindowConfig") -> None:
        self._config = config
        self._win = None

    def _attach(self, win) -> None:
        self._win = win

    def show(self) -> None:
        """Make the window visible."""
        if self._win is not None:
            self._win.show()

    def hide(self) -> None:
        """Hide the window without destroying it."""
        if self._win is not None:
            self._win.hide()

    def close(self) -> None:
        """Destroy the window."""
        if self._win is not None:
            self._win.destroy()

    def emit(self, event: str, payload=None) -> None:
        """Dispatch a named event to this window's frontend."""
        if self._win is None:
            return
        data = json.dumps(payload)
        js = f'window.dispatchEvent(new CustomEvent("vesper:{event}",{{detail:{data}}}))'
        self._win.evaluate_js(js)


def _to_file_types(filters: list[dict] | None) -> tuple:
    """Convert Vesper filter dicts to the tuple of strings PyWebView expects.

    Input:  [{"name": "Images", "extensions": ["png", "jpg"]}, ...]
    Output: ("Images (*.png;*.jpg)", ...)
    """
    if not filters:
        return ()
    result = []
    for f in filters:
        name = f.get("name", "Files")
        exts = f.get("extensions") or ["*"]
        parts = ";".join(f"*.*" if e == "*" else f"*.{e}" for e in exts)
        result.append(f"{name} ({parts})")
    return tuple(result)


def _to_webview_menu(items: list) -> list:
    """Convert a Vesper menu list to the format PyWebView expects."""
    from vesper.core.menu import MenuItem
    result = []
    for item in items:
        if item is None:
            result.append(webview.MenuSeparator())
        elif isinstance(item, MenuItem) and item.submenu is not None:
            result.append(webview.Menu(item.label, _to_webview_menu(item.submenu)))
        else:
            action = item.action if item.action is not None else (lambda: None)
            result.append(webview.MenuAction(item.label, action))
    return result


class Window:
    """
    Window layer for Vesper.

    Responsible for:
    - Creating the native desktop window
    - Connecting JavaScript (frontend) with Python IPC
    - Starting the application UI loop

    This class uses PyWebView as the underlying rendering engine.
    """

    def __init__(self) -> None:
        self.window = None
        self.ipc: IPC | None = None
        self._menu: list | None = None
        self._splash_win = None

    def create(
        self,
        ipc_handler: IPC,
        config: WindowConfig,
        hooks: dict[str, list[Callable]] | None = None,
        secondary_windows: list[WindowHandle] | None = None,
        menu: list | None = None,
        splash: dict | None = None,
    ) -> None:
        """
        Create the application window and bind IPC.

        Args:
            ipc_handler:
                Instance of the IPC system responsible for
                handling frontend messages.
            config:
                Window configuration.
            hooks:
                Lifecycle handlers keyed by Vesper event name
                (close, minimize, restore, focus, blur, loaded).
            secondary_windows:
                Pre-declared secondary windows created hidden.
                Each is attached to the IPC and shown on demand.
            menu:
                Native menu bar items (converted from Vesper MenuItem list).
            splash:
                Splash screen config dict with keys: html, width, height.
        """

        self._menu = menu
        self._splash_win = None

        dev_url = os.environ.get("VESPER_DEV_URL")

        if dev_url:
            frontend = dev_url
        else:
            frontend_path = Path(config.frontend)
            if not frontend_path.is_file():
                raise FileNotFoundError(f"Frontend file does not exist: {config.frontend}")
            frontend = config.frontend

        self.ipc = ipc_handler

        class API:
            def __init__(self, ipc: IPC):
                self.ipc = ipc

            def invoke(self, message):
                """
                Receive a message from JavaScript and forward it
                to the IPC layer.
                """
                if isinstance(message, str):
                    data = json.loads(message)
                elif isinstance(message, dict):
                    data = message
                else:
                    return {
                        "id": None,
                        "ok": False,
                        "error": {
                            "type": "InvalidMessageError",
                            "message": "IPC message must be a JSON string or object."
                        }
                    }

                return self.ipc.handle(data)

        api = API(ipc_handler)

        self.window = webview.create_window(
            title=config.title,
            url=frontend,
            js_api=api,
            width=config.width,
            height=config.height,
            resizable=config.resizable,
            fullscreen=config.fullscreen,
            minimized=config.minimized,
            on_top=config.on_top,
            hidden=splash is not None,
        )

        if hooks:
            for vesper_event, handlers in hooks.items():
                pywebview_attr = _HOOK_TO_EVENT.get(vesper_event)
                if pywebview_attr is None:
                    continue
                pywebview_event = getattr(self.window.events, pywebview_attr, None)
                if pywebview_event is None:
                    continue
                for fn in handlers:
                    pywebview_event += fn

        for handle in (secondary_windows or []):
            cfg = handle._config
            if dev_url:
                filename = Path(cfg.frontend).name
                sec_url = f"{dev_url.rstrip('/')}/{filename}"
            else:
                sec_frontend = Path(cfg.frontend)
                if not sec_frontend.is_file():
                    raise FileNotFoundError(
                        f"Secondary window frontend does not exist: {cfg.frontend}"
                    )
                sec_url = cfg.frontend
            sec_win = webview.create_window(
                title=cfg.title,
                url=sec_url,
                js_api=API(ipc_handler),
                width=cfg.width,
                height=cfg.height,
                resizable=cfg.resizable,
                fullscreen=cfg.fullscreen,
                minimized=cfg.minimized,
                on_top=cfg.on_top,
                hidden=True,
            )
            handle._attach(sec_win)

        if splash is not None:
            _DEFAULT_HTML = (
                "<body style='background:#1a1a1a;display:flex;align-items:center;"
                "justify-content:center;margin:0;font-family:sans-serif;color:#fff'>"
                "<p>Loading…</p></body>"
            )
            html_src = splash.get("html", "")
            sp_kwargs = (
                {"url": html_src} if html_src.endswith(".html")
                else {"html": html_src or _DEFAULT_HTML}
            )
            self._splash_win = webview.create_window(
                "",
                width=splash.get("width", 400),
                height=splash.get("height", 300),
                frameless=True,
                **sp_kwargs,
            )
            _splash = self._splash_win
            _main = self.window

            def _dismiss():
                _splash.destroy()
                _main.show()

            self.window.events.loaded += _dismiss

    def emit(self, event: str, payload=None) -> None:
        """
        Dispatch a named event to the frontend.

        Args:
            event: Event name (dispatched as "vesper:<event>" in JS).
            payload: JSON-serializable data attached as event.detail.
        """
        if self.window is None:
            return
        data = json.dumps(payload)
        js = f'window.dispatchEvent(new CustomEvent("vesper:{event}",{{detail:{data}}}))'
        self.window.evaluate_js(js)

    def open_dialog(
        self,
        multiple: bool = False,
        filters: list[dict] | None = None,
        directory: str = "",
    ) -> list[str] | None:
        """
        Open a native file-picker dialog.

        Args:
            multiple:  Allow selecting more than one file.
            filters:   List of ``{"name": str, "extensions": [str, ...]}`` dicts.
            directory: Initial directory shown to the user.

        Returns:
            List of selected absolute paths, or None if cancelled.
        """
        if self.window is None:
            raise RuntimeError("Cannot open dialog: window is not created yet.")
        result = self.window.create_file_dialog(
            webview.OPEN_DIALOG,
            directory=directory,
            allow_multiple=multiple,
            file_types=_to_file_types(filters),
        )
        return list(result) if result else None

    def save_dialog(
        self,
        filename: str = "",
        filters: list[dict] | None = None,
        directory: str = "",
    ) -> str | None:
        """
        Open a native save-file dialog.

        Args:
            filename:  Default file name pre-filled in the dialog.
            filters:   List of ``{"name": str, "extensions": [str, ...]}`` dicts.
            directory: Initial directory shown to the user.

        Returns:
            Absolute path chosen by the user, or None if cancelled.
        """
        if self.window is None:
            raise RuntimeError("Cannot open dialog: window is not created yet.")
        result = self.window.create_file_dialog(
            webview.SAVE_DIALOG,
            directory=directory,
            save_filename=filename,
            file_types=_to_file_types(filters),
        )
        return result[0] if result else None

    def pick_folder(
        self,
        directory: str = "",
        multiple: bool = False,
    ) -> list[str] | None:
        """
        Open a native folder-picker dialog.

        Args:
            directory: Initial directory shown to the user.
            multiple:  Allow selecting more than one folder.

        Returns:
            List of selected absolute paths, or None if cancelled.
        """
        if self.window is None:
            raise RuntimeError("Cannot open dialog: window is not created yet.")
        result = self.window.create_file_dialog(
            webview.FOLDER_DIALOG,
            directory=directory,
            allow_multiple=multiple,
        )
        return list(result) if result else None

    def minimize(self) -> None:
        """Minimize the main window."""
        if self.window is not None:
            self.window.minimize()

    def maximize(self) -> None:
        """Maximize the main window."""
        if self.window is not None:
            self.window.maximize()

    def restore(self) -> None:
        """Restore the main window from minimized or maximized state."""
        if self.window is not None:
            self.window.restore()

    def toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode on the main window."""
        if self.window is not None:
            self.window.toggle_fullscreen()

    def resize(self, width: int, height: int) -> None:
        """Resize the main window."""
        if self.window is not None:
            self.window.resize(width, height)

    def move(self, x: int, y: int) -> None:
        """Move the main window to the given screen coordinates."""
        if self.window is not None:
            self.window.move(x, y)

    def quit(self) -> None:
        """Destroy the main window and stop the event loop."""
        if self.window is not None:
            self.window.destroy()

    def list_screens(self) -> list[dict]:
        """Return info for all connected screens."""
        return [
            {
                "width": s.width,
                "height": s.height,
                "x": getattr(s, "x", 0),
                "y": getattr(s, "y", 0),
            }
            for s in webview.screens
        ]

    def show(self) -> None:
        """
        Start the GUI event loop.
        """

        if not self.window:
            raise RuntimeError("Window has not been created yet.")

        if self._menu:
            webview.start(menu=_to_webview_menu(self._menu))
        else:
            webview.start()
