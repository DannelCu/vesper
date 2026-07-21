"""Tests for IPC.close() and the vesper logger."""
from __future__ import annotations

import io
import logging
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from vesper import App
from vesper.core import logging as vesper_logging
from vesper.core.ipc import IPC
from vesper.core.registry import CommandRegistry


def _loop_threads() -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name == "vesper-async"]


# ── close() stops the loop thread ────────────────────────────────────────────


def test_close_stops_the_loop_thread():
    ipc = IPC(CommandRegistry())
    assert ipc._loop_thread.is_alive()

    ipc.close()

    assert not ipc._loop_thread.is_alive()
    assert ipc._loop.is_closed()


def test_close_is_idempotent():
    ipc = IPC(CommandRegistry())
    ipc.close()
    ipc.close()  # must not raise
    assert ipc._loop.is_closed()


def test_close_leaves_no_named_thread_behind():
    before = len(_loop_threads())
    ipc = IPC(CommandRegistry())
    assert len(_loop_threads()) == before + 1

    ipc.close()

    # join() has returned, so the thread is gone rather than merely stopping.
    assert len(_loop_threads()) == before


def test_async_commands_still_work_before_close():
    registry = CommandRegistry()

    async def ping() -> str:
        return "pong"

    registry.register(ping, name="ping")
    ipc = IPC(registry)

    try:
        resp = ipc.handle({"id": "1", "command": "ping", "args": {}})
        assert resp["result"] == "pong"
    finally:
        ipc.close()


def test_close_warns_and_survives_a_stuck_loop(caplog):
    """A command still holding the loop must not make close() hang or raise."""
    ipc = IPC(CommandRegistry())

    release = threading.Event()
    ipc._loop.call_soon_threadsafe(lambda: release.wait(5))

    vesper_logging.reset()
    try:
        with caplog.at_level(logging.WARNING, logger="vesper.ipc"):
            start = time.monotonic()
            ipc.close(timeout=0.2)
            elapsed = time.monotonic() - start

        assert elapsed < 2.0, "close() must give up rather than block"
        assert any("did not stop" in r.message for r in caplog.records)
        # The loop stays open on purpose — closing it under a running task would
        # raise inside that task and lose its cleanup.
        assert not ipc._loop.is_closed()
    finally:
        release.set()
        ipc.close()


# ── App.run() closes the loop ────────────────────────────────────────────────


def test_app_run_closes_the_ipc_loop():
    app = App()

    with patch.object(app.window, "create"), patch.object(app.window, "show"):
        app.run()

    assert not app.ipc._loop_thread.is_alive()


def test_app_run_closes_the_loop_even_if_show_raises():
    app = App()

    with patch.object(app.window, "create"), \
         patch.object(app.window, "show", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            app.run()

    assert not app.ipc._loop_thread.is_alive()


def test_app_run_closes_the_loop_after_tray_stop():
    """Ordering matters: the tray must be stopped before the loop goes away."""
    app = App()
    app._tray = MagicMock()
    calls = []

    app._tray.stop.side_effect = lambda: calls.append("tray")

    with patch.object(app.window, "create"), patch.object(app.window, "show"), \
         patch.object(app.ipc, "close", side_effect=lambda: calls.append("ipc")):
        app.run()

    assert calls == ["tray", "ipc"]


# ── logging module ───────────────────────────────────────────────────────────


def test_get_logger_is_namespaced():
    assert vesper_logging.get_logger("ipc").name == "vesper.ipc"
    assert vesper_logging.get_logger().name == "vesper"


def test_library_does_not_configure_logging_on_import():
    """Only a NullHandler, so importing Vesper never hijacks the app's logging."""
    vesper_logging.reset()
    root = logging.getLogger("vesper")
    assert all(isinstance(h, logging.NullHandler) for h in root.handlers)


def test_configure_debug_sets_debug_level():
    vesper_logging.reset()
    try:
        logger = vesper_logging.configure(debug=True, force=True)
        assert logger.level == logging.DEBUG
    finally:
        vesper_logging.reset()


def test_configure_without_debug_still_reports_warnings():
    """Verbosity changes with debug; failures are reported either way."""
    vesper_logging.reset()
    try:
        logger = vesper_logging.configure(debug=False, force=True)
        assert logger.level == logging.WARNING
    finally:
        vesper_logging.reset()


def test_configure_writes_to_the_given_stream():
    vesper_logging.reset()
    stream = io.StringIO()
    try:
        vesper_logging.configure(debug=True, stream=stream, force=True)
        vesper_logging.get_logger("test").warning("hello from vesper")
        assert "hello from vesper" in stream.getvalue()
    finally:
        vesper_logging.reset()


def test_repeated_configure_does_not_duplicate_output():
    vesper_logging.reset()
    stream = io.StringIO()
    try:
        vesper_logging.configure(debug=True, stream=stream, force=True)
        vesper_logging.configure(debug=True, stream=stream, force=True)
        vesper_logging.get_logger("test").warning("once")
        assert stream.getvalue().count("once") == 1
    finally:
        vesper_logging.reset()


# ── notify failures surface through the logger ───────────────────────────────


def test_notify_failure_is_logged_not_crashed(caplog):
    from vesper.core import notify

    vesper_logging.reset()
    with caplog.at_level(logging.ERROR, logger="vesper.notify"), \
         patch("vesper.core.notify.subprocess.run", side_effect=FileNotFoundError("no notify-send")):
        notify.send("title", "body")
        # send() is fire-and-forget; give the thread a moment to run.
        for _ in range(200):
            if caplog.records:
                break
            time.sleep(0.005)

    assert any("Failed to send notification" in r.message for r in caplog.records)
