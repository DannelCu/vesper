import json
import os
from collections.abc import Callable
from pathlib import Path

import webview

from vesper.core.config import WindowConfig
from vesper.core.ipc import IPC
from vesper.core.logging import get_logger

logger = get_logger("window")


def _file_dialog_const(name: str, legacy: str):
    """
    Resolve one PyWebView file-dialog constant, new spelling first.

    PyWebView 5 moved these onto a ``FileDialog`` enum and deprecated the
    module-level names, which print a warning to stdout on *every* dialog. The
    old names still work, and pyproject allows ``pywebview>=4.0``, where the enum
    does not exist — so both spellings have to be supported.

    Resolved once at import rather than per call: the answer cannot change while
    the process runs, and a per-call getattr would put the fallback on the hot
    path of every dialog.
    """
    enum = getattr(webview, "FileDialog", None)
    value = getattr(enum, name, None)
    if value is None:
        value = getattr(webview, legacy)  # pywebview < 5
    return value


_FD_OPEN = _file_dialog_const("OPEN", "OPEN_DIALOG")
_FD_SAVE = _file_dialog_const("SAVE", "SAVE_DIALOG")
_FD_FOLDER = _file_dialog_const("FOLDER", "FOLDER_DIALOG")

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
        event_name = json.dumps("vesper:" + event)
        data = json.dumps(payload)
        js = f"window.dispatchEvent(new CustomEvent({event_name},{{detail:{data}}}))"
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


def _chrome_kwargs(config: "WindowConfig") -> dict:
    """
    The create_window kwargs shared by main and secondary windows.

    min_size is only passed when configured, so the backend default applies
    otherwise. easy_drag is only meaningful alongside frameless, but PyWebView
    ignores it for framed windows, so it is safe to pass unconditionally.
    """
    kwargs = {
        "frameless": config.frameless,
        "easy_drag": config.easy_drag,
        "transparent": config.transparent,
        "vibrancy": config.vibrancy,
    }
    if config.min_width is not None and config.min_height is not None:
        kwargs["min_size"] = (config.min_width, config.min_height)
    return kwargs


def _menu_class(name: str):
    """
    Resolve one of PyWebView's menu classes.

    Only ``Menu`` is re-exported at the package top level; ``MenuAction`` and
    ``MenuSeparator`` live in ``webview.menu``. Reading them off ``webview``
    raised AttributeError before the window opened, so every menu was broken —
    and the tests missed it because they replaced the whole ``webview`` module
    with a MagicMock, which invents any attribute asked of it.

    Resolved at import, like the file-dialog constants above, with the top level
    tried as a fallback in case an older PyWebView only exported it there.
    """
    try:
        from webview import menu as menu_module
    except ImportError:
        menu_module = None

    resolved = getattr(menu_module, name, None)
    if resolved is None:
        resolved = getattr(webview, name, None)
    return resolved


_MENU = _menu_class("Menu")
_MENU_ACTION = _menu_class("MenuAction")
_MENU_SEPARATOR = _menu_class("MenuSeparator")


def _to_webview_menu(items: list) -> list:
    """Convert a Vesper menu list to the format PyWebView expects."""
    from vesper.core.menu import MenuItem
    result = []
    for item in items:
        if item is None:
            result.append(_MENU_SEPARATOR())
        elif isinstance(item, MenuItem) and item.submenu is not None:
            result.append(_MENU(item.label, _to_webview_menu(item.submenu)))
        else:
            action = item.action if item.action is not None else (lambda: None)
            result.append(_MENU_ACTION(item.label, action))
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
        # Every backend window this Window opened, so quit() can close all of
        # them. PyWebView's start() returns when the *last* window goes away, so
        # destroying only the main one leaves the app running with nothing on
        # screen — the process never exits and quit() looks like it did nothing.
        self._secondary_wins: list = []

    def create(
        self,
        ipc_handler: IPC,
        config: WindowConfig,
        hooks: dict[str, list[Callable]] | None = None,
        secondary_windows: list[WindowHandle] | None = None,
        menu: list | None = None,
        splash: dict | None = None,
        serve_url: str | None = None,
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
            serve_url:
                Base URL of the production localhost server
                (``App(serve_frontend=True)``). Frontend files load from it
                instead of ``file://``. The dev server URL still wins, so
                ``vesper dev`` behaves the same either way.
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
            if serve_url:
                frontend = f"{serve_url.rstrip('/')}/{frontend_path.name}"
            else:
                frontend = config.frontend

        self.ipc = ipc_handler

        class API:
            # PyWebView builds the JS-callable surface by walking this object with
            # dir(), recursing into every public attribute and skipping names that
            # start with an underscore. A public `self.ipc` therefore published
            # window.pywebview.api.ipc.handle, .close and .registry.register to the
            # page — letting the frontend reach the registry and bypass the invoke
            # envelope that guards and middleware hang off. Private name, so only
            # invoke() is exposed.
            def __init__(self, ipc: IPC):
                self._ipc = ipc

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

                return self._ipc.handle(data)

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
            # Only pass a position when one was set; PyWebView centres the window
            # when x/y are None, which is what a fresh app should do.
            **({"x": config.x, "y": config.y} if config.x is not None and config.y is not None else {}),
            **_chrome_kwargs(config),
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
                if serve_url:
                    sec_url = f"{serve_url.rstrip('/')}/{sec_frontend.name}"
                else:
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
                **_chrome_kwargs(cfg),
            )
            handle._attach(sec_win)
            self._secondary_wins.append(sec_win)

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
        event_name = json.dumps("vesper:" + event)
        data = json.dumps(payload)
        js = f"window.dispatchEvent(new CustomEvent({event_name},{{detail:{data}}}))"
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
            _FD_OPEN,
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
            _FD_SAVE,
            directory=directory,
            save_filename=filename,
            file_types=_to_file_types(filters),
        )
        return result[0] if result else None

    def confirm_dialog(self, title: str, message: str) -> bool:
        """
        Show a native confirmation dialog.

        Returns:
            True when the user confirmed, False when they cancelled or dismissed it.
        """
        if self.window is None:
            raise RuntimeError("Cannot open dialog: window is not created yet.")
        return bool(self.window.create_confirmation_dialog(title, message))

    def message_dialog(self, title: str, message: str) -> None:
        """
        Show a native message dialog with a single acknowledgement button.

        PyWebView exposes only a confirmation dialog, so this is built on it and the
        answer discarded — from the caller's side there is nothing to decide.
        """
        if self.window is None:
            raise RuntimeError("Cannot open dialog: window is not created yet.")
        self.window.create_confirmation_dialog(title, message)

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
            _FD_FOLDER,
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
        """
        Destroy every window this app opened, which stops the event loop.

        Secondary windows go first: PyWebView keeps running until the last
        window is gone, so closing only the main one leaves the process alive
        with no UI. Each is destroyed independently — one that is already gone
        must not strand the rest, and the main window is what actually ends the
        loop.
        """
        for win in self._secondary_wins:
            try:
                win.destroy()
            except Exception:
                logger.debug("Secondary window was already gone at quit")
        self._secondary_wins.clear()

        if self.window is not None:
            self.window.destroy()

    def get_geometry(self) -> dict[str, int] | None:
        """
        Current size and position, or None when the window is gone.

        Read while the window still exists — after it is destroyed the backend either
        returns stale values or raises, which is why callers grab this before
        teardown rather than after.
        """
        if self.window is None:
            return None

        try:
            return {
                "width": int(self.window.width),
                "height": int(self.window.height),
                "x": int(self.window.x),
                "y": int(self.window.y),
            }
        except (AttributeError, TypeError, ValueError):
            return None

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

        kwargs = {}
        if self._menu:
            kwargs["menu"] = _to_webview_menu(self._menu)

        # Set by `vesper dev` (like VESPER_DEV_URL), never by `vesper run` or a
        # packaged build — so the inspector exists exactly when the dev server does.
        # Distinct from App(debug=...), which only controls IPC error detail.
        if os.environ.get("VESPER_DEVTOOLS"):
            kwargs["debug"] = True

        webview.start(**kwargs)
