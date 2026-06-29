from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class VesperPlugin(ABC):
    """
    Base class for all Vesper plugins.

    Subclass this and implement register() to add IPC commands, middleware,
    and lifecycle hooks to a Vesper application.

    Usage in app.py:
        from my_plugin import MyPlugin
        app = App(plugins=[MyPlugin()])

    To ship a JavaScript SDK file that `vesper sync-sdk` copies into the
    project's frontend directory, override sdk_path() as a classmethod.
    """

    @abstractmethod
    def register(self, app) -> None:
        """
        Register commands, middleware, and hooks with the Vesper app.

        Called automatically by App.__init__ for every plugin in the
        plugins= list. Use app.command, app.middleware, and app.on here.
        """

    @classmethod
    def sdk_path(cls) -> Path | None:
        """
        Return the absolute path to this plugin's JavaScript SDK file.

        `vesper sync-sdk` calls this to copy the JS file into the project's
        frontend (vanilla) or public (framework) directory. Return None if
        the plugin ships no JavaScript SDK.
        """
        return None
