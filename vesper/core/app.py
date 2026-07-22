import os as _os
import sys as _sys
import threading
from collections.abc import Callable

from vesper.core.config import WindowConfig
from vesper.core.logging import configure as configure_logging
from vesper.core.logging import get_logger
from vesper.core.module import Container
from vesper.core.registry import CommandRegistry
from vesper.core.window import Window, WindowHandle, _HOOK_TO_EVENT
from vesper.core.ipc import IPC

_VALID_HOOKS: frozenset[str] = frozenset(_HOOK_TO_EVENT) | {"deeplink"}
_WEB_SCHEMES = ("http://", "https://", "ftp://", "ftps://")


logger = get_logger("app")


def _extract_deeplink(argv: list[str]) -> str | None:
    """Find a custom-scheme URL in argv, ignoring ordinary web URLs."""
    for arg in argv:
        if "://" in arg and not arg.startswith(_WEB_SCHEMES):
            return arg
    return None

# How long App.quit() waits before destroying the window. PyWebView answers every IPC
# call by delivering the return value through evaluate_js on a non-daemon thread; that
# call never returns if the WebView is already gone, and the process then hangs at
# interpreter shutdown with the window closed. Quitting from inside a command handler
# is the normal case (a "Quit" button calls vesper.quit()), so the reply needs a beat
# to land first. Delivery is sub-millisecond in practice; this is deliberately generous
# while staying imperceptible.
_QUIT_DELAY_SECONDS = 0.05


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
        frameless: bool = False,
        easy_drag: bool = True,
        transparent: bool = False,
        vibrancy: bool = False,
        min_width: int | None = None,
        min_height: int | None = None,
        frontend: str = "frontend/index.html",
        debug: bool = False,
        root_module: type | None = None,
        version: str = "",
        update_url: str = "",
        plugins: list | None = None,
        fs_scope: list[str] | str | None = None,
        shell_scope: dict | list | None = None,
        single_instance: bool = False,
        remember_window: bool = False,
        power_events: bool = False,
        serve_frontend: bool = False,
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
            frameless:
                Draw the window without the native titlebar and borders. Pair with
                the ``vesper:window:*`` commands to build a custom titlebar — see
                docs/frameless.md.
            easy_drag:
                With ``frameless=True``, whether the whole window is draggable.
                Turn off when using declared drag regions (a custom titlebar).
            transparent:
                Transparent window background. On Linux this needs a compositor;
                without one the background renders black.
            vibrancy:
                macOS-only translucency effect. Ignored elsewhere.
            min_width:
                Minimum window width. Must be set together with ``min_height``.
            min_height:
                Minimum window height. Must be set together with ``min_width``.
            frontend:
                Path to the frontend entry HTML file.
            debug:
                Whether to include debug information in IPC error responses.
            root_module:
                Optional root @Module class. All modules imported by it are
                registered automatically, so app.py stays minimal.
            shell_scope:
                Allowlist of executables the frontend may run through
                ``vesper.process``: a list of binaries, or a dict mapping each
                binary to fnmatch argument patterns. Without one, all process
                execution is rejected — see docs/process.md.
            single_instance:
                Allow only one running copy. A second launch forwards its argv to
                the first — so a deep link reaches the running window — and exits.
                Opt-in because it costs a loopback listener and a lock file.
            remember_window:
                Restore the window's size and position from the previous run, and
                save them on close.
            power_events:
                Emit ``power:suspend`` / ``power:resume`` / ``power:lock`` /
                ``power:unlock`` to the frontend. Opt-in because it costs a D-Bus
                connection or a message window, and best-effort because not every
                platform publishes every event — see docs/power.md.
            serve_frontend:
                Serve the frontend over ``http://127.0.0.1`` (ephemeral port,
                per-session token) instead of loading it via ``file://``. Opt-in
                for apps that need ES modules, SPA routing or relative fetch in
                production. Ignored under ``vesper dev``, whose own server takes
                precedence. See docs/project-config.md for the trade-offs and
                the threat model.
        """

        self.debug = debug
        configure_logging(debug)
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
            frameless=frameless,
            easy_drag=easy_drag,
            transparent=transparent,
            vibrancy=vibrancy,
            min_width=min_width,
            min_height=min_height,
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
        self._deeplink_url: str | None = _extract_deeplink(_sys.argv[1:])

        self._remember_window = remember_window
        self._power_events = power_events
        self._serve_frontend = serve_frontend
        self._static_server = None
        self._single_instance = None
        if single_instance:
            from vesper.core.single_instance import SingleInstance

            self._single_instance = SingleInstance(
                self.config.title, on_message=self._on_second_instance
            )

        # Built-in dialog commands — use vesper: prefix so sync-types skips them
        def _open_dialog(multiple: bool = False, filters=None, directory: str = ""):
            return self.window.open_dialog(multiple=multiple, filters=filters, directory=directory)

        def _save_dialog(filename: str = "", filters=None, directory: str = ""):
            return self.window.save_dialog(filename=filename, filters=filters, directory=directory)

        def _pick_folder(directory: str = "", multiple: bool = False):
            return self.window.pick_folder(directory=directory, multiple=multiple)

        def _dialog_confirm(title: str = "", message: str = "") -> bool:
            return self.window.confirm_dialog(title, message)

        def _dialog_message(title: str = "", message: str = "") -> None:
            self.window.message_dialog(title, message)

        self.registry.register(_open_dialog, name="vesper:dialog:open")
        self.registry.register(_save_dialog, name="vesper:dialog:save")
        self.registry.register(_pick_folder, name="vesper:dialog:folder")
        self.registry.register(_dialog_message, name="vesper:dialog:message")
        self.registry.register(_dialog_confirm, name="vesper:dialog:confirm")
        # ask() is confirm() under a name that reads better for a yes/no question;
        # PyWebView offers one dialog primitive, so they share an implementation.
        self.registry.register(_dialog_confirm, name="vesper:dialog:ask")

        from vesper.core import autostart as _autostart

        def _autostart_enable() -> bool:
            return _autostart.enable(self.config.title)

        def _autostart_disable() -> bool:
            return _autostart.disable(self.config.title)

        def _autostart_is_enabled() -> bool:
            return _autostart.is_enabled(self.config.title)

        self.registry.register(_autostart_enable, name="vesper:autostart:enable")
        self.registry.register(_autostart_disable, name="vesper:autostart:disable")
        self.registry.register(_autostart_is_enabled, name="vesper:autostart:is_enabled")

        from vesper.core import power as _power

        def _power_prevent_sleep(reason: str = "Vesper app is busy") -> bool:
            return _power.prevent_sleep(reason)

        def _power_allow_sleep() -> bool:
            return _power.allow_sleep()

        self.registry.register(_power_prevent_sleep, name="vesper:power:prevent_sleep")
        self.registry.register(_power_allow_sleep, name="vesper:power:allow_sleep")

        from vesper.core import capabilities as _capabilities

        def _capabilities_probe() -> dict:
            # Booleans only. The `fix` strings are install instructions for whoever
            # runs the app, not something a web UI should be rendering.
            return _capabilities.available_map()

        self.registry.register(_capabilities_probe, name="vesper:capabilities")

        from vesper.core.notify import send as _notify_send

        def _notify(title: str = "", body: str = "") -> None:
            _notify_send(title, body)

        self.registry.register(_notify, name="vesper:notify")

        from vesper.core import fs as _fs
        from vesper.core.fs_scope import FsScope

        _scope = FsScope(fs_scope) if fs_scope is not None else None
        # Public so plugins that touch paths on behalf of the frontend (file
        # watching, screenshots to disk) enforce the same sandbox as the fs API.
        self.fs_scope = _scope

        def _fs_read(path: str, encoding: str = "utf-8") -> str:
            return _fs.read(path, encoding, scope=_scope)

        def _fs_write(path: str, content: str, encoding: str = "utf-8") -> None:
            return _fs.write(path, content, encoding, scope=_scope)

        def _fs_exists(path: str) -> bool:
            return _fs.exists(path, scope=_scope)

        def _fs_list(path: str) -> list:
            return _fs.list_dir(path, scope=_scope)

        def _fs_trash(path: str) -> bool:
            return _fs.trash(path, scope=_scope)

        def _fs_mkdir(path: str, parents: bool = False) -> None:
            return _fs.mkdir(path, parents, scope=_scope)

        def _fs_copy(src: str, dst: str) -> None:
            return _fs.copy(src, dst, scope=_scope)

        def _fs_move(src: str, dst: str) -> None:
            return _fs.move(src, dst, scope=_scope)

        def _fs_remove(path: str, recursive: bool = False) -> None:
            return _fs.remove(path, recursive, scope=_scope)

        def _fs_stat(path: str) -> dict:
            return _fs.stat(path, scope=_scope)

        def _fs_read_bytes(path: str) -> str:
            return _fs.read_bytes(path, scope=_scope)

        def _fs_write_bytes(path: str, data: str) -> None:
            return _fs.write_bytes(path, data, scope=_scope)

        self.registry.register(_fs_read, name="vesper:fs:read")
        self.registry.register(_fs_write, name="vesper:fs:write")
        self.registry.register(_fs_exists, name="vesper:fs:exists")
        self.registry.register(_fs_list, name="vesper:fs:list")
        self.registry.register(_fs_trash, name="vesper:fs:trash")
        self.registry.register(_fs_mkdir, name="vesper:fs:mkdir")
        self.registry.register(_fs_copy, name="vesper:fs:copy")
        self.registry.register(_fs_move, name="vesper:fs:move")
        self.registry.register(_fs_remove, name="vesper:fs:remove")
        self.registry.register(_fs_stat, name="vesper:fs:stat")
        self.registry.register(_fs_read_bytes, name="vesper:fs:read_bytes")
        self.registry.register(_fs_write_bytes, name="vesper:fs:write_bytes")

        from vesper.core import shell as _shell
        from vesper.core import clipboard as _clipboard
        from vesper.core import os_info as _os_info

        self.registry.register(_shell.open_url, name="vesper:shell:open_url")
        self.registry.register(_shell.reveal, name="vesper:shell:reveal")
        from vesper.core import badge as _badge

        self.registry.register(_badge.set_progress, name="vesper:badge:set_progress")
        self.registry.register(_badge.clear_progress, name="vesper:badge:clear_progress")
        self.registry.register(_badge.set_badge, name="vesper:badge:set_badge")
        self.registry.register(_badge.clear_badge, name="vesper:badge:clear_badge")
        self.registry.register(_clipboard.read_image, name="vesper:clipboard:read_image")
        self.registry.register(_clipboard.write_image, name="vesper:clipboard:write_image")
        self.registry.register(_clipboard.read, name="vesper:clipboard:read")
        self.registry.register(_clipboard.write, name="vesper:clipboard:write")

        def _clipboard_write_files(paths: list) -> bool:
            return _clipboard.write_files(paths)

        def _clipboard_read_files() -> list:
            return _clipboard.read_files(scope=_scope)

        self.registry.register(_clipboard_write_files, name="vesper:clipboard:write_files")
        self.registry.register(_clipboard_read_files, name="vesper:clipboard:read_files")
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

        from vesper.core import positioner as _positioner

        def _window_position(
            position: str,
            screen=None,
            offset_x: int = 0,
            offset_y: int = 0,
        ) -> None:
            geometry = _w.get_geometry()
            if geometry is None:
                raise RuntimeError("Cannot position: window is not created yet.")
            screens = _w.list_screens()
            index = _positioner.resolve_screen_index(screen, screens)
            x, y = _positioner.compute(
                position,
                (geometry["width"], geometry["height"]),
                screens,
                screen_index=index,
                offset=(offset_x, offset_y),
            )
            _w.move(x, y)

        self.registry.register(_window_position, name="vesper:window:position")

        from vesper.core import window_effects as _window_effects

        def _window_set_backdrop(kind: str = "mica") -> bool:
            return _window_effects.set_backdrop(kind)

        self.registry.register(_window_set_backdrop, name="vesper:window:set_backdrop")
        # Routed through App.quit() rather than Window.quit() so the frontend's
        # vesper.quit() call gets its reply delivered before the WebView disappears.
        self.registry.register(lambda: self.quit(), name="vesper:app:quit")
        self.registry.register(lambda: _w.list_screens(), name="vesper:screen:list")

        from vesper.core import process as _process

        # Secure by default: with no scope declared, every invocation is rejected
        # before a process exists, mirroring an FsScope with no roots.
        _pscope = (
            shell_scope if isinstance(shell_scope, _process.ShellScope)
            else _process.ShellScope(shell_scope) if shell_scope is not None
            else None
        )
        self.shell_scope = _pscope
        self._process_manager = _process.ProcessManager(self.emit)

        def _process_run(argv: list, cwd: str = "", timeout: float = 0) -> dict:
            return _process.run(
                argv, scope=_pscope, cwd=cwd or None, timeout=timeout or None
            )

        def _process_spawn(argv: list, cwd: str = "") -> int:
            return self._process_manager.spawn(argv, scope=_pscope, cwd=cwd or None)

        def _process_kill(id: int) -> bool:
            return self._process_manager.kill(id)

        self.registry.register(_process_run, name="vesper:process:run")
        self.registry.register(_process_spawn, name="vesper:process:spawn")
        self.registry.register(_process_kill, name="vesper:process:kill")

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

        from vesper.core import net as _net

        def _net_download(url: str = "", dest: str = "", sha256: str = "", id: str = "") -> str:
            def _on_progress(percent: int) -> None:
                _app.window.emit("net:progress", {"id": id, "percent": percent})

            return _net.download(
                url, dest,
                on_progress=_on_progress,
                expected_sha256=sha256,
                scope=_scope,
            )

        self.registry.register(_net_download, name="vesper:net:download")

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
        frameless: bool = False,
        easy_drag: bool = True,
        transparent: bool = False,
        vibrancy: bool = False,
        min_width: int | None = None,
        min_height: int | None = None,
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
            frameless: Draw without the native titlebar and borders.
            easy_drag: With frameless, whether the whole window is draggable.
            transparent: Transparent window background (needs a compositor on Linux).
            vibrancy:  macOS-only translucency effect.
            min_width: Minimum width; set together with min_height.
            min_height: Minimum height; set together with min_width.
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
            frameless=frameless,
            easy_drag=easy_drag,
            transparent=transparent,
            vibrancy=vibrancy,
            min_width=min_width,
            min_height=min_height,
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

    def install_update(self, path: str, *, expected_sha256: str = "") -> None:
        """
        Replace the running executable with the binary at path and restart.

        On POSIX this re-execs the process. On Windows it launches a detached
        helper script and exits. Only meaningful for packaged apps.

        Pass expected_sha256 (from the manifest sha256 field) to verify the
        binary before installing. Raises ValueError on mismatch.
        """
        from vesper.core import updater
        updater.install(path, expected_sha256=expected_sha256)

    def emit(self, event: str, payload=None) -> None:
        """
        Dispatch a named event to the frontend.

        Args:
            event: Event name. The frontend receives it as "vesper:<event>".
            payload: JSON-serializable data passed as event.detail.
        """
        self.window.emit(event, payload)

    def _restore_window_state(self) -> None:
        """Apply stored geometry to the window config before the window is created."""
        try:
            from vesper.core import window_state

            screens = self._safe_list_screens()
            geometry = window_state.restorable(self.config.title, screens)
            if not geometry:
                return

            self.config.width = geometry["width"]
            self.config.height = geometry["height"]

            # x/y are absent when the stored position was off-screen; leaving the
            # config untouched keeps the backend's default centring.
            if "x" in geometry and "y" in geometry:
                self.config.x = geometry["x"]
                self.config.y = geometry["y"]
        except Exception:
            logger.exception("Could not restore window state; using defaults")

    def _save_window_state(self) -> None:
        """Persist the window's current geometry. Never raises."""
        try:
            from vesper.core import window_state

            geometry = self.window.get_geometry()
            if geometry:
                window_state.save(self.config.title, geometry)
        except Exception:
            logger.exception("Could not save window state")

    def _safe_list_screens(self) -> list:
        """Screen list, or empty when the backend cannot report one yet."""
        try:
            return self.window.list_screens()
        except Exception:
            # Called before the GUI backend is up, so this is expected rather than
            # exceptional; window_state treats an empty list as "cannot verify".
            logger.debug("Screen list unavailable while restoring window state")
            return []

    def _fire_deeplink(self, url: str) -> None:
        """
        Deliver a deep link to the app.

        Used both for a URL present in argv at startup and for one forwarded by a
        second instance while this one is already running, so a link behaves the same
        either way.
        """
        self._deeplink_url = url

        for fn in self._hooks.get("deeplink", []):
            try:
                fn(url)
            except Exception:
                # One bad handler must not stop the others or kill the listener
                # thread this may be running on.
                logger.exception("Deep link handler %r failed", fn)

        try:
            self.window.emit("deeplink", {"url": url})
        except Exception:
            logger.exception("Failed to emit deeplink event to the frontend")

    def _on_second_instance(self, argv: list[str]) -> None:
        """
        Handle argv forwarded by another copy of this app.

        Runs on the single-instance listener thread. Raising here would kill that
        thread and silently stop the app from accepting any further deep links, so
        failures are logged instead.
        """
        try:
            url = _extract_deeplink(argv[1:] if argv else [])
            if url:
                self._fire_deeplink(url)
        except Exception:
            logger.exception("Failed handling a second instance launch")

    def quit(self) -> None:
        """
        Destroy the main window and stop the application.

        Equivalent to the user clicking the close button. Can be called from
        Python or triggered from JS via ``vesper.quit()``.

        The window is destroyed a moment later rather than immediately, so that a
        call made from inside a command handler can still return its result to the
        frontend. See ``_QUIT_DELAY_SECONDS``. Use ``app.window.quit()`` when you
        need the window torn down synchronously and no IPC reply is pending.
        """
        timer = threading.Timer(_QUIT_DELAY_SECONDS, self.window.quit)
        timer.daemon = True
        timer.start()

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

    def _preflight(self) -> None:
        """
        Warn once, at startup, about features this app configured whose backend is
        missing on this machine.

        Only what the app asked for explicitly is checked. Guessing intent would
        mean warning about a clipboard the app may never touch, and a startup that
        warns about everything trains people to ignore it.

        This warns; it never aborts. The one hard failure is ``.tray()``, which
        already raises when pystray is absent, and that stays as it is.
        """
        from vesper.core import capabilities

        # Badges are deliberately absent: they are never declared on the App, so
        # there is no configuration to check against — calling set_badge() is the
        # only signal, and that happens long after startup.
        configured = []
        if self._tray is not None:
            configured.append(("tray", "system tray"))
        if self._power_events:
            configured.append(("power_events", "power events"))

        if not configured:
            return

        report = capabilities.probe()
        for name, description in configured:
            entry = report.get(name)
            if entry is None or entry["available"]:
                continue

            fix = f" Fix: {entry['fix']}" if entry["fix"] else ""
            logger.warning(
                "%s is configured but unavailable on this system (%s).%s",
                description, entry["detail"], fix,
            )

    def run(self) -> None:
        """
        Start the Vesper application.

        This initializes the window and starts the IPC loop.

        Returns immediately without opening a window when ``single_instance`` is
        enabled and another copy is already running; that copy has been handed this
        process's argv by then.
        """

        if self._single_instance is not None and not self._single_instance.acquire():
            logger.debug("Another instance is running; handed it our arguments")
            return

        self._preflight()

        if self._remember_window:
            self._restore_window_state()

        # Wire deep link: fire Python callbacks and emit JS event on first load.
        if self._deeplink_url:
            _url = self._deeplink_url
            self._hooks.setdefault("loaded", []).append(
                lambda: self._fire_deeplink(_url)
            )

        # The dev server takes precedence: under `vesper dev` the frontend is
        # already served over HTTP, so starting a second server would be waste.
        serve_url = None
        if self._serve_frontend and not _os.environ.get("VESPER_DEV_URL"):
            from vesper.core import static_server
            from pathlib import Path as _Path

            frontend_dir = _Path(self.config.frontend).resolve().parent
            self._static_server, serve_url = static_server.start(
                frontend_dir, token=static_server.new_token()
            )

        self.window.create(
            ipc_handler=self.ipc,
            config=self.config,
            hooks=self._hooks or None,
            secondary_windows=self._secondary_windows or None,
            menu=self._menu_items or None,
            splash=self._splash_config or None,
            serve_url=serve_url,
        )

        if self._tray is not None:
            self._tray.start()

        if self._power_events:
            # Started after the window exists, since the events are delivered to it.
            from vesper.core import power as _power_mod

            if not _power_mod.start_power_monitor(self.window.emit):
                logger.debug("Power events unavailable on this system")

        try:
            self.window.show()
        finally:
            # Geometry has to be read before the window is torn down, and the window
            # is already gone by the time show() returns on some backends — so the
            # save is driven by the "closing" hook where available and this is the
            # fallback for a clean exit.
            if self._remember_window:
                self._save_window_state()
            if self._tray is not None:
                self._tray.stop()
            if self._power_events:
                from vesper.core import power as _power_mod

                _power_mod.stop_power_monitor()
            # A closed window must not leave spawned children running.
            self._process_manager.kill_all()
            if self._static_server is not None:
                self._static_server.shutdown()
                self._static_server.server_close()
                self._static_server = None
            self.ipc.close()
            if self._single_instance is not None:
                self._single_instance.release()
