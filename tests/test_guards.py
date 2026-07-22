"""Tests for M2.2 — command-level guards."""
import asyncio

import pytest

from vesper import App, Controller, ForbiddenError, Injectable, Module, command, guard
from vesper.core.guard import guard as guard_fn_direct
from vesper.core.ipc import IPC
from vesper.core.registry import CommandRegistry


# ── guard() decorator ────────────────────────────────────────────────────────


def test_guard_attaches_attribute():
    def allow(cmd, args): return True

    @guard(allow)
    def fn(): pass

    assert fn.__vesper_guards__ == [allow]


def test_guard_returns_original_function():
    def allow(cmd, args): return True

    def fn(): return 42

    result = guard(allow)(fn)
    assert result is fn
    assert result() == 42


def test_guard_multiple_fns_in_single_call():
    def g1(cmd, args): return True
    def g2(cmd, args): return True

    @guard(g1, g2)
    def fn(): pass

    assert fn.__vesper_guards__ == [g1, g2]


def test_guard_stacked_outermost_runs_first():
    def g1(cmd, args): return True
    def g2(cmd, args): return True

    # decorators apply bottom-up, so @guard(g1) is outermost
    @guard(g1)
    @guard(g2)
    def fn(): pass

    assert fn.__vesper_guards__ == [g1, g2]


def test_guard_no_attribute_without_decorator():
    def fn(): pass
    assert not hasattr(fn, "__vesper_guards__")


# ── registry stores guards ────────────────────────────────────────────────────


def test_registry_stores_guards():
    registry = CommandRegistry()
    g = lambda cmd, args: True
    registry.register(lambda: None, name="cmd", guards=[g])
    assert registry._guards["cmd"] == [g]


def test_registry_no_guards_key_by_default():
    registry = CommandRegistry()
    registry.register(lambda: None, name="cmd")
    assert "cmd" not in registry._guards


def test_registry_empty_guards_not_stored():
    registry = CommandRegistry()
    registry.register(lambda: None, name="cmd", guards=[])
    assert "cmd" not in registry._guards


# ── @app.command picks up guards ──────────────────────────────────────────────


def test_app_command_registers_guard():
    app = App()
    g = lambda cmd, args: True

    @app.command
    @guard(g)
    def greet(): return "hi"

    assert app.registry._guards.get("greet") == [g]


def test_app_command_without_guard_no_entry():
    app = App()

    @app.command
    def greet(): return "hi"

    assert "greet" not in app.registry._guards


# ── IPC executes guards before middleware ─────────────────────────────────────



# Async tests build a real event loop and its thread. Tracking every IPC the
# factory hands out means no test in this file can forget to release one — the
# leak that used to surface hundreds of tests later as EMFILE.
_created: list = []


@pytest.fixture(autouse=True)
def _close_created_ipcs():
    yield
    while _created:
        _created.pop().close()

def _make_ipc(guards_map=None, middleware=None):
    registry = CommandRegistry()
    if guards_map:
        for name, gs in guards_map.items():
            registry._guards[name] = gs
    ipc = IPC(registry, middleware=middleware or [])
    _created.append(ipc)
    return ipc, registry


def test_guard_true_allows_command():
    ipc, registry = _make_ipc({"ping": [lambda cmd, args: True]})
    registry.register(lambda: "pong", name="ping")
    resp = ipc.handle({"id": "1", "command": "ping", "args": {}})
    assert resp["ok"] is True
    assert resp["result"] == "pong"


def test_guard_false_returns_forbidden():
    ipc, registry = _make_ipc({"secret": [lambda cmd, args: False]})
    registry.register(lambda: "data", name="secret")
    resp = ipc.handle({"id": "1", "command": "secret", "args": {}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ForbiddenError"


def test_guard_false_command_does_not_run():
    called = []

    def cmd():
        called.append(True)
        return "x"

    ipc, registry = _make_ipc({"cmd": [lambda c, a: False]})
    registry.register(cmd)
    ipc.handle({"id": "1", "command": "cmd", "args": {}})
    assert called == []


def test_guard_raises_exception_propagates():
    def strict(cmd, args):
        raise PermissionError("not allowed")

    ipc, registry = _make_ipc({"cmd": [strict]})
    registry.register(lambda: None, name="cmd")
    resp = ipc.handle({"id": "1", "command": "cmd", "args": {}})
    assert resp["ok"] is False
    # A guard blowing up is a bug in the guard, not a denial, so it is reported as
    # GuardError with the original class kept as the cause.
    assert resp["error"]["type"] == "GuardError"
    assert resp["error"]["cause"] == "PermissionError"
    assert "not allowed" in resp["error"]["message"]


def test_guard_receives_command_name_and_args():
    received = {}

    def capture(cmd, args):
        received["cmd"] = cmd
        received["args"] = args
        return True

    ipc, registry = _make_ipc({"echo": [capture]})
    registry.register(lambda x: x, name="echo")
    ipc.handle({"id": "1", "command": "echo", "args": {"x": 99}})
    assert received["cmd"] == "echo"
    assert received["args"] == {"x": 99}


def test_multiple_guards_all_pass():
    log = []
    ipc, registry = _make_ipc({"cmd": [
        lambda c, a: log.append(1) or True,
        lambda c, a: log.append(2) or True,
    ]})
    registry.register(lambda: None, name="cmd")
    resp = ipc.handle({"id": "1", "command": "cmd", "args": {}})
    assert resp["ok"] is True
    assert log == [1, 2]


def test_multiple_guards_first_fails_stops_chain():
    log = []

    def g1(cmd, args):
        log.append(1)
        return False

    def g2(cmd, args):
        log.append(2)
        return True

    ipc, registry = _make_ipc({"cmd": [g1, g2]})
    registry.register(lambda: None, name="cmd")
    ipc.handle({"id": "1", "command": "cmd", "args": {}})
    assert log == [1]


def test_guard_none_return_treated_as_allow():
    ipc, registry = _make_ipc({"cmd": [lambda c, a: None]})
    registry.register(lambda: "ok", name="cmd")
    resp = ipc.handle({"id": "1", "command": "cmd", "args": {}})
    assert resp["ok"] is True


# ── Guards run before middleware ──────────────────────────────────────────────


def test_guard_runs_before_middleware():
    log = []

    def g(cmd, args):
        log.append("guard")
        return True

    def mw(cmd, args):
        log.append("middleware")

    ipc, registry = _make_ipc({"cmd": [g]}, middleware=[mw])
    registry.register(lambda: None, name="cmd")
    ipc.handle({"id": "1", "command": "cmd", "args": {}})
    assert log == ["guard", "middleware"]


def test_guard_rejected_middleware_does_not_run():
    log = []

    def mw(cmd, args):
        log.append("middleware")

    ipc, registry = _make_ipc({"cmd": [lambda c, a: False]}, middleware=[mw])
    registry.register(lambda: None, name="cmd")
    ipc.handle({"id": "1", "command": "cmd", "args": {}})
    assert log == []


# ── Async guards ──────────────────────────────────────────────────────────────


def test_async_guard_true_allows():
    async def async_allow(cmd, args):
        await asyncio.sleep(0)
        return True

    ipc, registry = _make_ipc({"ping": [async_allow]})
    registry.register(lambda: "pong", name="ping")
    resp = ipc.handle({"id": "1", "command": "ping", "args": {}})
    assert resp["ok"] is True


def test_async_guard_false_returns_forbidden():
    async def async_deny(cmd, args):
        await asyncio.sleep(0)
        return False

    ipc, registry = _make_ipc({"secret": [async_deny]})
    registry.register(lambda: "data", name="secret")
    resp = ipc.handle({"id": "1", "command": "secret", "args": {}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ForbiddenError"


def test_async_guard_raises_propagates():
    async def async_strict(cmd, args):
        raise PermissionError("async blocked")

    ipc, registry = _make_ipc({"cmd": [async_strict]})
    registry.register(lambda: None, name="cmd")
    resp = ipc.handle({"id": "1", "command": "cmd", "args": {}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "GuardError"
    assert resp["error"]["cause"] == "PermissionError"


# ── Controller-level guards ───────────────────────────────────────────────────


def test_controller_guard_applies_to_all_commands():
    log = []

    def ctrl_guard(cmd, args):
        log.append(cmd)
        return True

    @Injectable()
    class Svc:
        pass

    @Controller("api", guards=[ctrl_guard])
    class Ctrl:
        @command
        def one(self): return 1

        @command
        def two(self): return 2

    @Module(controllers=[Ctrl], providers=[Svc])
    class Mod:
        pass

    app = App(root_module=Mod)
    app.ipc.handle({"id": "1", "command": "api.one", "args": {}})
    app.ipc.handle({"id": "2", "command": "api.two", "args": {}})
    assert "api.one" in log
    assert "api.two" in log


def test_controller_guard_blocks_command():
    @Controller("admin", guards=[lambda cmd, args: False])
    class Ctrl:
        @command
        def secret(self): return "classified"

    @Module(controllers=[Ctrl])
    class Mod:
        pass

    app = App(root_module=Mod)
    resp = app.ipc.handle({"id": "1", "command": "admin.secret", "args": {}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ForbiddenError"


def test_controller_guard_runs_before_method_guard():
    log = []

    def ctrl_g(cmd, args):
        log.append("ctrl")
        return True

    def method_g(cmd, args):
        log.append("method")
        return True

    @Controller("svc", guards=[ctrl_g])
    class Ctrl:
        @command
        @guard(method_g)
        def action(self): return "ok"

    @Module(controllers=[Ctrl])
    class Mod:
        pass

    app = App(root_module=Mod)
    app.ipc.handle({"id": "1", "command": "svc.action", "args": {}})
    assert log == ["ctrl", "method"]


def test_controller_guard_fails_method_guard_does_not_run():
    log = []

    def method_g(cmd, args):
        log.append("method")
        return True

    @Controller("svc", guards=[lambda cmd, args: False])
    class Ctrl:
        @command
        @guard(method_g)
        def action(self): return "ok"

    @Module(controllers=[Ctrl])
    class Mod:
        pass

    app = App(root_module=Mod)
    app.ipc.handle({"id": "1", "command": "svc.action", "args": {}})
    assert log == []


# ── End-to-end with App ───────────────────────────────────────────────────────


def test_app_command_with_guard_end_to_end():
    app = App()
    session = {"logged_in": True}

    def is_logged_in(cmd, args):
        return session["logged_in"]

    @app.command
    @guard(is_logged_in)
    def profile(): return {"user": "alice"}

    resp = app.ipc.handle({"id": "1", "command": "profile", "args": {}})
    assert resp["ok"] is True

    session["logged_in"] = False
    resp = app.ipc.handle({"id": "2", "command": "profile", "args": {}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ForbiddenError"
