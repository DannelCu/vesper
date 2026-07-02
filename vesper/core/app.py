import sys as _sys
from collections.abc import Callable

from vesper.core.config import WindowConfig
from vesper.core.module import Container
from vesper.core.registry import CommandRegistry
from vesper.core.window import Window, WindowHandle, _HOOK_TO_EVENT
from vesper.core.ipc import IPC

_VALID_HOOKS: frozenset[str] = frozenset(_HOOK_TO_EVENT) | {"deeplink"}
_WEB_SCHEMES = ("http://", "https://", "ftp://", "ftps://")


class App:
    """
    Main entry point of a Vesper application.

    The App class is responsible for initializing core components
    (registry, IPC, window) and exposing the public API used by
    developers to build desktop applications.

    It acts as the central coordinator of the framework.
    """

    def __init__(
        self,
        *,
        title: str = "Vesper App",
        width: int = 800,
        height: int = 600,
        resizable: bool = True,
        fullscreen: bool = False,
        minimized: bool = False,
        on_top: bool = False,
        frontend: str = "frontend/index.html",
        debug: bool = False,
        root_module: type | None = None,
        version: str = "",
        update_url: str = "",
        plugins: list | None = None,
        fs_scope: list[str] | str | None = None,
    ) -> None:
        """
        Initialize the Vesper application core systems.

        Args:
            title:
                Window title.
            width:
                Initial window width.
            height:
                Initial window height.
            resizable:
                Whether the window can be resized.
            fullscreen:
                Whether the window starts in fullscreen mode.
            minimized:
                Whether the window starts minimized.
            on_top:
                Whether the window stays on top of other windows.
            frontend:
                Path to the frontend entry HTML file.
            debug:
                Whether to include debug information in IPC error responses.
            root_module:
                Optional root @Module class. All modules imported by it are
                registered automatically, so app.py stays minimal.
        """

        self.debug = debug
        self._version = version
        self._update_url = update_url
        self.config = WindowConfig(
            title=title,
            width=width,
            height=height,
            resizable=resizable,
            fullscreen=fullscreen,
            minimized=minimized,
            on_top=on_top,
            frontend=frontend,
        )

        self.registry = CommandRegistry()
        self.window = Window()
        self._middleware: list[Callable] = []
        self._hooks: dict[str, list[Callable]] = {}
        self._secondary_windows: list[WindowHandle] = []
        self._tray = None
        self._menu_items: list | None = None
        self._splash_config: dict | None = None
        self._global_providers: dict = {}

        # Detect deep link URL passed via command-line argument
        self._deeplink_url: str | None = None
        for _arg in _sys.argv[1:]:
            if "://" in _arg and not _arg.startswith(_WEB_SCHEMES):
                self._deeplink_url = _arg
                break

        # Built-in dialog commands — use vesper: prefix so sync-types skips them
        def _open_dialog(multiple: bool = False, filters=None, directory: str = ""):
            return self.window.open_dialog(multiple=multiple, filters=filters, directory=directory)

        def _save_dialog(filename: str = "", filters=None, directory: str = ""):
            return self.window.save_dialog(filename=filename, filters=filters, directory=directory)

        def _pick_folder(directory: str = "", multiple: bool = False):
            return self.window.pick_folder(directory=directory, multiple=multiple)

        self.registry.register(_open_dialog, name="vesper:dialog:open")
        self.registry.register(_save_dialog, name="vesper:dialog:save")
        self.registry.register(_pick_folder, name="vesper:dialog:folder")

        from vesper.core.notify import send as _notify_send

        def _notify(title: str = "", body: str = "") -> None:
            _notify_send(title, body)

        self.registry.register(_notify, name="vesper:notify")

        from vesper.core import fs as _fs
        from vesper.core.fs_scope import FsScope

        _scope = FsScope(fs_scope) if fs_scope is not None else None

        def _fs_read(path: str, encoding: str = "utf-8") -> str:
            return _fs.read(path, encoding, scope=_scope)

        def _fs_write(path: str, content: str, encoding: str = "utf-8") -> None:
            return _fs.write(path, content, encoding, scope=_scope)

        def _fs_exists(path: str) -> bool:
            return _fs.exists(path, scope=_scope)

        def _fs_list(path: str) -> list:
            return _fs.list_dir(path, scope=_scope)

        self.registry.register(_fs_read, name="vesper:fs:read")
        self.registry.register(_fs_write, name="vesper:fs:write")
        self.registry.register(_fs_exists, name="vesper:fs:exists")
        self.registry.register(_fs_list, name="vesper:fs:list")

        from vesper.core import shell as _shell
        from vesper.core import clipboard as _clipboard
        from vesper.core import os_info as _os_info

        self.registry.register(_shell.open_url, name="vesper:shell:open_url")
        self.registry.register(_shell.reveal, name="vesper:shell:reveal")
        self.registry.register(_clipboard.read, name="vesper:clipboard:read")
        self.registry.register(_clipboard.write, name="vesper:clipboard:write")
        self.registry.register(_os_info.get_info, name="vesper:os:info")

        # Window controls — lambdas defer to the Window instance so they work
        # even when registered before the PyWebView window is created.
        _w = self.window
        self.registry.register(lambda: _w.minimize(), name="vesper:window:minimize")
        self.registry.register(lambda: _w.maximize(), name="vesper:window:maximize")
        self.registry.register(lambda: _w.restore(), name="vesper:window:restore")
        self.registry.register(lambda: _w.toggle_fullscreen(), name="vesper:window:fullscreen")

        def _window_resize(width: int, height: int) -> None:
            _w.resize(width, height)

        def _window_move(x: int, y: int) -> None:
            _w.move(x, y)

        self.registry.register(_window_resize, name="vesper:window:resize")
        self.registry.register(_window_move, name="vesper:window:move")
        self.registry.register(lambda: _w.quit(), name="vesper:app:quit")
        self.registry.register(lambda: _w.list_screens(), name="vesper:screen:list")

        from vesper.core import updater as _updater

        _app = self

        def _update_check() -> dict | None:
            return _updater.check(_app._update_url, _app._version)

        def _update_download(url: str = "") -> str:
            def _on_progress(percent: int) -> None:
                _app.window.emit("update:progress", {"percent": percent})
            return _updater.download(url, on_progress=_on_progress)

        def _update_install(path: str = "", sha256: str = "") -> None:
            _updater.install(path, expected_sha256=sha256)

        self.registry.register(_update_check, name="vesper:update:check")
        self.registry.register(_update_download, name="vesper:update:download")
        self.registry.register(_update_install, name="vesper:update:install")

        self.ipc = IPC(self.registry, middleware=self._middleware, debug=self.debug)

        # Plugins register before modules so global DI providers (e.g. DbSession)
        # are available when the module container resolves service dependencies.
        for plugin in (plugins or []):
            plugin.register(self)

        if root_module is not None:
            self.register_module(root_module)

    def command(
        self,
        target: Callable | str | None = None,
        *,
        name: str | None = None
    ) -> Callable:
        """
        Register a function as a Vesper command.

        Supports both usages:

            @app.command
            def hello():
                ...

            @app.command("hello")
            def say_hello():
                ...

            @app.command(name="hello")
            def say_hello():
                ...
        """

        if callable(target):
            guards = getattr(target, "__vesper_guards__", None)
            self.registry.register(target, name=name, guards=guards)
            return target

        if isinstance(target, str):
            if name is not None:
                raise ValueError("Command name cannot be provided twice.")

            name = target

        elif target is not None:
            raise TypeError(
                "app.command expected a function, a command name string, or no argument."
            )

        def decorator(fn: Callable) -> Callable:
            guards = getattr(fn, "__vesper_guards__", None)
            self.registry.register(fn, name=name, guards=guards)
            return fn

        return decorator

    def register_global_provider(self, type_: type, instance) -> None:
        """
        Register a DI provider scoped to this App instance.

        Makes *instance* injectable as *type_* in every module container
        created by this App, without polluting other App instances (unlike
        ``Container.register_global``). Used by plugins.
        """
        self._global_providers[type_] = instance

    def add_teardown(self, fn: Callable) -> None:
        """
        Register a teardown function that runs after every IPC call.

        Teardown runs in a finally block — it executes whether the command
        succeeded or failed. Exceptions in teardown are suppressed.

        Used by plugins to clean up per-call resources (e.g. database sessions).

        Args:
            fn: Zero-argument callable to invoke after each IPC call.
        """
        self.ipc._teardown.append(fn)

    def middleware(self, fn: Callable) -> Callable:
        """
        Register a global IPC middleware function.

        Middleware runs before every command, in registration order. Raising
        an exception inside middleware rejects the call and returns an error
        response — use this for auth, logging, or rate-limiting.

        Signature: fn(command: str, args: Any) -> None
        Async middleware (async def) is also supported.

        Usage:
            @app.middleware
            def log(command, args):
                print(f"[IPC] {command}")

            @app.middleware
            def auth(command, args):
                if command.startswith("admin.") and not session.valid:
                    raise PermissionError("Unauthorized")
        """
        self._middleware.append(fn)
        return fn

    def on(self, event: str) -> Callable:
        """
        Register a lifecycle hook for a window event.

        Supported events: close, minimize, restore, focus, blur, loaded.

        Usage:
            @app.on("close")
            def handle_close():
                db.close()
        """
        if event not in _VALID_HOOKS:
            raise ValueError(
                f"Unknown lifecycle event: '{event}'. "
                f"Valid events: {sorted(_VALID_HOOKS)}"
            )

        def decorator(fn: Callable) -> Callable:
            self._hooks.setdefault(event, []).append(fn)
            return fn

        return decorator

    def register_module(self, module_cls: type) -> None:
        """
        Register a @Module class, wiring its controllers and providers.

        Resolves provider dependencies via the built-in IoC container and
        registers every @command method on each controller into the IPC
        registry under "<prefix>.<command_name>".

        Args:
            module_cls: A class decorated with @Module.
        """
        meta = getattr(module_cls, "__vesper_module__", None)
        if meta is None:
            raise TypeError(f"{module_cls.__name__} is not decorated with @Module.")

        for imported in meta["imports"]:
            self.register_module(imported)

        container = Container(meta["providers"], global_providers=self._global_providers)

        for ctrl_cls in meta["controllers"]:
            ctrl_meta = getattr(ctrl_cls, "__vesper_controller__", None)
            if ctrl_meta is None:
                raise TypeError(f"{ctrl_cls.__name__} is not decorated with @Controller.")

            prefix = ctrl_meta["prefix"]
            instance = container.resolve(ctrl_cls)

            for attr_name in dir(instance):
                if attr_name.startswith("_"):
                    continue
                method = getattr(instance, attr_name, None)
                if not callable(method):
                    continue
                cmd_meta = getattr(method, "__vesper_command__", None)
                if cmd_meta is None:
                    continue
                cmd_name = f"{prefix}.{cmd_meta['name']}" if prefix else cmd_meta["name"]
                method_guards = getattr(method, "__vesper_guards__", [])
                ctrl_guards = ctrl_meta.get("guards", [])
                all_guards = ctrl_guards + method_guards
                self.registry.register(method, name=cmd_name, guards=all_guards or None)

    def register_window(
        self,
        *,
        title: str = "Vesper Window",
        width: int = 800,
        height: int = 600,
        resizable: bool = True,
        fullscreen: bool = False,
        minimized: bool = False,
        on_top: bool = False,
        frontend: str,
    ) -> WindowHandle:
        """
        Pre-declare a secondary window.

        The window is created hidden when ``app.run()`` is called and shares
        the same IPC registry as the main window. Call ``handle.show()`` from
        a command to display it on demand.

        Args:
            title:     Window title.
            width:     Initial width in pixels.
            height:    Initial height in pixels.
            resizable: Whether the window can be resized.
            fullscreen: Whether the window starts fullscreen.
            minimized: Whether the window starts minimized.
            on_top:    Whether the window stays on top.
            frontend:  Path to the HTML entry file for this window.

        Returns:
            A :class:`WindowHandle` you can call ``.show()`` / ``.hide()`` /
            ``.close()`` / ``.emit()`` on after the app starts.
        """
        cfg = WindowConfig(
            title=title,
            width=width,
            height=height,
            resizable=resizable,
            fullscreen=fullscreen,
            minimized=minimized,
            on_top=on_top,
            frontend=frontend,
        )
        handle = WindowHandle(cfg)
        self._secondary_windows.append(handle)
        return handle

    def notify(self, title: str, body: str = "") -> None:
        """
        Send a native desktop notification (fire-and-forget).

        Dispatches in a background thread so it never blocks the app.
        Uses PowerShell on Windows, osascript on macOS, notify-send on Linux.

        Args:
            title: Notification title.
            body:  Notification body text.
        """
        from vesper.core.notify import send
        send(title, body)

    def tray(
        self,
        icon: str,
        menu: list,
        *,
        title: str = "",
    ) -> None:
        """
        Configure a system tray icon with a context menu.

        Must be called before ``app.run()``. Requires the ``vesper[tray]``
        extra (pystray + Pillow).

        Args:
            icon:  Path to the icon image file (PNG recommended).
            menu:  List of :class:`TrayMenuItem` items. Pass ``None`` to
                   insert a separator.
            title: Tooltip text shown when hovering over the tray icon.
        """
        from vesper.core.tray import Tray
        self._tray = Tray(icon=icon, menu=menu, title=title)

    def check_update(self) -> dict | None:
        """
        Check the configured update manifest for a newer version.

        Returns a dict with ``version``, ``notes``, and ``download_url`` if an
        update is available for the current platform, or None otherwise.
        Requires ``update_url`` and ``version`` to be set on the App.
        """
        from vesper.core import updater
        return updater.check(self._update_url, self._version)

    def download_update(
        self,
        url: str,
        on_progress: "Callable[[int], None] | None" = None,
    ) -> str:
        """
        Download an update binary from url to a temporary file.

        Args:
            url:         Direct download URL (from check_update result).
            on_progress: Optional callback called with percent (0–100).

        Returns:
            Local path to the downloaded binary.
        """
        from vesper.core import updater
        return updater.download(url, on_progress=on_progress)

    def install_update(self, path: str) -> None:
        """
        Replace the running executable with the binary at path and restart.

        On POSIX this re-execs the process. On Windows it launches a detached
        helper script and exits. Only meaningful for packaged apps.
        """
        from vesper.core import updater
        updater.install(path)

    def emit(self, event: str, payload=None) -> None:
        """
        Dispatch a named event to the frontend.

        Args:
            event: Event name. The frontend receives it as "vesper:<event>".
            payload: JSON-serializable data passed as event.detail.
        """
        self.window.emit(event, payload)

    def quit(self) -> None:
        """
        Destroy the main window and stop the application.

        Equivalent to the user clicking the close button. Can be called from
        Python or triggered from JS via ``vesper.quit()``.
        """
        self.window.quit()

    def splash(self, html: str = "", *, width: int = 400, height: int = 300) -> None:
        """
        Configure a splash screen shown while the main window loads.

        Must be called before ``app.run()``. The splash is a frameless window
        that is automatically destroyed once the main window fires its ``loaded``
        event.

        Args:
            html:   Inline HTML string, or path to an ``.html`` file.
                    Defaults to a built-in dark loading indicator.
            width:  Splash window width in pixels.
            height: Splash window height in pixels.
        """
        self._splash_config = {"html": html, "width": width, "height": height}

    def menu(self, items: list) -> None:
        """
        Set the native menu bar.

        Must be called before ``app.run()``. Items are :class:`MenuItem`
        instances; pass ``None`` in a submenu list to insert a separator.

        Args:
            items: List of top-level :class:`MenuItem` objects.
        """
        self._menu_items = items

    def run(self) -> None:
        """
        Start the Vesper application.

        This initializes the window and starts the IPC loop.
        """

        # Wire deep link: fire Python callbacks and emit JS event on first load.
        if self._deeplink_url:
            _url = self._deeplink_url
            _app = self

            def _fire_deeplink():
                for fn in _app._hooks.get("deeplink", []):
                    fn(_url)
                _app.window.emit("deeplink", {"url": _url})

            self._hooks.setdefault("loaded", []).append(_fire_deeplink)

        self.window.create(
            ipc_handler=self.ipc,
            config=self.config,
            hooks=self._hooks or None,
            secondary_windows=self._secondary_windows or None,
            menu=self._menu_items or None,
            splash=self._splash_config or None,
        )

        if self._tray is not None:
            self._tray.start()

        try:
            self.window.show()
        finally:
            if self._tray is not None:
                self._tray.stop()
