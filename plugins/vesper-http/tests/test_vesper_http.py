"""Tests for the vesper-http plugin."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("httpx", reason="httpx not installed")

from vesper import App, Controller, Injectable, Module, command
from vesper.core.module import Container
from vesper_http import HttpClient, HttpPlugin, Plugin


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_response(
    status_code: int = 200,
    json_data: dict | None = None,
    text: str = "",
    content_type: str | None = None,
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    if json_data is not None:
        resp.text = json.dumps(json_data)
        resp.json.return_value = json_data
        ct = content_type or "application/json"
    else:
        resp.text = text
        resp.json.side_effect = ValueError("no json")
        ct = content_type or "text/plain"
    resp.headers = {"content-type": ct}
    return resp


def _patch_request(resp: MagicMock):
    return patch("httpx.Client.request", return_value=resp)


# ── Plugin basics ─────────────────────────────────────────────────────────────


def test_plugin_alias_is_http_plugin():
    assert Plugin is HttpPlugin


def test_http_plugin_is_vesper_plugin():
    from vesper import VesperPlugin
    assert issubclass(HttpPlugin, VesperPlugin)


def test_sdk_path_returns_path():
    p = HttpPlugin.sdk_path()
    assert p is not None
    assert isinstance(p, Path)


def test_sdk_path_points_to_js_file():
    assert HttpPlugin.sdk_path().name == "vesper-http.js"


def test_sdk_js_file_exists():
    assert HttpPlugin.sdk_path().is_file()


def test_sdk_js_contains_vesper_http():
    content = HttpPlugin.sdk_path().read_text(encoding="utf-8")
    assert "vesper.http" in content


def test_sdk_js_exposes_all_methods():
    content = HttpPlugin.sdk_path().read_text(encoding="utf-8")
    for method in ("get", "post", "put", "patch", "delete"):
        assert method in content


# ── DI registration ───────────────────────────────────────────────────────────


def test_plugin_registers_http_client_globally():
    app = App(plugins=[HttpPlugin()])
    assert HttpClient in Container._global


def test_global_http_client_is_http_client_instance():
    app = App(plugins=[HttpPlugin()])
    assert isinstance(Container._global[HttpClient], HttpClient)


def test_plugin_registers_ipc_commands():
    app = App(plugins=[HttpPlugin()])
    for cmd in ("http:get", "http:post", "http:put", "http:patch", "http:delete"):
        assert cmd in app.registry._commands


def test_http_client_injected_into_service():
    @Injectable()
    class MyService:
        def __init__(self, http: HttpClient):
            self.http = http

    app = App(plugins=[HttpPlugin()])
    container = Container([MyService])
    service = container.resolve(MyService)
    assert isinstance(service.http, HttpClient)


# ── HttpClient.get ────────────────────────────────────────────────────────────


def test_client_get_returns_response_dict():
    client = HttpClient()
    with _patch_request(_mock_response(200, {"id": 1})):
        resp = client.get("https://api.example.com/users/1")
    assert resp["status"] == 200
    assert resp["ok"] is True
    assert resp["json"] == {"id": 1}


def test_client_get_sets_ok_false_on_4xx():
    client = HttpClient()
    with _patch_request(_mock_response(404, text="Not Found")):
        resp = client.get("https://api.example.com/missing")
    assert resp["status"] == 404
    assert resp["ok"] is False


def test_client_get_sets_ok_false_on_5xx():
    client = HttpClient()
    with _patch_request(_mock_response(500, text="Server Error")):
        resp = client.get("https://api.example.com/error")
    assert resp["ok"] is False


def test_client_get_body_contains_raw_text():
    client = HttpClient()
    with _patch_request(_mock_response(200, text="hello world", content_type="text/plain")):
        resp = client.get("https://example.com")
    assert resp["body"] == "hello world"


def test_client_get_json_is_none_for_non_json():
    client = HttpClient()
    with _patch_request(_mock_response(200, text="plain text", content_type="text/plain")):
        resp = client.get("https://example.com")
    assert resp["json"] is None


def test_client_get_headers_present_in_response():
    client = HttpClient()
    with _patch_request(_mock_response(200, json_data={})):
        resp = client.get("https://example.com")
    assert "content-type" in resp["headers"]


def test_client_get_passes_params():
    client = HttpClient()
    mock = _mock_response(200, {})
    with patch("httpx.Client.request", return_value=mock) as m:
        client.get("https://api.example.com/search", params={"q": "test"})
    m.assert_called_once_with("GET", "https://api.example.com/search", params={"q": "test"})


def test_client_get_passes_custom_headers():
    client = HttpClient()
    mock = _mock_response(200, {})
    with patch("httpx.Client.request", return_value=mock) as m:
        client.get("https://api.example.com", headers={"X-Token": "abc"})
    call_kwargs = m.call_args[1]
    assert call_kwargs["headers"] == {"X-Token": "abc"}


def test_client_get_passes_timeout():
    client = HttpClient()
    mock = _mock_response(200, {})
    with patch("httpx.Client.request", return_value=mock) as m:
        client.get("https://api.example.com", timeout=5.0)
    assert m.call_args[1]["timeout"] == 5.0


def test_client_get_omits_none_kwargs():
    client = HttpClient()
    mock = _mock_response(200, {})
    with patch("httpx.Client.request", return_value=mock) as m:
        client.get("https://api.example.com")
    call_kwargs = m.call_args[1]
    assert "params" not in call_kwargs
    assert "timeout" not in call_kwargs


# ── HttpClient.post ───────────────────────────────────────────────────────────


def test_client_post_sends_json_body():
    client = HttpClient()
    mock = _mock_response(201, {"id": 42})
    with patch("httpx.Client.request", return_value=mock) as m:
        resp = client.post("https://api.example.com/users", json={"name": "Alice"})
    m.assert_called_once_with("POST", "https://api.example.com/users", json={"name": "Alice"})
    assert resp["status"] == 201
    assert resp["json"]["id"] == 42


def test_client_post_sends_form_data():
    client = HttpClient()
    mock = _mock_response(200, {})
    with patch("httpx.Client.request", return_value=mock) as m:
        client.post("https://example.com/form", data={"field": "value"})
    call_kwargs = m.call_args[1]
    assert call_kwargs["data"] == {"field": "value"}


# ── HttpClient.put / patch / delete ──────────────────────────────────────────


def test_client_put_uses_put_method():
    client = HttpClient()
    mock = _mock_response(200, {"updated": True})
    with patch("httpx.Client.request", return_value=mock) as m:
        client.put("https://api.example.com/users/1", json={"name": "Bob"})
    assert m.call_args[0][0] == "PUT"


def test_client_patch_uses_patch_method():
    client = HttpClient()
    mock = _mock_response(200, {})
    with patch("httpx.Client.request", return_value=mock) as m:
        client.patch("https://api.example.com/users/1", json={"name": "Bob"})
    assert m.call_args[0][0] == "PATCH"


def test_client_delete_uses_delete_method():
    client = HttpClient()
    mock = _mock_response(204, text="")
    with patch("httpx.Client.request", return_value=mock) as m:
        resp = client.delete("https://api.example.com/users/1")
    assert m.call_args[0][0] == "DELETE"
    assert resp["status"] == 204


# ── HttpPlugin configuration ──────────────────────────────────────────────────


def test_plugin_default_timeout_is_30():
    plugin = HttpPlugin()
    assert plugin._timeout == 30.0


def test_plugin_custom_base_url():
    plugin = HttpPlugin(base_url="https://api.example.com")
    assert plugin._base_url == "https://api.example.com"


def test_plugin_custom_headers():
    plugin = HttpPlugin(headers={"Authorization": "Bearer token"})
    assert plugin._headers == {"Authorization": "Bearer token"}


def test_plugin_custom_timeout():
    plugin = HttpPlugin(timeout=10.0)
    assert plugin._timeout == 10.0


# ── IPC commands ──────────────────────────────────────────────────────────────


def test_ipc_get_command():
    app = App(plugins=[HttpPlugin()])
    with _patch_request(_mock_response(200, {"hello": "world"})):
        resp = app.ipc.handle({
            "id": "1",
            "command": "http:get",
            "args": {"url": "https://api.example.com/data"},
        })
    assert resp["ok"] is True
    assert resp["result"]["status"] == 200
    assert resp["result"]["json"] == {"hello": "world"}


def test_ipc_post_command():
    app = App(plugins=[HttpPlugin()])
    with _patch_request(_mock_response(201, {"id": 1})):
        resp = app.ipc.handle({
            "id": "1",
            "command": "http:post",
            "args": {"url": "https://api.example.com/users", "json": {"name": "Alice"}},
        })
    assert resp["ok"] is True
    assert resp["result"]["status"] == 201


def test_ipc_put_command():
    app = App(plugins=[HttpPlugin()])
    with _patch_request(_mock_response(200, {})):
        resp = app.ipc.handle({
            "id": "1",
            "command": "http:put",
            "args": {"url": "https://api.example.com/users/1", "json": {"name": "Bob"}},
        })
    assert resp["ok"] is True


def test_ipc_patch_command():
    app = App(plugins=[HttpPlugin()])
    with _patch_request(_mock_response(200, {})):
        resp = app.ipc.handle({
            "id": "1",
            "command": "http:patch",
            "args": {"url": "https://api.example.com/users/1"},
        })
    assert resp["ok"] is True


def test_ipc_delete_command():
    app = App(plugins=[HttpPlugin()])
    with _patch_request(_mock_response(204, text="")):
        resp = app.ipc.handle({
            "id": "1",
            "command": "http:delete",
            "args": {"url": "https://api.example.com/users/1"},
        })
    assert resp["ok"] is True
    assert resp["result"]["status"] == 204


def test_ipc_get_missing_url_returns_validation_error():
    app = App(plugins=[HttpPlugin()])
    resp = app.ipc.handle({"id": "1", "command": "http:get", "args": {}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValidationError"


def test_ipc_error_response_on_network_failure():
    app = App(plugins=[HttpPlugin()])
    import httpx
    with patch("httpx.Client.request", side_effect=httpx.ConnectError("refused")):
        resp = app.ipc.handle({
            "id": "1",
            "command": "http:get",
            "args": {"url": "https://unreachable.example.com"},
        })
    assert resp["ok"] is False


# ── DI integration with module system ────────────────────────────────────────


@Injectable()
class ApiService:
    def __init__(self, http: HttpClient):
        self.http = http

    def fetch(self, url: str) -> dict:
        return self.http.get(url)


@Controller("api")
class ApiController:
    def __init__(self, service: ApiService):
        self.service = service

    @command
    def fetch(self, url: str) -> dict:
        return self.service.fetch(url)


@Module(controllers=[ApiController], providers=[ApiService])
class ApiModule:
    pass


def test_di_service_receives_http_client():
    app = App(plugins=[HttpPlugin()], root_module=ApiModule)
    container = Container([ApiService])
    service = container.resolve(ApiService)
    assert isinstance(service.http, HttpClient)


def test_di_service_command_callable_via_ipc():
    app = App(plugins=[HttpPlugin()], root_module=ApiModule)
    with _patch_request(_mock_response(200, {"value": 42})):
        resp = app.ipc.handle({
            "id": "1",
            "command": "api.fetch",
            "args": {"url": "https://api.example.com/value"},
        })
    assert resp["ok"] is True
    assert resp["result"]["json"] == {"value": 42}


# ── Public API exports ────────────────────────────────────────────────────────


def test_http_client_importable():
    from vesper_http import HttpClient as HC
    assert HC is HttpClient


def test_http_plugin_importable():
    from vesper_http import HttpPlugin as HP
    assert HP is HttpPlugin


def test_plugin_alias_exported():
    from vesper_http import Plugin as P
    assert P is HttpPlugin
