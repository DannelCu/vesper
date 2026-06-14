from collections.abc import Callable

from vesper.core.config import WindowConfig
from vesper.core.registry import CommandRegistry
from vesper.core.window import Window
from vesper.core.ipc import IPC


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
        self.ipc = IPC(self.registry, debug=self.debug)

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
            self.registry.register(target, name=name)
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
            self.registry.register(fn, name=name)
            return fn

        return decorator

    def run(self) -> None:
        """
        Start the Vesper application.

        This initializes the window and starts the IPC loop.
        """

        self.window.create(
            ipc_handler=self.ipc,
            config=self.config,
        )

        self.window.show()
