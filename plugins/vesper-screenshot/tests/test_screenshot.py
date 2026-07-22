"""Tests for vesper-screenshot — mocked mss, real scope and error contracts."""
from __future__ import annotations

import base64

import pytest

from vesper import App
from vesper_screenshot import ScreenshotPlugin


@pytest.fixture
def app():
    application = App(plugins=[ScreenshotPlugin()])
    yield application
    application.ipc.close()


def _capture(app, **args):
    return app.ipc.handle({"id": "1", "command": "vesper:screenshot:capture", "args": args})


def test_commands_registered(app):
    assert "vesper:screenshot:capture" in app.registry._commands
    assert "vesper:screenshot:monitors" in app.registry._commands


def test_capture_returns_png_data_url(app, mock_mss):
    resp = _capture(app)
    assert resp["ok"] is True
    assert resp["result"].startswith("data:image/png;base64,")
    decoded = base64.b64decode(resp["result"].split(",", 1)[1])
    assert decoded == b"\x89PNG fake bytes"
    # Default grabs the whole virtual screen (mss monitor 0).
    mock_mss._sct.grab.assert_called_once_with(mock_mss._sct.monitors[0])


def test_capture_specific_monitor(app, mock_mss):
    resp = _capture(app, monitor=2)
    assert resp["ok"] is True
    mock_mss._sct.grab.assert_called_once_with(mock_mss._sct.monitors[2])


def test_capture_region_overrides_monitor(app, mock_mss):
    region = {"left": 10, "top": 20, "width": 300, "height": 200}
    resp = _capture(app, monitor=1, region=region)
    assert resp["ok"] is True
    mock_mss._sct.grab.assert_called_once_with(region)


def test_monitor_out_of_range_is_a_clear_error(app):
    resp = _capture(app, monitor=9)
    assert resp["ok"] is False
    assert "out of range" in resp["error"]["message"]


def test_capture_to_file_respects_scope(tmp_path, mock_mss):
    inside = tmp_path / "inside"
    inside.mkdir()
    app = App(plugins=[ScreenshotPlugin()], fs_scope=[str(inside)])
    try:
        denied = _capture(app, dest=str(tmp_path / "out.png"))
        assert denied["ok"] is False
        assert denied["error"]["type"] == "FsScopeError"

        allowed = _capture(app, dest=str(inside / "shot.png"))
        assert allowed["ok"] is True
        assert (inside / "shot.png").read_bytes() == b"\x89PNG fake bytes"
    finally:
        app.ipc.close()


def test_wayland_fails_with_explanation(app, monkeypatch):
    monkeypatch.setattr(ScreenshotPlugin._check_supported.__globals__["sys"], "platform", "linux")
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")

    resp = _capture(app)
    assert resp["ok"] is False
    assert "Wayland" in resp["error"]["message"]
    assert resp["error"]["type"] == "RuntimeError"


def test_backend_failure_explains_macos_permission(app, mock_mss, monkeypatch):
    import vesper_screenshot.plugin as plugin_mod

    monkeypatch.setattr(plugin_mod.sys, "platform", "darwin")
    mock_mss._sct.grab.side_effect = Exception("CGDisplayCreateImage failed")

    resp = _capture(app)
    assert resp["ok"] is False
    assert "Screen Recording" in resp["error"]["message"]


def test_monitors_lists_geometry(app, mock_mss):
    resp = app.ipc.handle({"id": "1", "command": "vesper:screenshot:monitors", "args": {}})
    assert resp["ok"] is True
    assert len(resp["result"]) == 3
    assert resp["result"][1]["width"] == 1920


def test_plugin_alias():
    from vesper_screenshot import Plugin
    from vesper_screenshot.plugin import ScreenshotPlugin as Direct
    assert Plugin is Direct


def test_sdk_path_exists():
    path = ScreenshotPlugin.sdk_path()
    assert path is not None
    assert path.name == "vesper-screenshot.js"
