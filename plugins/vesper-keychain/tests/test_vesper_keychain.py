"""Tests for the vesper-keychain plugin."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("keyring", reason="keyring not installed")

from vesper import App, Controller, Injectable, Module, command
from vesper.core.module import Container
from vesper_keychain import Keychain, KeychainPlugin, Plugin


# ── Plugin basics ─────────────────────────────────────────────────────────────


def test_plugin_alias_is_keychain_plugin():
    assert Plugin is KeychainPlugin


def test_keychain_plugin_is_vesper_plugin():
    from vesper import VesperPlugin
    assert issubclass(KeychainPlugin, VesperPlugin)


def test_sdk_path_returns_path():
    p = KeychainPlugin.sdk_path()
    assert p is not None
    assert isinstance(p, Path)


def test_sdk_path_points_to_js_file():
    assert KeychainPlugin.sdk_path().name == "vesper-keychain.js"


def test_sdk_js_file_exists():
    assert KeychainPlugin.sdk_path().is_file()


def test_sdk_js_contains_vesper_keychain():
    content = KeychainPlugin.sdk_path().read_text(encoding="utf-8")
    assert "vesper.keychain" in content


def test_sdk_js_exposes_all_methods():
    content = KeychainPlugin.sdk_path().read_text(encoding="utf-8")
    for method in ("get", "set", "delete", "has"):
        assert method in content


def test_plugin_default_service():
    plugin = KeychainPlugin()
    assert plugin._service == "vesper-app"


def test_plugin_custom_service():
    plugin = KeychainPlugin(service="my-app")
    assert plugin._service == "my-app"


# ── DI registration ───────────────────────────────────────────────────────────


def test_plugin_registers_keychain_globally():
    App(plugins=[KeychainPlugin(service="test-app")])
    assert Keychain in Container._global


def test_global_keychain_is_keychain_instance():
    App(plugins=[KeychainPlugin(service="test-app")])
    assert isinstance(Container._global[Keychain], Keychain)


def test_plugin_registers_ipc_commands():
    app = App(plugins=[KeychainPlugin(service="test-app")])
    for cmd in ("keychain:get", "keychain:set", "keychain:delete", "keychain:has"):
        assert cmd in app.registry._commands


def test_keychain_injected_into_service():
    @Injectable()
    class MyService:
        def __init__(self, keychain: Keychain):
            self.keychain = keychain

    App(plugins=[KeychainPlugin(service="test-app")])
    container = Container([MyService])
    service = container.resolve(MyService)
    assert isinstance(service.keychain, Keychain)


# ── Keychain.get / set ────────────────────────────────────────────────────────


def test_set_and_get_value():
    kc = Keychain(service="test")
    kc.set("token", "abc123")
    assert kc.get("token") == "abc123"


def test_get_missing_key_returns_none():
    kc = Keychain(service="test")
    assert kc.get("nonexistent") is None


def test_set_overwrites_existing_value():
    kc = Keychain(service="test")
    kc.set("key", "first")
    kc.set("key", "second")
    assert kc.get("key") == "second"


def test_different_keys_are_independent():
    kc = Keychain(service="test")
    kc.set("a", "value-a")
    kc.set("b", "value-b")
    assert kc.get("a") == "value-a"
    assert kc.get("b") == "value-b"


def test_different_services_are_isolated():
    kc1 = Keychain(service="app-1")
    kc2 = Keychain(service="app-2")
    kc1.set("token", "for-app-1")
    assert kc2.get("token") is None


def test_value_can_contain_special_characters():
    kc = Keychain(service="test")
    kc.set("key", "p@$$w0rd!#%&*()=+")
    assert kc.get("key") == "p@$$w0rd!#%&*()=+"


def test_value_can_contain_unicode():
    kc = Keychain(service="test")
    kc.set("key", "contraseña-こんにちは")
    assert kc.get("key") == "contraseña-こんにちは"


def test_value_can_be_long_string():
    kc = Keychain(service="test")
    long_value = "x" * 10_000
    kc.set("key", long_value)
    assert kc.get("key") == long_value


# ── Keychain.delete ───────────────────────────────────────────────────────────


def test_delete_removes_key():
    kc = Keychain(service="test")
    kc.set("token", "secret")
    kc.delete("token")
    assert kc.get("token") is None


def test_delete_nonexistent_key_is_noop():
    kc = Keychain(service="test")
    kc.delete("ghost")  # must not raise


def test_delete_does_not_affect_other_keys():
    kc = Keychain(service="test")
    kc.set("a", "1")
    kc.set("b", "2")
    kc.delete("a")
    assert kc.get("b") == "2"


# ── Keychain.has ──────────────────────────────────────────────────────────────


def test_has_true_when_key_exists():
    kc = Keychain(service="test")
    kc.set("token", "secret")
    assert kc.has("token") is True


def test_has_false_when_key_missing():
    kc = Keychain(service="test")
    assert kc.has("missing") is False


def test_has_false_after_delete():
    kc = Keychain(service="test")
    kc.set("key", "val")
    kc.delete("key")
    assert kc.has("key") is False


# ── IPC commands ──────────────────────────────────────────────────────────────


def _app():
    return App(plugins=[KeychainPlugin(service="ipc-test")])


def test_ipc_set_and_get():
    app = _app()
    app.ipc.handle({"id": "1", "command": "keychain:set",
                    "args": {"key": "token", "value": "secret"}})
    resp = app.ipc.handle({"id": "2", "command": "keychain:get",
                           "args": {"key": "token"}})
    assert resp["ok"] is True
    assert resp["result"] == "secret"


def test_ipc_get_missing_returns_none():
    app = _app()
    resp = app.ipc.handle({"id": "1", "command": "keychain:get",
                           "args": {"key": "missing"}})
    assert resp["ok"] is True
    assert resp["result"] is None


def test_ipc_has_true():
    app = _app()
    app.ipc.handle({"id": "1", "command": "keychain:set",
                    "args": {"key": "k", "value": "v"}})
    resp = app.ipc.handle({"id": "2", "command": "keychain:has",
                           "args": {"key": "k"}})
    assert resp["result"] is True


def test_ipc_has_false():
    app = _app()
    resp = app.ipc.handle({"id": "1", "command": "keychain:has",
                           "args": {"key": "absent"}})
    assert resp["result"] is False


def test_ipc_delete():
    app = _app()
    app.ipc.handle({"id": "1", "command": "keychain:set",
                    "args": {"key": "k", "value": "v"}})
    app.ipc.handle({"id": "2", "command": "keychain:delete",
                    "args": {"key": "k"}})
    resp = app.ipc.handle({"id": "3", "command": "keychain:get",
                           "args": {"key": "k"}})
    assert resp["result"] is None


def test_ipc_delete_nonexistent_is_ok():
    app = _app()
    resp = app.ipc.handle({"id": "1", "command": "keychain:delete",
                           "args": {"key": "ghost"}})
    assert resp["ok"] is True


def test_ipc_set_missing_key_arg():
    app = _app()
    resp = app.ipc.handle({"id": "1", "command": "keychain:set", "args": {}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValidationError"


def test_ipc_set_missing_value_arg():
    app = _app()
    resp = app.ipc.handle({"id": "1", "command": "keychain:set",
                           "args": {"key": "k"}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValidationError"


def test_ipc_get_missing_key_arg():
    app = _app()
    resp = app.ipc.handle({"id": "1", "command": "keychain:get", "args": {}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValidationError"


# ── DI integration with module system ────────────────────────────────────────


@Injectable()
class TokenService:
    def __init__(self, keychain: Keychain):
        self.keychain = keychain

    def save(self, token: str) -> None:
        self.keychain.set("api_token", token)

    def load(self) -> str | None:
        return self.keychain.get("api_token")

    def revoke(self) -> None:
        self.keychain.delete("api_token")


@Controller("auth")
class AuthController:
    def __init__(self, service: TokenService):
        self.service = service

    @command
    def save_token(self, token: str) -> None:
        self.service.save(token)

    @command
    def get_token(self) -> str | None:
        return self.service.load()

    @command
    def revoke_token(self) -> None:
        self.service.revoke()


@Module(controllers=[AuthController], providers=[TokenService])
class AuthModule:
    pass


def test_di_service_receives_keychain():
    app = App(plugins=[KeychainPlugin(service="di-test")], root_module=AuthModule)
    container = Container([TokenService])
    service = container.resolve(TokenService)
    assert isinstance(service.keychain, Keychain)


def test_di_save_and_load_token_via_ipc():
    app = App(plugins=[KeychainPlugin(service="di-test")], root_module=AuthModule)

    app.ipc.handle({"id": "1", "command": "auth.save_token",
                    "args": {"token": "sk-abc123"}})
    resp = app.ipc.handle({"id": "2", "command": "auth.get_token", "args": {}})

    assert resp["ok"] is True
    assert resp["result"] == "sk-abc123"


def test_di_revoke_token_via_ipc():
    app = App(plugins=[KeychainPlugin(service="di-test")], root_module=AuthModule)

    app.ipc.handle({"id": "1", "command": "auth.save_token",
                    "args": {"token": "sk-abc123"}})
    app.ipc.handle({"id": "2", "command": "auth.revoke_token", "args": {}})
    resp = app.ipc.handle({"id": "3", "command": "auth.get_token", "args": {}})

    assert resp["result"] is None


# ── Public API exports ────────────────────────────────────────────────────────


def test_keychain_importable():
    from vesper_keychain import Keychain as KC
    assert KC is Keychain


def test_keychain_plugin_importable():
    from vesper_keychain import KeychainPlugin as KP
    assert KP is KeychainPlugin


def test_plugin_alias_exported():
    from vesper_keychain import Plugin as P
    assert P is KeychainPlugin
