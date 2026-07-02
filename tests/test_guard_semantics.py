"""Tests for fail-safe guard semantics: only True and None allow a call."""
from __future__ import annotations

from vesper import App


def _call(app, guard_fn):
    app.registry._guards["vesper:os:info"] = [guard_fn]
    return app.ipc.handle({"id": 1, "command": "vesper:os:info", "args": {}})


def test_guard_true_allows():
    assert _call(App(), lambda c, a: True)["ok"] is True


def test_guard_none_allows():
    assert _call(App(), lambda c, a: None)["ok"] is True


def test_guard_false_blocks():
    assert _call(App(), lambda c, a: False)["ok"] is False


def test_guard_zero_blocks():
    assert _call(App(), lambda c, a: 0)["ok"] is False


def test_guard_empty_string_blocks():
    assert _call(App(), lambda c, a: "")["ok"] is False


def test_guard_empty_list_blocks():
    assert _call(App(), lambda c, a: [])["ok"] is False
