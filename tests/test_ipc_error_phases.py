"""
Tests that IPC reports which phase failed.

A guard rejecting a call is policy the frontend may act on; a guard or middleware
raising is a bug in the app. They used to be indistinguishable in the response.
"""
from __future__ import annotations

import logging

import pytest

from vesper import App, guard
from vesper.core import logging as vesper_logging
from vesper.exceptions import ForbiddenError


def _make_app(**kwargs) -> App:
    return App(**kwargs)


def _call(app: App, command: str = "target", args: dict | None = None) -> dict:
    return app.ipc.handle({"id": "1", "command": command, "args": args or {}})


# ── Guard rejection stays ForbiddenError ─────────────────────────────────────


def test_guard_returning_false_is_forbidden():
    app = _make_app()

    @app.command("target")
    @guard(lambda name, args: False)
    def target() -> str:
        return "reached"

    resp = _call(app)
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ForbiddenError"


def test_guard_raising_forbidden_error_is_forbidden():
    app = _make_app()

    def deny(name, args):
        raise ForbiddenError("nope")

    @app.command("target")
    @guard(deny)
    def target() -> str:
        return "reached"

    resp = _call(app)
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ForbiddenError"
    assert resp["error"]["message"] == "nope"


# ── Guard blowing up is a GuardError ─────────────────────────────────────────


def test_guard_raising_unexpected_error_is_guard_error():
    app = _make_app()

    def broken(name, args):
        raise RuntimeError("guard exploded")

    @app.command("target")
    @guard(broken)
    def target() -> str:
        return "reached"

    resp = _call(app)
    assert resp["ok"] is False
    assert resp["error"]["type"] == "GuardError"
    assert resp["error"]["message"] == "guard exploded"
    # The real class is preserved so the cause is not lost.
    assert resp["error"]["cause"] == "RuntimeError"


def test_guard_error_is_distinguishable_from_command_error():
    """The whole point: a broken check must not look like a rejected call."""
    app = _make_app()

    def broken(name, args):
        raise ValueError("boom")

    @app.command("target")
    @guard(broken)
    def target() -> str:
        return "reached"

    assert _call(app)["error"]["type"] != "ForbiddenError"


# ── Middleware ───────────────────────────────────────────────────────────────


def test_middleware_raising_is_middleware_error():
    app = _make_app()

    @app.middleware
    def broken(name, args):
        raise RuntimeError("middleware exploded")

    @app.command("target")
    def target() -> str:
        return "reached"

    resp = _call(app)
    assert resp["ok"] is False
    assert resp["error"]["type"] == "MiddlewareError"
    assert resp["error"]["cause"] == "RuntimeError"


def test_middleware_may_still_reject_with_forbidden():
    app = _make_app()

    @app.middleware
    def deny(name, args):
        raise ForbiddenError("blocked by policy")

    @app.command("target")
    def target() -> str:
        return "reached"

    resp = _call(app)
    assert resp["error"]["type"] == "ForbiddenError"
    assert resp["error"]["message"] == "blocked by policy"


def test_middleware_error_does_not_run_the_command():
    app = _make_app()
    calls = []

    @app.middleware
    def broken(name, args):
        raise RuntimeError("nope")

    @app.command("target")
    def target() -> str:
        calls.append(1)
        return "reached"

    _call(app)
    assert calls == []


# ── Command errors keep their own type ───────────────────────────────────────


def test_command_raising_reports_its_own_exception_type():
    app = _make_app()

    @app.command("target")
    def target() -> str:
        raise KeyError("missing")

    resp = _call(app)
    assert resp["ok"] is False
    assert resp["error"]["type"] == "KeyError"
    # No phase wrapper, so no cause field is added.
    assert "cause" not in resp["error"]


def test_all_three_phases_report_distinct_types():
    """One assertion covering the actual requirement."""
    types = {}

    guard_app = _make_app()

    def exploding_guard(name, args):
        raise RuntimeError("g")

    @guard_app.command("target")
    @guard(exploding_guard)
    def guard_target() -> None: ...

    types["guard"] = _call(guard_app)["error"]["type"]

    mw_app = _make_app()

    @mw_app.middleware
    def mw(name, args):
        raise RuntimeError("m")

    @mw_app.command("target")
    def mw_target() -> None: ...

    types["middleware"] = _call(mw_app)["error"]["type"]

    cmd_app = _make_app()

    @cmd_app.command("target")
    def cmd_target() -> None:
        raise RuntimeError("c")

    types["command"] = _call(cmd_app)["error"]["type"]

    assert types == {
        "guard": "GuardError",
        "middleware": "MiddlewareError",
        "command": "RuntimeError",
    }


# ── debug traceback still attached per phase ─────────────────────────────────


@pytest.mark.parametrize("phase", ["guard", "middleware"])
def test_debug_mode_attaches_traceback_for_each_phase(phase):
    app = _make_app(debug=True)

    if phase == "guard":
        def exploding_guard(name, args):
            raise RuntimeError("x")

        @app.command("target")
        @guard(exploding_guard)
        def target() -> None: ...
    else:
        @app.middleware
        def mw(name, args):
            raise RuntimeError("x")

        @app.command("target")
        def target() -> None: ...

    resp = _call(app)
    assert "traceback" in resp["error"]
    assert "RuntimeError" in resp["error"]["traceback"]


# ── Teardown failures are logged, not swallowed ──────────────────────────────


def test_teardown_failure_is_logged(caplog):
    app = _make_app()

    @app.command("target")
    def target() -> str:
        return "ok"

    def broken_teardown():
        raise RuntimeError("teardown exploded")

    app.add_teardown(broken_teardown)

    vesper_logging.reset()
    with caplog.at_level(logging.ERROR, logger="vesper.ipc"):
        resp = _call(app)

    # The command still succeeds — teardown failures must not break the response.
    assert resp["ok"] is True
    assert any("Teardown callback" in r.message for r in caplog.records)
    assert any("teardown exploded" in (r.exc_text or "") for r in caplog.records)
