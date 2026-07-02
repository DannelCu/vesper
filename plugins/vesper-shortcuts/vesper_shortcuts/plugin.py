from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from vesper.core.plugin import VesperPlugin


class ShortcutsPlugin(VesperPlugin):
    """
    Global keyboard shortcuts plugin for Vesper.

    Registers system-wide hotkeys that fire even when the application window
    does not have focus. Uses pynput for cross-platform support.

    Accelerator format: modifier keys joined with ``+``, followed by the key.
    Supported modifiers: ``ctrl``, ``shift``, ``alt``, ``cmd`` (macOS) /
    ``win`` / ``super`` (Linux/Windows).

    Usage::

        from vesper import App
        from vesper_shortcuts import ShortcutsPlugin

        shortcuts = ShortcutsPlugin()
        app = App(plugins=[shortcuts])

        # Register in Python
        shortcuts.add("ctrl+shift+s", lambda: app.emit("screenshot"))

    Or from JavaScript::

        // Register and listen via IPC
        await vesper.shortcuts.register("ctrl+shift+s")
        vesper.on("shortcut", ({ accelerator }) => {
            if (accelerator === "ctrl+shift+s") takeScreenshot()
        })
    """

    _MODIFIER_MAP: dict[str, str] = {
        "ctrl":  "<ctrl>",
        "shift": "<shift>",
        "alt":   "<alt>",
        "cmd":   "<cmd>",
        "win":   "<cmd>",
        "super": "<cmd>",
    }

    def __init__(self) -> None:
        self._hotkeys: dict[str, Callable] = {}
        self._listener = None
        self._app = None

    def _to_pynput(self, accelerator: str) -> str:
        parts = accelerator.lower().split("+")
        return "+".join(self._MODIFIER_MAP.get(p, p) for p in parts)

    def _restart_listener(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

        if not self._hotkeys:
            return

        from pynput import keyboard

        pynput_map = {self._to_pynput(k): v for k, v in self._hotkeys.items()}
        self._listener = keyboard.GlobalHotKeys(pynput_map)
        self._listener.start()

    def add(self, accelerator: str, callback: Callable) -> None:
        """Register a global shortcut with a Python callback."""
        self._hotkeys[accelerator] = callback
        self._restart_listener()

    def remove(self, accelerator: str) -> None:
        """Unregister a global shortcut."""
        self._hotkeys.pop(accelerator, None)
        self._restart_listener()

    def remove_all(self) -> None:
        """Unregister all global shortcuts."""
        self._hotkeys.clear()
        self._restart_listener()

    def register(self, app) -> None:
        self._app = app

        plugin = self

        def _ipc_register(accelerator: str) -> None:
            def _fire():
                if plugin._app is not None:
                    plugin._app.window.emit("shortcut", {"accelerator": accelerator})
            plugin.add(accelerator, _fire)

        def _ipc_unregister(accelerator: str) -> None:
            plugin.remove(accelerator)

        def _ipc_unregister_all() -> None:
            plugin.remove_all()

        app.registry.register(_ipc_register, name="vesper:shortcuts:register")
        app.registry.register(_ipc_unregister, name="vesper:shortcuts:unregister")
        app.registry.register(_ipc_unregister_all, name="vesper:shortcuts:unregister_all")

    @classmethod
    def sdk_path(cls) -> Path | None:
        from importlib.resources import files
        return Path(str(files("vesper_shortcuts").joinpath("sdk/vesper-shortcuts.js")))
