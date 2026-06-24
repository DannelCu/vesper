import asyncio

import pytest

from vesper import App, Controller, Injectable, Module, command
from vesper.core.ipc import IPC
from vesper.core.module import Container
from vesper.core.registry import CommandRegistry


# ── Decorator unit tests ──────────────────────────────────────────────────────


def test_injectable_sets_marker():
    @Injectable()
    class MyService:
        pass

    assert getattr(MyService, "__vesper_injectable__", False) is True


def test_controller_sets_prefix():
    @Controller("users")
    class UsersController:
        pass

    assert UsersController.__vesper_controller__ == {"prefix": "users", "guards": []}


def test_controller_empty_prefix():
    @Controller()
    class Ctrl:
        pass

    assert Ctrl.__vesper_controller__ == {"prefix": "", "guards": []}


def test_command_bare_uses_fn_name():
    @command
    def find_all(self):
        pass

    assert find_all.__vesper_command__ == {"name": "find_all"}


def test_command_string_arg():
    @command("getOne")
    def get_one(self):
        pass

    assert get_one.__vesper_command__ == {"name": "getOne"}


def test_command_name_kwarg():
    @command(name="getOne")
    def get_one(self):
        pass

    assert get_one.__vesper_command__ == {"name": "getOne"}


def test_command_empty_parens_uses_fn_name():
    @command()
    def list_items(self):
        pass

    assert list_items.__vesper_command__ == {"name": "list_items"}


def test_command_duplicate_name_raises():
    with pytest.raises(ValueError):

        @command("name", name="other")
        def fn():
            pass


def test_command_invalid_target_raises():
    with pytest.raises(TypeError):
        command(42)


# ── Container unit tests ──────────────────────────────────────────────────────


def test_container_resolves_no_deps():
    @Injectable()
    class SimpleService:
        def greet(self):
            return "hello"

    c = Container([SimpleService])
    svc = c.resolve(SimpleService)
    assert svc.greet() == "hello"


def test_container_resolves_with_deps():
    @Injectable()
    class Repo:
        def find(self):
            return [1, 2, 3]

    @Injectable()
    class Service:
        def __init__(self, repo: Repo):
            self.repo = repo

        def all(self):
            return self.repo.find()

    c = Container([Repo, Service])
    svc = c.resolve(Service)
    assert svc.all() == [1, 2, 3]


def test_container_returns_singleton():
    @Injectable()
    class Counter:
        def __init__(self):
            self.n = 0

    c = Container([Counter])
    a = c.resolve(Counter)
    b = c.resolve(Counter)
    a.n = 99
    assert b.n == 99


# ── Module integration tests ──────────────────────────────────────────────────


def test_register_module_registers_commands():
    @Injectable()
    class Svc:
        def greet(self):
            return "hi"

    @Controller("hello")
    class Ctrl:
        def __init__(self, svc: Svc):
            self.svc = svc

        @command
        def greet(self):
            return self.svc.greet()

    @Module(controllers=[Ctrl], providers=[Svc])
    class MyModule:
        pass

    app = App()
    app.register_module(MyModule)
    fn = app.registry.get("hello.greet")
    assert fn() == "hi"


def test_register_module_namespaces_with_prefix():
    @Controller("items")
    class Ctrl:
        @command
        def list(self):
            return []

        @command("getById")
        def get_by_id(self):
            return {}

    @Module(controllers=[Ctrl])
    class M:
        pass

    app = App()
    app.register_module(M)
    assert app.registry.get("items.list") is not None
    assert app.registry.get("items.getById") is not None


def test_register_module_no_prefix():
    @Controller()
    class Ctrl:
        @command
        def ping(self):
            return "pong"

    @Module(controllers=[Ctrl])
    class M:
        pass

    app = App()
    app.register_module(M)
    assert app.registry.get("ping")() == "pong"


def test_register_module_not_a_module_raises():
    class NotAModule:
        pass

    app = App()
    with pytest.raises(TypeError):
        app.register_module(NotAModule)


def test_register_module_controller_not_decorated_raises():
    class BareController:
        @command
        def do(self):
            pass

    @Module(controllers=[BareController])
    class M:
        pass

    app = App()
    with pytest.raises(TypeError):
        app.register_module(M)


def test_register_module_ipc_end_to_end():
    @Injectable()
    class MathService:
        def add(self, a: int, b: int) -> int:
            return a + b

    @Controller("math")
    class MathController:
        def __init__(self, svc: MathService):
            self.svc = svc

        @command
        def add(self, a: int, b: int):
            return self.svc.add(a, b)

    @Module(controllers=[MathController], providers=[MathService])
    class MathModule:
        pass

    app = App()
    app.register_module(MathModule)

    resp = app.ipc.handle({"id": "1", "command": "math.add", "args": {"a": 3, "b": 4}})
    assert resp["ok"] is True
    assert resp["result"] == 7


def test_register_module_async_command():
    @Controller("async")
    class AsyncCtrl:
        @command
        async def fetch(self):
            await asyncio.sleep(0)
            return "async result"

    @Module(controllers=[AsyncCtrl])
    class M:
        pass

    app = App()
    app.register_module(M)

    resp = app.ipc.handle({"id": "1", "command": "async.fetch", "args": {}})
    assert resp["ok"] is True
    assert resp["result"] == "async result"


def test_register_module_imports():
    @Controller("a")
    class CtrlA:
        @command
        def hello(self):
            return "from A"

    @Module(controllers=[CtrlA])
    class ModuleA:
        pass

    @Controller("b")
    class CtrlB:
        @command
        def world(self):
            return "from B"

    @Module(controllers=[CtrlB], imports=[ModuleA])
    class ModuleB:
        pass

    app = App()
    app.register_module(ModuleB)

    # Both modules' commands should be registered
    assert app.registry.get("a.hello")() == "from A"
    assert app.registry.get("b.world")() == "from B"
