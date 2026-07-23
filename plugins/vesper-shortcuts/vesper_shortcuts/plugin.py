from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

from vesper.core.plugin import VesperPlugin

logger = logging.getLogger("vesper.shortcuts")


class ShortcutsPlugin(VesperPlugin):
    """
    Global keyboard shortcuts plugin for Vesper.

    Registers system-wide hotkeys that fire even when the application window
    does not have focus. Uses pynput for cross-platform support.

    Accelerator format: modifier keys joined with ``+``, followed by the key.
    Supported modifiers: ``ctrl``, ``shift``, ``alt``, ``cmd`` (macOS) /
    ``win`` / ``super`` (Linux/Windows).

    The final key is either a single character (``k``, ``7``, ``/``) or one of
    pynput's named keys — ``space``, ``enter``, ``tab``, ``esc``, ``backspace``,
    ``delete``, ``up``/``down``/``left``/``right``, ``home``, ``end``,
    ``page_up``/``page_down``, ``insert``, ``f1``–``f20``, the ``media_*`` keys.
    Common spellings are accepted for those (``escape``, ``return``, ``pgup``,
    ``arrowleft``, …). An accelerator that cannot be parsed raises ``ValueError``
    at registration rather than failing silently at key-press time.

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

    # Spellings people actually type, mapped to the name pynput knows.
    _KEY_ALIASES: dict[str, str] = {
        "escape": "esc",
        "return": "enter",
        "del": "delete",
        "ins": "insert",
        "spacebar": "space",
        "pgup": "page_up",
        "pgdn": "page_down",
        "pagedown": "page_down",
        "pageup": "page_up",
        "arrowup": "up",
        "arrowdown": "down",
        "arrowleft": "left",
        "arrowright": "right",
        "capslock": "caps_lock",
        "numlock": "num_lock",
        "scrolllock": "scroll_lock",
        "printscreen": "print_screen",
    }

    # How long to wait for pynput's backend thread to finish coming up. See
    # _wait_ready.
    _READY_TIMEOUT = 2.0

    def __init__(self) -> None:
        self._hotkeys: dict[str, Callable] = {}
        self._listener = None
        self._app = None

    def _to_pynput(self, accelerator: str) -> str:
        """
        Translate an accelerator into pynput's hotkey syntax.

        pynput spells every non-character key in angle brackets — ``<space>``,
        ``<enter>``, ``<f2>`` — and feeds anything else to ``KeyCode.from_char``,
        which only accepts a single character. Passing ``space`` through bare
        therefore raised a bare ``ValueError: space``, so ``ctrl+alt+space`` (the
        most obvious launcher hotkey there is) could never be registered at all.
        """
        parts = accelerator.lower().split("+")
        converted = []
        for part in parts:
            if part in self._MODIFIER_MAP:
                converted.append(self._MODIFIER_MAP[part])
                continue
            part = self._KEY_ALIASES.get(part, part)
            converted.append(part if len(part) == 1 else f"<{part}>")
        return "+".join(converted)

    def _validate(self, accelerator: str) -> None:
        """
        Reject an unusable accelerator here, with an error that names the fix.

        Left to pynput this surfaces as ``ValueError: space`` from inside the
        listener constructor, which says nothing about which shortcut was wrong
        or what a right one looks like.
        """
        from pynput import keyboard

        try:
            keyboard.HotKey.parse(self._to_pynput(accelerator))
        except ValueError as exc:
            valid = ", ".join(sorted(k.name for k in keyboard.Key))
            raise ValueError(
                f"{accelerator!r} is not a usable global shortcut: pynput could not "
                f"parse {str(exc)!r}. Modifiers are ctrl/shift/alt/cmd (win, super); "
                f"the final key is a single character or one of: {valid}."
            ) from None

    @classmethod
    def _wait_ready(cls, listener) -> None:
        """
        Block until pynput's backend thread is actually up.

        pynput sets ``_running`` at the top of its thread but only builds the
        X11 recording context part-way through ``_run``. ``stop()`` called inside
        that window raises ``AttributeError: _display_record`` — which is how
        registering a second shortcut could kill the listener holding the first.
        The bounded poll degrades to "carry on" rather than hanging if a future
        pynput drops the attribute, and returns immediately if the thread died.
        """
        deadline = time.monotonic() + cls._READY_TIMEOUT
        while time.monotonic() < deadline:
            if getattr(listener, "_ready", True) or not listener.is_alive():
                return
            time.sleep(0.01)
        logger.debug("pynput listener did not report ready within %.1fs", cls._READY_TIMEOUT)

    def _stop_listener(self) -> None:
        if self._listener is None:
            return
        try:
            self._listener.stop()
        except Exception as exc:  # pragma: no cover - depends on pynput internals
            logger.debug("Stopping the pynput listener raised %r; dropping it anyway", exc)
        finally:
            self._listener = None

    def _restart_listener(self) -> None:
        self._stop_listener()

        if not self._hotkeys:
            return

        from pynput import keyboard

        pynput_map = {self._to_pynput(k): v for k, v in self._hotkeys.items()}
        listener = keyboard.GlobalHotKeys(pynput_map)
        listener.start()
        self._wait_ready(listener)
        self._listener = listener

    def _apply(self, hotkeys: dict[str, Callable]) -> None:
        """
        Swap in a new set of shortcuts, rolling back if it cannot be started.

        Without the rollback a single bad accelerator stayed in the map and every
        later add/remove re-raised on it, so one typo silently disabled every
        shortcut the app had already registered — permanently.
        """
        previous = dict(self._hotkeys)
        self._hotkeys = hotkeys
        try:
            self._restart_listener()
        except Exception:
            self._hotkeys = previous
            try:
                self._restart_listener()
            except Exception as exc:  # pragma: no cover - the old set already worked
                logger.debug("Could not restore the previous shortcuts: %r", exc)
            raise

    def add(self, accelerator: str, callback: Callable) -> None:
        """
        Register a global shortcut with a Python callback.

        Raises ``ValueError`` if the accelerator cannot be parsed; the shortcuts
        already registered keep working.
        """
        self._validate(accelerator)
        self._apply({**self._hotkeys, accelerator: callback})

    def remove(self, accelerator: str) -> None:
        """Unregister a global shortcut."""
        if accelerator not in self._hotkeys:
            return
        remaining = dict(self._hotkeys)
        remaining.pop(accelerator)
        self._apply(remaining)

    def remove_all(self) -> None:
        """Unregister all global shortcuts."""
        self._apply({})

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
