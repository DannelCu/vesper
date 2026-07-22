"""Tests for vesper-crash — mocked sentry_sdk, real IPC pipeline."""
from __future__ import annotations

import sys

import pytest

from vesper import App
from vesper_crash import CrashPlugin

DSN = "https://key@example.ingest.sentry.io/1"


@pytest.fixture
def app(mock_sentry):
    application = App(plugins=[CrashPlugin(dsn=DSN, release="app@1.0", environment="test")])
    yield application
    application.ipc.close()


# ── initialisation and privacy defaults ──────────────────────────────────────


def test_init_is_privacy_first(app, mock_sentry):
    mock_sentry.init.assert_called_once()
    kwargs = mock_sentry.init.call_args.kwargs
    assert kwargs["dsn"] == DSN
    assert kwargs["send_default_pii"] is False
    assert kwargs["default_integrations"] is False
    assert kwargs["max_breadcrumbs"] == 0
    assert kwargs["release"] == "app@1.0"
    assert kwargs["environment"] == "test"


def test_without_dsn_nothing_initialises(mock_sentry):
    app = App(plugins=[CrashPlugin()])
    try:
        mock_sentry.init.assert_not_called()
        # The bridge command exists as a no-op so frontend code needs no branch.
        resp = app.ipc.handle({
            "id": "1", "command": "vesper:crash:report", "args": {"message": "x"},
        })
        assert resp["ok"] is True
        assert resp["result"] is False
        mock_sentry.capture_message.assert_not_called()
    finally:
        app.ipc.close()


# ── IPC command exceptions ───────────────────────────────────────────────────


def test_command_exception_is_reported_and_error_flow_unchanged(app, mock_sentry):
    boom = ValueError("boom")

    @app.command
    def explode():
        raise boom

    resp = app.ipc.handle({"id": "1", "command": "explode", "args": {}})

    # The frontend still gets the exact same IPC error it always did.
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValueError"
    assert resp["error"]["message"] == "boom"

    mock_sentry.capture_exception.assert_called_once_with(boom)
    mock_sentry._scope.set_tag.assert_any_call("vesper.command", "explode")


def test_successful_commands_report_nothing(app, mock_sentry):
    @app.command
    def fine() -> str:
        return "ok"

    resp = app.ipc.handle({"id": "1", "command": "fine", "args": {}})
    assert resp["ok"] is True
    mock_sentry.capture_exception.assert_not_called()


def test_reporting_failure_does_not_alter_the_response(app, mock_sentry):
    mock_sentry.capture_exception.side_effect = RuntimeError("sentry down")

    @app.command
    def explode():
        raise ValueError("boom")

    resp = app.ipc.handle({"id": "1", "command": "explode", "args": {}})
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValueError"


# ── sys.excepthook ───────────────────────────────────────────────────────────


def test_excepthook_captures_and_chains(app, mock_sentry):
    calls = []
    original = sys.excepthook  # already the plugin's; grab the chain base first

    # Re-register on a fresh app to control the previous hook explicitly.
    app.ipc.close()
    sys.excepthook = lambda t, v, tb: calls.append(("previous", v))

    app2 = App(plugins=[CrashPlugin(dsn=DSN)])
    try:
        error = RuntimeError("unhandled")
        sys.excepthook(RuntimeError, error, None)

        mock_sentry.capture_exception.assert_called_with(error)
        assert ("previous", error) in calls   # the prior hook still ran
    finally:
        app2.ipc.close()
        sys.excepthook = original


# ── frontend bridge ──────────────────────────────────────────────────────────


def test_js_error_report_captures_message(app, mock_sentry):
    resp = app.ipc.handle({
        "id": "1", "command": "vesper:crash:report",
        "args": {"message": "undefined is not a function", "stack": "at foo.js:1", "kind": "error"},
    })
    assert resp["ok"] is True
    assert resp["result"] is True

    mock_sentry.capture_message.assert_called_once_with(
        "[frontend] undefined is not a function", level="error"
    )
    mock_sentry._scope.set_tag.assert_any_call("vesper.source", "frontend")
    mock_sentry._scope.set_extra.assert_any_call("stack", "at foo.js:1")


def test_plugin_alias():
    from vesper_crash import Plugin
    from vesper_crash.plugin import CrashPlugin as Direct
    assert Plugin is Direct


def test_sdk_path_exists():
    path = CrashPlugin.sdk_path()
    assert path is not None
    assert path.name == "vesper-crash.js"
