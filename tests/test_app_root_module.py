import pytest

from vesper import App, Controller, Injectable, Module, command
from vesper.core.ipc import IPC


# ── root_module parameter ─────────────────────────────────────────────────────


def test_app_root_module_none_is_default():
    app = App()
    user_cmds = {k for k in app.registry._commands if not k.startswith("vesper:")}
    assert user_cmds == set()


def test_app_root_module_registers_commands():
    @Controller("ping")
    class PingCtrl:
        @command
        def ping(self):
            return "pong"

    @Module(controllers=[PingCtrl])
    class PingModule:
        pass

    app = App(root_module=PingModule)
    fn = app.registry.get("ping.ping")
    assert fn() == "pong"


def test_app_root_module_ipc_end_to_end():
    @Injectable()
    class GreetService:
        def hello(self, name: str) -> str:
            return f"hello {name}"

    @Controller("greet")
    class GreetCtrl:
        def __init__(self, svc: GreetService):
            self.svc = svc

        @command
        def hello(self, name: str):
            return self.svc.hello(name)

    @Module(controllers=[GreetCtrl], providers=[GreetService])
    class GreetModule:
        pass

    app = App(root_module=GreetModule)
    resp = app.ipc.handle({"id": "1", "command": "greet.hello", "args": {"name": "world"}})
    assert resp["ok"] is True
    assert resp["result"] == "hello world"


def test_app_root_module_not_decorated_raises():
    class NotAModule:
        pass

    with pytest.raises(TypeError):
        App(root_module=NotAModule)


def test_app_root_module_with_imports():
    @Controller("a")
    class CtrlA:
        @command
        def ping(self):
            return "a"

    @Module(controllers=[CtrlA])
    class ModA:
        pass

    @Controller("b")
    class CtrlB:
        @command
        def ping(self):
            return "b"

    @Module(controllers=[CtrlB])
    class ModB:
        pass

    @Module(imports=[ModA, ModB])
    class AppModule:
        pass

    app = App(root_module=AppModule)
    assert app.registry.get("a.ping")() == "a"
    assert app.registry.get("b.ping")() == "b"


def test_app_root_module_and_manual_register_coexist():
    @Controller("mod")
    class ModCtrl:
        @command
        def one(self):
            return 1

    @Module(controllers=[ModCtrl])
    class Mod:
        pass

    @Controller("extra")
    class ExtraCtrl:
        @command
        def two(self):
            return 2

    @Module(controllers=[ExtraCtrl])
    class ExtraMod:
        pass

    app = App(root_module=Mod)
    app.register_module(ExtraMod)

    assert app.registry.get("mod.one")() == 1
    assert app.registry.get("extra.two")() == 2
