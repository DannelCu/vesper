"""Tests for single-instance locking and runtime deep links."""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from vesper import App
from vesper.core.single_instance import SingleInstance


def _wait_until(predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return False


@pytest.fixture
def lock_dir(tmp_path):
    return tmp_path / "lock"


# ── acquire / release ────────────────────────────────────────────────────────


def test_first_instance_acquires(lock_dir):
    lock = SingleInstance("app", lock_dir=lock_dir)
    try:
        assert lock.acquire() is True
        assert lock.is_primary is True
        assert lock.lock_file.exists()
    finally:
        lock.release()


def test_second_instance_is_refused(lock_dir):
    first = SingleInstance("app", lock_dir=lock_dir)
    second = SingleInstance("app", lock_dir=lock_dir)
    try:
        assert first.acquire() is True
        assert second.acquire() is False
        assert second.is_primary is False
    finally:
        second.release()
        first.release()


def test_release_removes_the_lock_file(lock_dir):
    lock = SingleInstance("app", lock_dir=lock_dir)
    lock.acquire()
    assert lock.lock_file.exists()

    lock.release()
    assert not lock.lock_file.exists()


def test_release_is_idempotent(lock_dir):
    lock = SingleInstance("app", lock_dir=lock_dir)
    lock.acquire()
    lock.release()
    lock.release()  # must not raise


def test_lock_can_be_reacquired_after_release(lock_dir):
    first = SingleInstance("app", lock_dir=lock_dir)
    first.acquire()
    first.release()

    second = SingleInstance("app", lock_dir=lock_dir)
    try:
        assert second.acquire() is True
    finally:
        second.release()


def test_different_app_names_do_not_contend(tmp_path):
    a = SingleInstance("app-a", lock_dir=tmp_path / "a")
    b = SingleInstance("app-b", lock_dir=tmp_path / "b")
    try:
        assert a.acquire() is True
        assert b.acquire() is True
    finally:
        a.release()
        b.release()


def test_context_manager_releases(lock_dir):
    with SingleInstance("app", lock_dir=lock_dir) as lock:
        lock.acquire()
        path = lock.lock_file
        assert path.exists()
    assert not path.exists()


# ── argv forwarding ──────────────────────────────────────────────────────────


def test_second_instance_forwards_argv(lock_dir):
    received: list[list[str]] = []

    first = SingleInstance("app", lock_dir=lock_dir, on_message=received.append)
    second = SingleInstance("app", lock_dir=lock_dir)
    try:
        first.acquire()

        with patch.object(sys, "argv", ["app.py", "myapp://open/42"]):
            assert second.acquire() is False

        assert _wait_until(lambda: received)
        assert received[0] == ["app.py", "myapp://open/42"]
    finally:
        second.release()
        first.release()


def test_send_delivers_explicit_argv(lock_dir):
    received: list[list[str]] = []
    first = SingleInstance("app", lock_dir=lock_dir, on_message=received.append)
    second = SingleInstance("app", lock_dir=lock_dir)
    try:
        first.acquire()
        assert second.send(["app.py", "myapp://x"]) is True
        assert _wait_until(lambda: received)
        assert received[0] == ["app.py", "myapp://x"]
    finally:
        first.release()


def test_send_without_a_primary_returns_false(lock_dir):
    lock = SingleInstance("app", lock_dir=lock_dir)
    assert lock.send(["app.py"]) is False


def test_handler_exception_does_not_kill_the_listener(lock_dir):
    calls = []

    def explode(argv):
        calls.append(argv)
        raise RuntimeError("handler exploded")

    first = SingleInstance("app", lock_dir=lock_dir, on_message=explode)
    try:
        first.acquire()
        SingleInstance("app", lock_dir=lock_dir).send(["a", "one://"])
        assert _wait_until(lambda: len(calls) == 1)

        # The listener must still accept the next message.
        SingleInstance("app", lock_dir=lock_dir).send(["a", "two://"])
        assert _wait_until(lambda: len(calls) == 2)
    finally:
        first.release()


# ── stale locks ──────────────────────────────────────────────────────────────


def test_stale_lock_file_is_taken_over(lock_dir):
    """A lock left by a crash names a port nobody is listening on."""
    lock_dir.mkdir(parents=True)
    stale = lock_dir / "instance.lock"
    stale.write_text(json.dumps({"port": 1, "token": "dead", "pid": 999999}))

    lock = SingleInstance("app", lock_dir=lock_dir)
    try:
        assert lock.acquire() is True
    finally:
        lock.release()


@pytest.mark.parametrize("content", ["", "not json", "[]", '{"port": 123}', '{"token": "x"}'])
def test_malformed_lock_file_is_taken_over(lock_dir, content):
    lock_dir.mkdir(parents=True)
    (lock_dir / "instance.lock").write_text(content)

    lock = SingleInstance("app", lock_dir=lock_dir)
    try:
        assert lock.acquire() is True
    finally:
        lock.release()


def test_acquire_degrades_to_running_unguarded_on_failure(lock_dir):
    """A lock that cannot be created must not stop the app from starting."""
    lock = SingleInstance("app", lock_dir=lock_dir)
    with patch.object(lock, "_become_primary", side_effect=OSError("no sockets")):
        assert lock.acquire() is True


# ── token authentication ─────────────────────────────────────────────────────


def test_lock_file_contains_a_token_and_port(lock_dir):
    lock = SingleInstance("app", lock_dir=lock_dir)
    try:
        lock.acquire()
        data = json.loads(lock.lock_file.read_text())
        assert isinstance(data["port"], int)
        assert len(data["token"]) >= 32
    finally:
        lock.release()


def test_message_without_the_token_is_rejected(lock_dir):
    """Loopback is reachable by any local process, so argv must be authenticated."""
    received: list[list[str]] = []
    lock = SingleInstance("app", lock_dir=lock_dir, on_message=received.append)
    try:
        lock.acquire()
        port = json.loads(lock.lock_file.read_text())["port"]

        with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
            sock.sendall(json.dumps({"argv": ["x", "evil://payload"]}).encode())
            sock.shutdown(socket.SHUT_WR)
            sock.recv(64)

        time.sleep(0.2)
        assert received == []
    finally:
        lock.release()


def test_message_with_a_wrong_token_is_rejected(lock_dir):
    received: list[list[str]] = []
    lock = SingleInstance("app", lock_dir=lock_dir, on_message=received.append)
    try:
        lock.acquire()
        port = json.loads(lock.lock_file.read_text())["port"]

        with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
            payload = {"token": "wrong", "argv": ["x", "evil://payload"]}
            sock.sendall(json.dumps(payload).encode())
            sock.shutdown(socket.SHUT_WR)
            sock.recv(64)

        time.sleep(0.2)
        assert received == []
    finally:
        lock.release()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes only")
def test_lock_file_is_not_world_readable(lock_dir):
    """The token is what authenticates a client, so the file must stay private."""
    lock = SingleInstance("app", lock_dir=lock_dir)
    try:
        lock.acquire()
        mode = os.stat(lock.lock_file).st_mode & 0o777
        assert mode == 0o600
    finally:
        lock.release()


def test_oversized_message_is_discarded(lock_dir):
    received: list[list[str]] = []
    lock = SingleInstance("app", lock_dir=lock_dir, on_message=received.append)
    try:
        lock.acquire()
        port = json.loads(lock.lock_file.read_text())["port"]

        with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
            try:
                sock.sendall(b"x" * (256 * 1024))
                sock.shutdown(socket.SHUT_WR)
            except OSError:
                pass  # server may close first, which is the point

        time.sleep(0.2)
        assert received == []
    finally:
        lock.release()


# ── App integration ──────────────────────────────────────────────────────────


def test_app_without_single_instance_has_no_lock():
    assert App()._single_instance is None


def test_app_with_single_instance_creates_one():
    app = App(single_instance=True)
    assert app._single_instance is not None
    app._single_instance.release()


def test_run_returns_without_a_window_when_another_instance_exists():
    app = App(single_instance=True)
    app._single_instance = MagicMock()
    app._single_instance.acquire.return_value = False

    with patch.object(app.window, "create") as create, \
         patch.object(app.window, "show") as show:
        app.run()

    create.assert_not_called()
    show.assert_not_called()


def test_run_releases_the_lock_on_exit():
    app = App(single_instance=True)
    app._single_instance = MagicMock()
    app._single_instance.acquire.return_value = True

    with patch.object(app.window, "create"), patch.object(app.window, "show"):
        app.run()

    app._single_instance.release.assert_called_once()


# ── runtime deep links ───────────────────────────────────────────────────────


def test_second_instance_argv_fires_deeplink_hooks():
    """A link opened while the app runs must reach the hooks, not a new process."""
    app = App()
    seen = []

    @app.on("deeplink")
    def handler(url):
        seen.append(url)

    with patch.object(app.window, "emit") as emit:
        app._on_second_instance(["app.py", "myapp://open/7"])

    assert seen == ["myapp://open/7"]
    emit.assert_called_once_with("deeplink", {"url": "myapp://open/7"})


def test_second_instance_without_a_url_fires_nothing():
    app = App()
    seen = []

    @app.on("deeplink")
    def handler(url):
        seen.append(url)

    with patch.object(app.window, "emit") as emit:
        app._on_second_instance(["app.py", "--flag"])

    assert seen == []
    emit.assert_not_called()


def test_second_instance_ignores_plain_web_urls():
    app = App()
    seen = []

    @app.on("deeplink")
    def handler(url):
        seen.append(url)

    with patch.object(app.window, "emit"):
        app._on_second_instance(["app.py", "https://example.com"])

    assert seen == []


def test_fire_deeplink_survives_a_failing_hook():
    app = App()
    seen = []

    @app.on("deeplink")
    def broken(url):
        raise RuntimeError("bad handler")

    @app.on("deeplink")
    def good(url):
        seen.append(url)

    with patch.object(app.window, "emit"):
        app._fire_deeplink("myapp://x")

    assert seen == ["myapp://x"]


def test_fire_deeplink_updates_the_stored_url():
    app = App()
    with patch.object(app.window, "emit"):
        app._fire_deeplink("myapp://latest")
    assert app._deeplink_url == "myapp://latest"


def test_startup_deeplink_still_fires_on_loaded():
    with patch.object(sys, "argv", ["app.py", "myapp://boot"]):
        app = App()

    seen = []

    @app.on("deeplink")
    def handler(url):
        seen.append(url)

    with patch.object(app.window, "create"), patch.object(app.window, "show"), \
         patch.object(app.window, "emit"):
        app.run()
        # run() registers the deep link on the "loaded" hook; fire it as the
        # window backend would.
        for fn in app._hooks.get("loaded", []):
            fn()

    assert seen == ["myapp://boot"]


# ── end to end across real processes ─────────────────────────────────────────


def test_two_real_processes_hand_over_argv(tmp_path):
    """
    The behaviour users actually get: launching the app twice.

    Exercised in-process across threads rather than with subprocesses so the test
    stays fast and portable, but through the same socket path.
    """
    received: list[list[str]] = []
    primary = SingleInstance("e2e", lock_dir=tmp_path, on_message=received.append)

    try:
        assert primary.acquire() is True

        results = []

        def second_launch():
            other = SingleInstance("e2e", lock_dir=tmp_path)
            with patch.object(sys, "argv", ["app.py", "myapp://from-second"]):
                results.append(other.acquire())

        thread = threading.Thread(target=second_launch)
        thread.start()
        thread.join(timeout=5)

        assert results == [False], "second launch should stand down"
        assert _wait_until(lambda: received)
        assert received[0][1] == "myapp://from-second"
    finally:
        primary.release()
