"""Tests for the Vesper plugin system (VesperPlugin base class + App integration)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vesper import App, VesperPlugin


# ── VesperPlugin contract ─────────────────────────────────────────────────────


def test_vesper_plugin_is_abstract():
    with pytest.raises(TypeError):
        VesperPlugin()  # type: ignore


def test_vesper_plugin_subclass_without_register_is_abstract():
    class BadPlugin(VesperPlugin):
        pass

    with pytest.raises(TypeError):
        BadPlugin()


def test_vesper_plugin_subclass_with_register_instantiates():
    class GoodPlugin(VesperPlugin):
        def register(self, app) -> None:
            pass

    plugin = GoodPlugin()
    assert isinstance(plugin, VesperPlugin)


def test_vesper_plugin_sdk_path_returns_none_by_default():
    class MyPlugin(VesperPlugin):
        def register(self, app) -> None:
            pass

    assert MyPlugin.sdk_path() is None


def test_vesper_plugin_sdk_path_can_be_overridden(tmp_path):
    js = tmp_path / "my-plugin.js"
    js.write_text("// sdk")

    class MyPlugin(VesperPlugin):
        def register(self, app) -> None:
            pass

        @classmethod
        def sdk_path(cls) -> Path | None:
            return js

    assert MyPlugin.sdk_path() == js


# ── App(plugins=[...]) integration ───────────────────────────────────────────


def test_app_accepts_plugins_list():
    class NoopPlugin(VesperPlugin):
        def register(self, app) -> None:
            pass

    app = App(plugins=[NoopPlugin()])
    assert app is not None


def test_app_calls_register_on_each_plugin():
    calls = []

    class SpyPlugin(VesperPlugin):
        def register(self, app) -> None:
            calls.append(app)

    app = App(plugins=[SpyPlugin(), SpyPlugin()])
    assert len(calls) == 2
    assert all(c is app for c in calls)


def test_app_plugin_can_register_commands():
    class GreetPlugin(VesperPlugin):
        def register(self, app) -> None:
            @app.command("greet")
            def greet(name: str) -> str:
                return f"Hello {name}"

    app = App(plugins=[GreetPlugin()])
    assert "greet" in app.registry._commands


def test_app_plugin_command_callable_via_ipc():
    class MathPlugin(VesperPlugin):
        def register(self, app) -> None:
            @app.command("add")
            def add(a: int, b: int) -> int:
                return a + b

    app = App(plugins=[MathPlugin()])
    resp = app.ipc.handle({"id": "1", "command": "add", "args": {"a": 3, "b": 4}})
    assert resp["ok"] is True
    assert resp["result"] == 7


def test_app_no_plugins_still_works():
    app = App()
    assert app is not None
    app2 = App(plugins=None)
    assert app2 is not None
    app3 = App(plugins=[])
    assert app3 is not None


def test_app_plugin_can_add_middleware():
    log = []

    class LogPlugin(VesperPlugin):
        def register(self, app) -> None:
            @app.middleware
            def mw(command, args):
                log.append(command)

            @app.command("ping")
            def ping() -> str:
                return "pong"

    app = App(plugins=[LogPlugin()])
    app.ipc.handle({"id": "1", "command": "ping", "args": {}})
    assert "ping" in log


# ── VesperPlugin exported from public API ────────────────────────────────────


def test_vesper_plugin_exported_from_package():
    import vesper
    assert hasattr(vesper, "VesperPlugin")
    assert vesper.VesperPlugin is VesperPlugin
