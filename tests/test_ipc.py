import asyncio

import pytest
from vesper.core.ipc import IPC
from vesper.core.registry import CommandRegistry


def _make_ipc(*, debug: bool = False) -> tuple[IPC, CommandRegistry]:
    registry = CommandRegistry()
    return IPC(registry, debug=debug), registry


def test_valid_command_returns_result():
    ipc, registry = _make_ipc()
    registry.register(lambda: "hello", name="greet")
    resp = ipc.handle({"id": "1", "command": "greet", "args": {}})
    assert resp == {"id": "1", "ok": True, "result": "hello"}


def test_command_receives_kwargs():
    ipc, registry = _make_ipc()
    registry.register(lambda name: f"hi {name}", name="greet")
    resp = ipc.handle({"id": "1", "command": "greet", "args": {"name": "World"}})
    assert resp["ok"] is True
    assert resp["result"] == "hi World"


def test_command_with_no_args_field():
    ipc, registry = _make_ipc()
    registry.register(lambda: 42, name="answer")
    resp = ipc.handle({"id": "2", "command": "answer"})
    assert resp["ok"] is True
    assert resp["result"] == 42


def test_unknown_command_returns_error():
    ipc, _ = _make_ipc()
    resp = ipc.handle({"id": "1", "command": "nope", "args": {}})
    assert resp["ok"] is False
    assert resp["id"] == "1"
    assert resp["error"]["type"] == "CommandNotFoundError"


def test_missing_id_returns_error():
    ipc, _ = _make_ipc()
    resp = ipc.handle({"command": "greet"})
    assert resp["ok"] is False
    assert resp["id"] is None
    assert resp["error"]["type"] == "InvalidRequestError"


def test_missing_command_returns_error():
    ipc, _ = _make_ipc()
    resp = ipc.handle({"id": "1"})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "InvalidRequestError"


def test_empty_command_returns_error():
    ipc, _ = _make_ipc()
    resp = ipc.handle({"id": "1", "command": ""})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "InvalidRequestError"


def test_non_dict_message_returns_error():
    ipc, _ = _make_ipc()
    resp = ipc.handle("not a dict")  # type: ignore
    assert resp["ok"] is False
    assert resp["id"] is None


def test_command_exception_returns_error():
    ipc, registry = _make_ipc()

    def boom():
        raise ValueError("something went wrong")

    registry.register(boom)
    resp = ipc.handle({"id": "1", "command": "boom", "args": {}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValueError"
    assert "something went wrong" in resp["error"]["message"]


def test_debug_mode_includes_traceback():
    ipc, registry = _make_ipc(debug=True)

    def boom():
        raise RuntimeError("oops")

    registry.register(boom)
    resp = ipc.handle({"id": "1", "command": "boom", "args": {}})
    assert "traceback" in resp["error"]
    assert "RuntimeError" in resp["error"]["traceback"]


def test_non_debug_mode_excludes_traceback():
    ipc, registry = _make_ipc(debug=False)

    def boom():
        raise RuntimeError("oops")

    registry.register(boom)
    resp = ipc.handle({"id": "1", "command": "boom", "args": {}})
    assert "traceback" not in resp["error"]


def test_response_preserves_request_id():
    ipc, registry = _make_ipc()
    registry.register(lambda: None, name="noop")
    resp = ipc.handle({"id": "req-abc-123", "command": "noop"})
    assert resp["id"] == "req-abc-123"


def test_args_as_non_dict_returns_validation_error():
    ipc, registry = _make_ipc()
    registry.register(lambda x: x * 2, name="double")
    resp = ipc.handle({"id": "1", "command": "double", "args": 5})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValidationError"


# ── Async commands ────────────────────────────────────────────────────────────


def test_async_command_returns_result():
    ipc, registry = _make_ipc()

    async def async_hello():
        return "async hello"

    registry.register(async_hello)
    resp = ipc.handle({"id": "1", "command": "async_hello", "args": {}})
    assert resp == {"id": "1", "ok": True, "result": "async hello"}


def test_async_command_receives_kwargs():
    ipc, registry = _make_ipc()

    async def async_greet(name: str):
        return f"hello {name}"

    registry.register(async_greet)
    resp = ipc.handle({"id": "1", "command": "async_greet", "args": {"name": "world"}})
    assert resp["ok"] is True
    assert resp["result"] == "hello world"


def test_async_command_can_await():
    ipc, registry = _make_ipc()

    async def waiter():
        await asyncio.sleep(0)
        return "waited"

    registry.register(waiter)
    resp = ipc.handle({"id": "1", "command": "waiter", "args": {}})
    assert resp["ok"] is True
    assert resp["result"] == "waited"


def test_async_command_exception_returns_error():
    ipc, registry = _make_ipc()

    async def async_fail():
        raise ValueError("async error")

    registry.register(async_fail)
    resp = ipc.handle({"id": "1", "command": "async_fail", "args": {}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValueError"
    assert "async error" in resp["error"]["message"]


def test_sync_and_async_commands_coexist():
    ipc, registry = _make_ipc()
    registry.register(lambda: "sync", name="sync_cmd")

    async def async_cmd():
        return "async"

    registry.register(async_cmd)
    r1 = ipc.handle({"id": "1", "command": "sync_cmd", "args": {}})
    r2 = ipc.handle({"id": "2", "command": "async_cmd", "args": {}})
    assert r1["result"] == "sync"
    assert r2["result"] == "async"


# ── Arg validation ────────────────────────────────────────────────────────────


def test_missing_required_arg_returns_validation_error():
    ipc, registry = _make_ipc()
    registry.register(lambda user_id: user_id, name="get_user")
    resp = ipc.handle({"id": "1", "command": "get_user", "args": {}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValidationError"
    assert "user_id" in resp["error"]["message"]


def test_unexpected_arg_returns_validation_error():
    ipc, registry = _make_ipc()
    registry.register(lambda: None, name="noop")
    resp = ipc.handle({"id": "1", "command": "noop", "args": {"x": 1}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValidationError"
    assert "x" in resp["error"]["message"]


def test_valid_args_pass_validation():
    ipc, registry = _make_ipc()
    registry.register(lambda name: name, name="echo")
    resp = ipc.handle({"id": "1", "command": "echo", "args": {"name": "hi"}})
    assert resp["ok"] is True
    assert resp["result"] == "hi"


def test_optional_arg_not_required():
    ipc, registry = _make_ipc()
    registry.register(lambda x=0: x + 1, name="inc")
    resp = ipc.handle({"id": "1", "command": "inc", "args": {}})
    assert resp["ok"] is True
    assert resp["result"] == 1


def test_var_kwargs_command_accepts_any_args():
    ipc, registry = _make_ipc()

    def flexible(**kwargs):
        return list(kwargs.keys())

    registry.register(flexible)
    resp = ipc.handle({"id": "1", "command": "flexible", "args": {"a": 1, "b": 2}})
    assert resp["ok"] is True


def test_non_dict_args_returns_validation_error():
    ipc, registry = _make_ipc()
    registry.register(lambda x: x * 2, name="double")
    resp = ipc.handle({"id": "1", "command": "double", "args": 5})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValidationError"
    assert "dict" in resp["error"]["message"].lower()
