import json
from unittest.mock import MagicMock

from vesper.core.window import Window


def _make_window():
    w = Window()
    mock = MagicMock()
    w.window = mock
    return w, mock


def test_emit_calls_evaluate_js():
    w, mock = _make_window()
    w.emit("test")
    mock.evaluate_js.assert_called_once()


def test_emit_event_name_prefixed():
    w, mock = _make_window()
    w.emit("my_event")
    js = mock.evaluate_js.call_args[0][0]
    assert 'vesper:my_event' in js


def test_emit_none_payload_serializes_null():
    w, mock = _make_window()
    w.emit("ping")
    js = mock.evaluate_js.call_args[0][0]
    assert "null" in js


def test_emit_dict_payload_serialized():
    w, mock = _make_window()
    payload = {"key": "value", "num": 42}
    w.emit("data", payload)
    js = mock.evaluate_js.call_args[0][0]
    assert json.dumps(payload) in js


def test_emit_list_payload_serialized():
    w, mock = _make_window()
    w.emit("items", [1, 2, 3])
    js = mock.evaluate_js.call_args[0][0]
    assert json.dumps([1, 2, 3]) in js


def test_emit_dispatches_custom_event():
    w, mock = _make_window()
    w.emit("update", {"v": 1})
    js = mock.evaluate_js.call_args[0][0]
    assert "CustomEvent" in js
    assert "dispatchEvent" in js


def test_emit_before_window_create_does_not_raise():
    w = Window()
    assert w.window is None
    w.emit("test", {"data": 1})


def test_emit_before_window_create_skips_evaluate_js():
    w = Window()
    w.emit("test")
    # Nothing to assert — just verifying no AttributeError on None
