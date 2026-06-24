from __future__ import annotations

import asyncio
import inspect
import threading
import traceback
from typing import Any, Dict

from vesper.exceptions import CommandNotFoundError
from vesper.core.registry import CommandRegistry


class IPC:
    """
    Inter-Process Communication manager.

    Responsible for:
        - Receiving frontend messages
        - Validating requests
        - Resolving commands from registry
        - Executing commands (sync and async)
        - Returning structured responses
        - Error handling and reporting
    """

    def __init__(
        self,
        registry: CommandRegistry,
        *,
        middleware: list | None = None,
        debug: bool = False,
    ) -> None:
        """
        Initialize IPC with a command registry.

        Args:
            registry:   Command registry containing all registered commands.
            middleware: Shared middleware list. Passed by reference from App
                        so handlers registered after IPC construction are visible.
            debug:      Whether to include debug information in error responses.
        """
        self.registry = registry
        self.debug = debug
        self._middleware: list = middleware if middleware is not None else []

        self._loop = asyncio.new_event_loop()
        _started = threading.Event()

        def _run() -> None:
            asyncio.set_event_loop(self._loop)
            self._loop.call_soon(lambda: _started.set())
            self._loop.run_forever()

        self._loop_thread = threading.Thread(target=_run, daemon=True, name="vesper-async")
        self._loop_thread.start()
        _started.wait(timeout=5)

    def handle(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an incoming IPC message from the frontend.

        Expected message format:
            {
                "id": <request_id>,
                "command": "<command_name>",
                "args": {...}  # optional
            }

        Args:
            message: Dictionary containing the request

        Returns:
            Response dictionary with one of these formats:
            - Success: {"id": id, "ok": True, "result": result}
            - Error: {"id": id, "ok": False, "error": {"type": type, "message": message}}
        """
        if not isinstance(message, dict):
            return {
                "id": None,
                "ok": False,
                "error": {
                    "type": "InvalidMessageError",
                    "message": "IPC message must be a dictionary"
                }
            }

        request_id = message.get("id")
        command_name = message.get("command")
        args = message.get("args", {})

        if request_id is None:
            return {
                "id": None,
                "ok": False,
                "error": {
                    "type": "InvalidRequestError",
                    "message": "Missing request id"
                }
            }

        if not command_name:
            return {
                "id": request_id,
                "ok": False,
                "error": {
                    "type": "InvalidRequestError",
                    "message": "Missing command name"
                }
            }

        try:
            command = self.registry.get(command_name)
        except CommandNotFoundError as e:
            return {
                "id": request_id,
                "ok": False,
                "error": {
                    "type": "CommandNotFoundError",
                    "message": str(e)
                }
            }

        try:
            for mw in self._middleware:
                if inspect.iscoroutinefunction(mw):
                    future = asyncio.run_coroutine_threadsafe(
                        mw(command_name, args), self._loop
                    )
                    future.result()
                else:
                    mw(command_name, args)

            if isinstance(args, dict):
                if inspect.iscoroutinefunction(command):
                    future = asyncio.run_coroutine_threadsafe(command(**args), self._loop)
                    result = future.result()
                else:
                    result = command(**args)
            else:
                if inspect.iscoroutinefunction(command):
                    future = asyncio.run_coroutine_threadsafe(command(args), self._loop)
                    result = future.result()
                else:
                    result = command(args)

            return {
                "id": request_id,
                "ok": True,
                "result": result
            }
        except Exception as e:
            error = {
                "type": e.__class__.__name__,
                "message": str(e)
            }

            if self.debug:
                error["traceback"] = traceback.format_exc()

            return {
                "id": request_id,
                "ok": False,
                "error": error
            }
