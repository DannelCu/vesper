from collections.abc import Callable

from vesper.exceptions import CommandAlreadyRegisteredError, CommandNotFoundError


class CommandRegistry:
    """
    Registry for Python functions exposed as Vesper commands.
    """

    def __init__(self) -> None:
        self._commands: dict[str, Callable] = {}

    def register(self, fn: Callable, *, name: str | None = None) -> None:
        """
        Register a Python function as a Vesper command.

        Args:
            fn:
                Python callable to expose to the frontend.
            name:
                Optional public command name. If omitted, the function name is used.
        """

        command_name = name or fn.__name__

        if not isinstance(command_name, str) or not command_name.strip():
            raise ValueError("Command name must be a non-empty string.")

        command_name = command_name.strip()

        if command_name in self._commands:
            raise CommandAlreadyRegisteredError(
                f"Command already registered: {command_name}"
            )

        self._commands[command_name] = fn

    def get(self, name: str) -> Callable:
        """
        Get a registered command by name.
        """

        if name not in self._commands:
            raise CommandNotFoundError(f"Command not found: {name}")

        return self._commands[name]
