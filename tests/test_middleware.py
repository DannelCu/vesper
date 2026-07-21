import asyncio

import pytest

from vesper import App
from vesper.core.ipc import IPC
from vesper.core.registry import CommandRegistry


def _make_ipc(middleware=None, *, debug=False):
    registry = CommandRegistry()
    ipc = IPC(registry, middleware=middleware, debug=debug)
    return ipc, registry


# ── app.middleware decorator ──────────────────────────────────────────────────


def test_middleware_decorator_registers_function():
    app = App()

    @app.middleware
    def mw(command, args): pass

    assert mw in app._middleware


def test_middleware_decorator_returns_original_function():
    app = App()

    def mw(command, args):
        return 42

    result = app.middleware(mw)
    assert result is mw


def test_middleware_multiple_registered_in_order():
    app = App()
    order = []

    @app.middleware
    def first(command, args): order.append("first")

    @app.middleware
    def second(command, args): order.append("second")

    assert app._middleware[0] is first
    assert app._middleware[1] is second


# ── IPC middleware execution ──────────────────────────────────────────────────


def test_middleware_is_called_on_every_command():
    calls = []
    mw_list = [lambda cmd, args: calls.append(cmd)]
    ipc, registry = _make_ipc(mw_list)
    registry.register(lambda: "ok", name="ping")

    ipc.handle({"id": "1", "command": "ping", "args": {}})
    assert calls == ["ping"]


def test_middleware_receives_correct_command_name():
    received = {}
    mw_list = [lambda cmd, args: received.update({"cmd": cmd})]
    ipc, registry = _make_ipc(mw_list)
    registry.register(lambda: None, name="my_command")

    ipc.handle({"id": "1", "command": "my_command", "args": {}})
    assert received["cmd"] == "my_command"


def test_middleware_receives_args():
    received = {}
    mw_list = [lambda cmd, args: received.update({"args": args})]
    ipc, registry = _make_ipc(mw_list)
    registry.register(lambda x: x, name="echo")

    ipc.handle({"id": "1", "command": "echo", "args": {"x": 99}})
    assert received["args"] == {"x": 99}


def test_middleware_runs_before_command():
    log = []
    mw_list = [lambda cmd, args: log.append("middleware")]
    ipc, registry = _make_ipc(mw_list)

    def cmd():
        log.append("command")
        return "done"

    registry.register(cmd)
    ipc.handle({"id": "1", "command": "cmd", "args": {}})
    assert log == ["middleware", "command"]


def test_multiple_middleware_run_in_order():
    log = []
    mw_list = [
        lambda cmd, args: log.append(1),
        lambda cmd, args: log.append(2),
        lambda cmd, args: log.append(3),
    ]
    ipc, registry = _make_ipc(mw_list)
    registry.register(lambda: None, name="noop")

    ipc.handle({"id": "1", "command": "noop", "args": {}})
    assert log == [1, 2, 3]


def test_middleware_exception_returns_error_response():
    def blocking_mw(cmd, args):
        raise PermissionError("Forbidden")

    ipc, registry = _make_ipc([blocking_mw])
    registry.register(lambda: "secret", name="secret")

    resp = ipc.handle({"id": "1", "command": "secret", "args": {}})
    assert resp["ok"] is False
    # Middleware raising is a bug in the middleware, reported under its own type
    # with the original class kept as the cause.
    assert resp["error"]["type"] == "MiddlewareError"
    assert resp["error"]["cause"] == "PermissionError"
    assert "Forbidden" in resp["error"]["message"]


def test_middleware_exception_stops_command():
    command_called = []

    def blocking_mw(cmd, args):
        raise RuntimeError("blocked")

    ipc, registry = _make_ipc([blocking_mw])

    def secret_cmd():
        command_called.append(True)
        return "secret"

    registry.register(secret_cmd)
    ipc.handle({"id": "1", "command": "secret_cmd", "args": {}})
    assert command_called == []


def test_middleware_exception_stops_remaining_middleware():
    log = []

    def mw1(cmd, args): log.append(1)
    def mw2(cmd, args): raise ValueError("stop")
    def mw3(cmd, args): log.append(3)

    ipc, registry = _make_ipc([mw1, mw2, mw3])
    registry.register(lambda: None, name="noop")
    ipc.handle({"id": "1", "command": "noop", "args": {}})
    assert log == [1]


def test_no_middleware_command_still_works():
    ipc, registry = _make_ipc()
    registry.register(lambda: "hello", name="greet")
    resp = ipc.handle({"id": "1", "command": "greet", "args": {}})
    assert resp["ok"] is True
    assert resp["result"] == "hello"


# ── Async middleware ──────────────────────────────────────────────────────────


def test_async_middleware_is_called():
    log = []

    async def async_mw(cmd, args):
        await asyncio.sleep(0)
        log.append(cmd)

    ipc, registry = _make_ipc([async_mw])
    registry.register(lambda: None, name="noop")
    ipc.handle({"id": "1", "command": "noop", "args": {}})
    assert log == ["noop"]


def test_async_middleware_exception_returns_error():
    async def async_blocking(cmd, args):
        raise PermissionError("async blocked")

    ipc, registry = _make_ipc([async_blocking])
    registry.register(lambda: "data", name="data")
    resp = ipc.handle({"id": "1", "command": "data", "args": {}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "MiddlewareError"
    assert resp["error"]["cause"] == "PermissionError"


def test_sync_and_async_middleware_coexist():
    log = []

    def sync_mw(cmd, args): log.append("sync")

    async def async_mw(cmd, args):
        await asyncio.sleep(0)
        log.append("async")

    ipc, registry = _make_ipc([sync_mw, async_mw])
    registry.register(lambda: None, name="noop")
    ipc.handle({"id": "1", "command": "noop", "args": {}})
    assert log == ["sync", "async"]


# ── App-level integration ─────────────────────────────────────────────────────


def test_app_middleware_shared_with_ipc():
    """Middleware added via @app.middleware after IPC creation is seen by IPC."""
    app = App()
    app.registry.register(lambda: "hi", name="greet")

    log = []

    @app.middleware
    def mw(cmd, args):
        log.append(cmd)

    app.ipc.handle({"id": "1", "command": "greet", "args": {}})
    assert log == ["greet"]


def test_app_middleware_runs_for_module_commands():
    from vesper import Controller, Injectable, Module, command as vcmd

    log = []

    @Injectable()
    class Svc:
        def hi(self): return "hi"

    @Controller("greet")
    class Ctrl:
        def __init__(self, svc: Svc): self.svc = svc

        @vcmd
        def hello(self): return self.svc.hi()

    @Module(controllers=[Ctrl], providers=[Svc])
    class Mod:
        pass

    app = App(root_module=Mod)

    @app.middleware
    def audit(cmd, args):
        log.append(cmd)

    resp = app.ipc.handle({"id": "1", "command": "greet.hello", "args": {}})
    assert resp["ok"] is True
    assert log == ["greet.hello"]
