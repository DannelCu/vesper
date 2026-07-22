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
    ipc._ensure_loop()          # the loop is lazy; an async call would do the same
    assert ipc._loop_thread.is_alive()

    ipc.close()

    assert not ipc._loop_thread.is_alive()
    assert ipc._loop.is_closed()


def test_close_is_idempotent():
    ipc = IPC(CommandRegistry())
    ipc._ensure_loop()
    ipc.close()
    ipc.close()  # must not raise
    assert ipc._loop.is_closed()


def test_close_leaves_no_named_thread_behind():
    before = len(_loop_threads())
    ipc = IPC(CommandRegistry())
    ipc._ensure_loop()
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
    ipc._ensure_loop()

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
    app.ipc._ensure_loop()      # an app with no async command never builds one

    with patch.object(app.window, "create"), patch.object(app.window, "show"):
        app.run()

    assert not app.ipc._loop_thread.is_alive()


def test_app_run_closes_the_loop_even_if_show_raises():
    app = App()
    app.ipc._ensure_loop()

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


# ── the loop is lazy ─────────────────────────────────────────────────────────
#
# Every App used to cost a thread and three descriptors from the moment it was
# constructed, reclaimable only by close(). Tests build Apps and never call
# run(), so a full suite ran the process out of file descriptors and unrelated
# tests started failing with EMFILE hundreds of tests later.


def test_no_loop_thread_until_something_async_runs():
    before = len(_loop_threads())
    ipc = IPC(CommandRegistry())

    assert ipc._loop is None
    assert ipc._loop_thread is None
    assert len(_loop_threads()) == before


def test_a_sync_command_never_starts_the_loop():
    registry = CommandRegistry()
    registry.register(lambda: "pong", name="ping")
    ipc = IPC(registry)

    assert ipc.handle({"id": "1", "command": "ping", "args": {}})["result"] == "pong"
    assert ipc._loop is None, "a sync-only app must not pay for an event loop"


def test_an_app_starts_no_threads():
    """The construct-and-never-run case that exhausted the descriptors."""
    before = len(_loop_threads())
    App()
    assert len(_loop_threads()) == before


def test_the_first_async_command_starts_the_loop_and_returns():
    """Laziness must be invisible: the first async call works like any other."""
    registry = CommandRegistry()

    async def ping() -> str:
        return "pong"

    registry.register(ping, name="ping")
    ipc = IPC(registry)
    assert ipc._loop is None

    try:
        resp = ipc.handle({"id": "1", "command": "ping", "args": {}})
        assert resp["ok"] is True
        assert resp["result"] == "pong"
        assert ipc._loop is not None
        assert ipc._loop_thread.is_alive()
    finally:
        ipc.close()


def test_repeated_async_calls_reuse_one_loop():
    registry = CommandRegistry()

    async def ping() -> str:
        return "pong"

    registry.register(ping, name="ping")
    ipc = IPC(registry)
    before = len(_loop_threads())

    try:
        for i in range(5):
            assert ipc.handle({"id": str(i), "command": "ping", "args": {}})["ok"]
        assert len(_loop_threads()) == before + 1
    finally:
        ipc.close()


def test_close_without_a_loop_is_a_noop():
    ipc = IPC(CommandRegistry())
    ipc.close()
    ipc.close()   # must not raise on an IPC that never built a loop
    assert ipc._loop is None


def test_concurrent_first_calls_create_one_loop():
    """handle() is reachable from several threads; two loops would orphan one."""
    registry = CommandRegistry()

    async def ping() -> str:
        return "pong"

    registry.register(ping, name="ping")
    ipc = IPC(registry)
    before = len(_loop_threads())

    loops = []
    barrier = threading.Barrier(8)

    def race() -> None:
        barrier.wait()
        loops.append(ipc._ensure_loop())

    threads = [threading.Thread(target=race) for _ in range(8)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len({id(loop) for loop in loops}) == 1
        assert len(_loop_threads()) == before + 1
    finally:
        ipc.close()


# ── App.close() ──────────────────────────────────────────────────────────────


def test_app_close_is_idempotent():
    app = App()
    app.close()
    app.close()   # must not raise


def test_app_close_on_a_fresh_app_does_not_raise():
    """Nothing was started, so every piece close() touches is still None."""
    App().close()


def test_app_close_releases_the_loop():
    app = App()
    app.ipc._ensure_loop()
    before = len(_loop_threads())

    app.close()

    assert len(_loop_threads()) == before - 1


def test_app_close_stops_the_tray():
    app = App()
    app._tray = MagicMock()
    tray = app._tray

    app.close()

    tray.stop.assert_called_once()


def test_app_close_survives_a_failing_piece():
    """One backend failing must not strand the rest — the loop still closes."""
    app = App()
    app.ipc._ensure_loop()
    app._tray = MagicMock()
    app._tray.stop.side_effect = RuntimeError("tray is wedged")

    app.close()

    assert app.ipc._loop.is_closed()


def test_app_works_as_a_context_manager():
    before = len(_loop_threads())

    with App() as app:
        assert isinstance(app, App)
        app.ipc._ensure_loop()
        assert len(_loop_threads()) == before + 1

    assert len(_loop_threads()) == before


def test_context_manager_closes_on_an_exception():
    before = len(_loop_threads())

    with pytest.raises(ValueError):
        with App() as app:
            app.ipc._ensure_loop()
            raise ValueError("boom")

    assert len(_loop_threads()) == before
