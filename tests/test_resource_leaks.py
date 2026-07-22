"""
Regression guard for the descriptor and thread leak in App.

Every App used to build an asyncio event loop and its thread in IPC.__init__,
whether or not anything async was ever run. Three descriptors and one thread per
App, and neither `del` nor the garbage collector reclaimed them — the daemon
thread keeps the loop alive. A full test run builds hundreds of Apps without
calling run(), so the process hit its descriptor limit and tests that merely
happened to run late (vesper-watch's, which need inotify descriptors) started
failing with EMFILE.

These tests fail if that comes back.
"""
from __future__ import annotations

import gc
import os
import threading

import pytest

from vesper import App

APP_COUNT = 20


def _loop_threads() -> int:
    return sum(1 for t in threading.enumerate() if t.name == "vesper-async")


def _open_fds() -> int:
    return len(os.listdir("/proc/self/fd"))


# Counting descriptors portably means a different mechanism per platform, each
# with its own failure modes. /proc is exact where it exists, and the thread
# assertions below run everywhere and catch the same leak.
needs_proc = pytest.mark.skipif(
    not os.path.isdir("/proc/self/fd"), reason="descriptor count needs /proc"
)


def test_many_apps_start_no_threads():
    """The plain case: no async anywhere, so no loop should ever be built."""
    before = _loop_threads()

    apps = [App() for _ in range(APP_COUNT)]
    assert _loop_threads() == before

    for app in apps:
        app.close()
    assert _loop_threads() == before


@needs_proc
def test_many_apps_leak_no_descriptors():
    before_fds = _open_fds()

    apps = [App() for _ in range(APP_COUNT)]
    for app in apps:
        app.close()
    del apps
    gc.collect()

    # Not an equality check: the import machinery and pytest's own capture can
    # legitimately move the count by one or two. The leak was three per App —
    # sixty across this loop — so the margin is nowhere near it.
    assert _open_fds() - before_fds <= 2


def test_apps_with_async_commands_release_their_loops():
    """The case laziness cannot help: the loop is real, so close() must reclaim it."""
    before = _loop_threads()

    apps = []
    for _ in range(APP_COUNT):
        app = App()

        @app.command("ping")
        async def ping() -> str:
            return "pong"

        assert app.ipc.handle({"id": "1", "command": "ping", "args": {}})["ok"]
        apps.append(app)

    assert _loop_threads() == before + APP_COUNT, "each async app runs its own loop"

    for app in apps:
        app.close()

    assert _loop_threads() == before, "close() must reclaim every loop thread"


@needs_proc
def test_async_apps_leak_no_descriptors_once_closed():
    before_fds = _open_fds()

    for _ in range(APP_COUNT):
        with App() as app:

            @app.command("ping")
            async def ping() -> str:
                return "pong"

            app.ipc.handle({"id": "1", "command": "ping", "args": {}})

    gc.collect()

    assert _open_fds() - before_fds <= 2


def test_context_manager_reclaims_everything():
    before = _loop_threads()

    for _ in range(APP_COUNT):
        with App() as app:
            app.ipc._ensure_loop()

    assert _loop_threads() == before
