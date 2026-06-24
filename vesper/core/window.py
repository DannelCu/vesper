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

    def create(
        self,
        ipc_handler: IPC,
        config: WindowConfig,
        hooks: dict[str, list[Callable]] | None = None,
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
        """

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

    def show(self) -> None:
        """
        Start the GUI event loop.
        """

        if not self.window:
            raise RuntimeError("Window has not been created yet.")

        webview.start()
