import json
import webview

from vesper.core.config import WindowConfig
from vesper.core.ipc import IPC


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

    def create(self, ipc_handler: IPC, config: WindowConfig) -> None:
        """
        Create the application window and bind IPC.

        Args:
            ipc_handler:
                Instance of the IPC system responsible for
                handling frontend messages.
            config:
                Window configuration.
        """

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
            url=config.frontend,
            js_api=api,
            width=config.width,
            height=config.height,
            resizable=config.resizable,
            fullscreen=config.fullscreen,
            minimized=config.minimized,
            on_top=config.on_top,
        )

    def show(self) -> None:
        """
        Start the GUI event loop.
        """

        if not self.window:
            raise RuntimeError("Window has not been created yet.")

        webview.start()
