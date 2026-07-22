import asyncio

import pytest
from vesper.core.ipc import IPC
from vesper.core.registry import CommandRegistry



# Async tests build a real event loop and its thread. Tracking every IPC the
# factory hands out means no test in this file can forget to release one — the
# leak that used to surface hundreds of tests later as EMFILE.
_created: list = []


@pytest.fixture(autouse=True)
def _close_created_ipcs():
    yield
    while _created:
        _created.pop().close()

def _make_ipc(*, debug: bool = False) -> tuple[IPC, CommandRegistry]:
    registry = CommandRegistry()
    ipc = IPC(registry, debug=debug)
    _created.append(ipc)
    return ipc, registry


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


# ── the surface PyWebView publishes to JavaScript ─────────────────────────────


def _js_exposed_names(js_api) -> set[str]:
    """
    Reproduce PyWebView's introspection of the js_api object.

    It walks the object with dir(), recurses into public attributes and skips
    names starting with an underscore (webview/util.py, inject_pywebview). Every
    name it collects becomes callable from the page as window.pywebview.api.<name>.
    """
    import inspect

    seen: list[int] = []

    def walk(obj, base="", found=None):
        if id(obj) in seen:
            return found
        seen.append(id(obj))
        if found is None:
            found = set()
        for name in dir(obj):
            if name.startswith("_"):
                continue
            try:
                full = f"{base}.{name}" if base else name
                attr = getattr(obj, name)
                if inspect.ismethod(attr) or inspect.isfunction(attr):
                    found.add(full)
                elif inspect.isclass(attr) or (
                    isinstance(attr, object)
                    and not callable(attr)
                    and hasattr(attr, "__module__")
                ):
                    walk(attr, full, found)
            except Exception:
                continue
        return found

    return walk(js_api)


def _build_js_api(tmp_path):
    """The API object Window.create hands to webview.create_window."""
    from unittest.mock import MagicMock, patch

    from vesper import App
    from vesper.core import window as window_mod

    # create() checks the frontend exists before building the window.
    index = tmp_path / "index.html"
    index.write_text("<html></html>", encoding="utf-8")

    app = App(frontend=str(index))
    captured = {}

    def fake_create_window(**kwargs):
        captured["js_api"] = kwargs["js_api"]
        return MagicMock()

    with patch.object(window_mod.webview, "create_window", side_effect=fake_create_window):
        app.window.create(ipc_handler=app.ipc, config=app.config)

    return captured["js_api"], app


def test_only_invoke_is_exposed_to_javascript(tmp_path):
    """
    The page must reach Python through invoke() and nothing else.

    A public attribute on the API object is not private: PyWebView recurses into
    it and publishes what it finds. Holding the IPC under a public name exposed
    ipc.handle, ipc.close and ipc.registry.register to the frontend, which is a
    way around the invoke envelope that guards and middleware hang off.
    """
    js_api, _ = _build_js_api(tmp_path)
    assert _js_exposed_names(js_api) == {"invoke"}


def test_the_registry_is_not_reachable_from_javascript(tmp_path):
    """Specifically: registering a command from the page must not be possible."""
    js_api, _ = _build_js_api(tmp_path)
    exposed = _js_exposed_names(js_api)
    assert not any("registry" in name for name in exposed), exposed


def test_invoke_still_routes_through_the_ipc(tmp_path):
    """Making the reference private must not break the bridge it carries."""
    js_api, app = _build_js_api(tmp_path)

    app.registry.register(lambda: "ok", name="probe")
    response = js_api.invoke('{"id": "1", "command": "probe", "args": {}}')

    assert response["ok"] is True
    assert response["result"] == "ok"
