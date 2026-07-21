"""
Single-instance support.

When enabled, the first process to start becomes the primary instance and listens on
a loopback socket. Any later process hands its ``sys.argv`` to the primary and exits,
so a deep link opened while the app is already running reaches the running window
instead of starting a second copy.

Design notes
------------
**Transport: loopback TCP, not a named mutex or a Unix socket.** A mutex signals that
another instance exists but carries no payload, and forwarding argv is the whole
point. Unix domain sockets are the natural POSIX answer but are awkward on Windows,
so a socket bound to 127.0.0.1 on an ephemeral port is used everywhere and keeps one
code path.

**Authentication.** The port is written to a lock file along with a random token, and
a client must present that token before its argv is accepted. Loopback is reachable
by every process on the machine, so without this any local program could inject a
deep link into a running app. The lock file is created 0600, which is what actually
restricts the token to this user.

**Stale locks.** A lock file left behind by a crash names a port nobody is listening
on. Rather than trusting the file, acquire() tries to connect: only a successful
handshake proves a live primary, and anything else means the lock is stale and can be
taken over.
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import threading
from collections.abc import Callable
from pathlib import Path

from vesper.core.logging import get_logger
from vesper.core.paths import ensure_dir, runtime_dir

logger = get_logger("single_instance")

_HOST = "127.0.0.1"
_TOKEN_BYTES = 32
_CONNECT_TIMEOUT = 2.0
_ACCEPT_POLL = 0.1
_MAX_PAYLOAD = 64 * 1024


class SingleInstance:
    """
    Guards against a second copy of the app running.

    Usage:
        lock = SingleInstance("my-app", on_message=handle_argv)
        if not lock.acquire():
            sys.exit(0)   # a primary already exists and has been notified
    """

    def __init__(
        self,
        app_name: str,
        *,
        on_message: Callable[[list[str]], None] | None = None,
        lock_dir: Path | None = None,
    ) -> None:
        """
        Args:
            app_name:   Identifies the app; two apps with different names never
                        contend for the same lock.
            on_message: Called on the primary with the argv a secondary forwarded.
                        Runs on the listener thread, not the UI thread.
            lock_dir:   Override the lock file location. Intended for tests.
        """
        self.app_name = app_name
        self.on_message = on_message

        self._dir = lock_dir if lock_dir is not None else runtime_dir(app_name)
        self._lock_file = self._dir / "instance.lock"

        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._token: str | None = None
        self._running = False

    # ── public API ───────────────────────────────────────────────────────────

    @property
    def lock_file(self) -> Path:
        return self._lock_file

    @property
    def is_primary(self) -> bool:
        return self._running

    def acquire(self) -> bool:
        """
        Try to become the primary instance.

        Returns:
            True if this process is now the primary and should carry on starting.
            False if another instance is already running; it has been handed this
            process's argv and this one should exit.

        Never raises: if the lock cannot be used at all, the app starts normally as
        an unguarded instance rather than refusing to run.
        """
        try:
            existing = self._read_lock()

            if existing and self._notify_primary(existing):
                return False

            # Either no lock file, or one naming a port with nobody behind it.
            return self._become_primary()
        except Exception:
            logger.exception(
                "Single-instance lock unavailable; starting without it"
            )
            return True

    def release(self) -> None:
        """Stop listening and remove the lock file. Safe to call more than once."""
        self._running = False

        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
            self._server = None

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

        try:
            if self._lock_file.exists():
                self._lock_file.unlink()
        except OSError:
            logger.debug("Could not remove lock file %s", self._lock_file)

    def send(self, argv: list[str]) -> bool:
        """
        Forward argv to a running primary, if there is one.

        Returns True when a primary accepted the message.
        """
        existing = self._read_lock()
        if not existing:
            return False
        return self._notify_primary(existing, argv)

    def __enter__(self) -> SingleInstance:
        return self

    def __exit__(self, *exc_info) -> None:
        self.release()

    # ── lock file ────────────────────────────────────────────────────────────

    def _read_lock(self) -> dict | None:
        try:
            raw = self._lock_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.debug("Ignoring malformed lock file %s", self._lock_file)
            return None

        if not isinstance(data, dict) or "port" not in data or "token" not in data:
            return None
        return data

    def _write_lock(self, port: int, token: str) -> None:
        ensure_dir(self._dir)
        payload = json.dumps({"port": port, "token": token, "pid": os.getpid()})

        # Create with 0600 from the start. Writing first and chmod-ing after would
        # leave the token world-readable in between.
        fd = os.open(self._lock_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, payload.encode("utf-8"))
        finally:
            os.close(fd)

    # ── primary ──────────────────────────────────────────────────────────────

    def _become_primary(self) -> bool:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.bind((_HOST, 0))
            server.listen(8)
            server.settimeout(_ACCEPT_POLL)
        except OSError:
            server.close()
            raise

        port = server.getsockname()[1]
        self._token = secrets.token_hex(_TOKEN_BYTES)
        self._write_lock(port, self._token)

        self._server = server
        self._running = True
        self._thread = threading.Thread(
            target=self._serve, name="vesper-single-instance", daemon=True
        )
        self._thread.start()

        logger.debug("Primary instance listening on port %d", port)
        return True

    def _serve(self) -> None:
        while self._running and self._server is not None:
            try:
                conn, _ = self._server.accept()
            except TimeoutError:
                # The accept timeout exists so this loop notices release() promptly:
                # closing the socket does not reliably wake a blocked accept() on
                # Linux, which would make every release() wait out its join timeout.
                continue
            except OSError:
                # Expected when release() closes the socket out from under accept().
                break

            with conn:
                try:
                    conn.settimeout(_CONNECT_TIMEOUT)
                    self._handle_client(conn)
                except Exception:
                    logger.exception("Failed handling a second-instance message")

    def _handle_client(self, conn: socket.socket) -> None:
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > _MAX_PAYLOAD:
                logger.warning("Discarding oversized second-instance message")
                return

        try:
            message = json.loads(b"".join(chunks).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.debug("Ignoring malformed second-instance message")
            return

        if not isinstance(message, dict):
            return

        # Loopback is reachable by every local process, so an unauthenticated
        # message could inject a deep link into a running app.
        if not self._token or message.get("token") != self._token:
            logger.warning("Rejected second-instance message with a bad token")
            return

        argv = message.get("argv")
        if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
            return

        conn.sendall(b'{"ok":true}')

        if self.on_message is not None:
            self.on_message(argv)

    # ── secondary ────────────────────────────────────────────────────────────

    def _notify_primary(self, lock: dict, argv: list[str] | None = None) -> bool:
        """
        Hand argv to the primary named in the lock file.

        Returns False when nothing is listening, which is how a stale lock file is
        told apart from a live instance.
        """
        import sys

        port = lock.get("port")
        token = lock.get("token")
        if not isinstance(port, int) or not isinstance(token, str):
            return False

        payload = json.dumps({
            "token": token,
            "argv": list(argv) if argv is not None else list(sys.argv),
        }).encode("utf-8")

        try:
            with socket.create_connection((_HOST, port), timeout=_CONNECT_TIMEOUT) as sock:
                sock.sendall(payload)
                sock.shutdown(socket.SHUT_WR)
                reply = sock.recv(256)
        except OSError:
            logger.debug("No primary instance on port %s; treating lock as stale", port)
            return False

        return b'"ok":true' in reply.replace(b" ", b"")
