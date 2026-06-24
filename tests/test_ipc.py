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


def test_args_as_non_dict_passed_positionally():
    ipc, registry = _make_ipc()
    registry.register(lambda x: x * 2, name="double")
    resp = ipc.handle({"id": "1", "command": "double", "args": 5})
    assert resp["ok"] is True
    assert resp["result"] == 10
