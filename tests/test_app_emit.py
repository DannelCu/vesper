from unittest.mock import MagicMock

from vesper import App


def test_app_emit_calls_evaluate_js():
    app = App()
    app.window.window = MagicMock()
    app.emit("test_event", {"data": 1})
    app.window.window.evaluate_js.assert_called_once()


def test_app_emit_before_window_create_does_not_raise():
    app = App()
    assert app.window.window is None
    app.emit("test_event")


def test_app_emit_event_name_in_js():
    app = App()
    app.window.window = MagicMock()
    app.emit("my_event")
    js = app.window.window.evaluate_js.call_args[0][0]
    assert "vesper:my_event" in js


def test_app_emit_payload_in_js():
    import json
    app = App()
    app.window.window = MagicMock()
    payload = {"version": "1.0", "items": [1, 2]}
    app.emit("update", payload)
    js = app.window.window.evaluate_js.call_args[0][0]
    assert json.dumps(payload) in js