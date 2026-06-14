from typing import Any, Dict
import traceback

from vesper.exceptions import CommandNotFoundError
from vesper.core.registry import CommandRegistry


class IPC:
    """
    Inter-Process Communication manager.

    Responsible for:
        - Receiving frontend messages
        - Validating requests
        - Resolving commands from registry
        - Executing commands
        - Returning structured responses
        - Error handling and reporting
    """

    def __init__(self, registry: CommandRegistry, *, debug: bool = False) -> None:
        """
        Initialize IPC with a command registry.

        Args:
            registry: Command registry containing all registered commands
            debug: Whether to include debug information in error responses
        """
        self.registry = registry
        self.debug = debug

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
            if isinstance(args, dict):
                result = command(**args)
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
