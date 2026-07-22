from __future__ import annotations

import asyncio
import threading
import uuid
from pathlib import Path

from vesper.core.plugin import VesperPlugin


class NotifyPlugin(VesperPlugin):
    """
    Rich notifications for Vesper via desktop-notifier: click callbacks, action
    buttons, custom icons and sound.

    The core's ``vesper.notify()`` stays untouched as the minimal fallback —
    this plugin adds what the shell-out backends cannot do: knowing that the
    user clicked. Clicks come back as events:

        vesper.on("notify:clicked", ({ id }) => ...)
        vesper.on("notify:action",  ({ id, button }) => ...)

    desktop-notifier is asyncio-based, so the plugin runs a private event loop
    on a daemon thread and bridges the synchronous IPC calls onto it.

    **macOS:** click and button callbacks only work from a *signed app bundle* —
    the notification centre ignores callbacks from unsigned processes. See the
    README and docs/code-signing.md.

    Usage::

        from vesper_notify import NotifyPlugin

        app = App(plugins=[NotifyPlugin(app_name="My App")])
    """

    def __init__(self, *, app_name: str = "Vesper App") -> None:
        self._app_name = app_name
        self._app = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._notifier = None
        self._lock = threading.Lock()

    def register(self, app) -> None:
        self._app = app

        def _send(
            title: str,
            body: str = "",
            buttons: list = [],
            icon: str = "",
            sound: bool = False,
        ) -> str:
            return self.send(title, body, buttons=buttons, icon=icon, sound=sound)

        app.registry.register(_send, name="vesper:notify:send")

    # ── asyncio bridge ───────────────────────────────────────────────────────

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None:
                loop = asyncio.new_event_loop()
                started = threading.Event()

                def _run() -> None:
                    asyncio.set_event_loop(loop)
                    loop.call_soon(started.set)
                    loop.run_forever()

                threading.Thread(target=_run, daemon=True, name="vesper-notify").start()
                started.wait(timeout=5)
                self._loop = loop
            return self._loop

    def _ensure_notifier(self):
        if self._notifier is None:
            from desktop_notifier import DesktopNotifier

            self._notifier = DesktopNotifier(app_name=self._app_name)
        return self._notifier

    # ── API ──────────────────────────────────────────────────────────────────

    def send(
        self,
        title: str,
        body: str = "",
        *,
        buttons: list[str] | None = None,
        icon: str = "",
        sound: bool = False,
    ) -> str:
        """
        Show a notification. Returns an id echoed by the click/action events.

        Args:
            title:   Notification title.
            body:    Body text.
            buttons: Action button labels; a press emits ``notify:action``
                     with ``{id, button}``.
            icon:    Path to a custom icon image.
            sound:   Play the platform's default notification sound.
        """
        from desktop_notifier import DEFAULT_SOUND, Button, Icon

        notify_id = uuid.uuid4().hex[:12]
        emit = self._app.emit

        def _clicked() -> None:
            try:
                emit("notify:clicked", {"id": notify_id})
            except Exception:
                pass

        def _pressed(label: str):
            def _handler() -> None:
                try:
                    emit("notify:action", {"id": notify_id, "button": label})
                except Exception:
                    pass
            return _handler

        kwargs = {
            "title": title,
            "message": body,
            "on_clicked": _clicked,
            "buttons": [
                Button(title=label, on_pressed=_pressed(label))
                for label in (buttons or [])
            ],
        }
        if icon:
            kwargs["icon"] = Icon(path=Path(icon))
        if sound:
            kwargs["sound"] = DEFAULT_SOUND

        loop = self._ensure_loop()
        notifier = self._ensure_notifier()

        future = asyncio.run_coroutine_threadsafe(notifier.send(**kwargs), loop)
        # Surfacing a backend failure beats returning an id for a notification
        # that never appeared.
        future.result(timeout=10)
        return notify_id

    @classmethod
    def sdk_path(cls) -> Path | None:
        from importlib.resources import files
        return Path(str(files("vesper_notify").joinpath("sdk/vesper-notify.js")))
