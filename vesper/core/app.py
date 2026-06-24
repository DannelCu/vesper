from collections.abc import Callable

from vesper.core.config import WindowConfig
from vesper.core.module import Container
from vesper.core.registry import CommandRegistry
from vesper.core.window import Window, _HOOK_TO_EVENT
from vesper.core.ipc import IPC

_VALID_HOOKS: frozenset[str] = frozenset(_HOOK_TO_EVENT)


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

        self.ipc = IPC(self.registry, middleware=self._middleware, debug=self.debug)

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

        container = Container(meta["providers"])

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

    def emit(self, event: str, payload=None) -> None:
        """
        Dispatch a named event to the frontend.

        Args:
            event: Event name. The frontend receives it as "vesper:<event>".
            payload: JSON-serializable data passed as event.detail.
        """
        self.window.emit(event, payload)

    def run(self) -> None:
        """
        Start the Vesper application.

        This initializes the window and starts the IPC loop.
        """

        self.window.create(
            ipc_handler=self.ipc,
            config=self.config,
            hooks=self._hooks or None,
        )

        self.window.show()
