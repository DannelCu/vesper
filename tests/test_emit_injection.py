"""Tests that Window.emit() escapes event names to prevent JS injection."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from vesper.core.window import Window


def test_emit_event_name_is_escaped():
    w = Window()
    w.window = MagicMock()
    w.emit('x") ; alert(1) ; //', {"a": 1})
    sent = w.window.evaluate_js.call_args[0][0]
    assert json.dumps('vesper:x") ; alert(1) ; //') in sent


def test_emit_safe_event_name_is_correct():
    w = Window()
    w.window = MagicMock()
    w.emit("ready", {"status": "ok"})
    sent = w.window.evaluate_js.call_args[0][0]
    assert '"vesper:ready"' in sent
    assert '"status"' in sent


def test_emit_payload_is_serialized():
    w = Window()
    w.window = MagicMock()
    w.emit("data", {"key": "val\""})
    sent = w.window.evaluate_js.call_args[0][0]
    assert json.dumps({"key": 'val"'}) in sent
