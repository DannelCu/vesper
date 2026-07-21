"""Tests for dev server path confinement (vesper/commands/dev.py)."""
from __future__ import annotations

import http.server
import socket
import threading

import pytest

from vesper.commands.dev import _make_dev_handler


@pytest.fixture
def dev_server(tmp_path):
    """
    Run the real dev handler over a real socket.

    Requests are written as raw HTTP so the traversal payload reaches the server
    verbatim — an HTTP client library would normalize "/../" away before sending and
    the test would pass without the server doing anything.
    """
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text("<body>hello</body>")
    (frontend / "app.js").write_text("console.log(1)")

    # The file a traversal is trying to reach, one level above the served root.
    (tmp_path / "secret.txt").write_text("TOP SECRET")

    server = http.server.HTTPServer(("localhost", 0), _make_dev_handler(frontend, [0]))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield server, tmp_path, frontend

    server.shutdown()
    server.server_close()


def _raw_get(server, target: str) -> tuple[int, bytes]:
    """Send a GET with an unnormalized target; return (status, body)."""
    host, port = server.server_address[:2]
    with socket.create_connection((host, port), timeout=5) as sock:
        sock.sendall(f"GET {target} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
        chunks = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)

    raw = b"".join(chunks)
    head, _, body = raw.partition(b"\r\n\r\n")
    status = int(head.split()[1])
    return status, body


# ── Normal serving still works ───────────────────────────────────────────────


def test_serves_index_at_root(dev_server):
    server, _, _ = dev_server
    status, body = _raw_get(server, "/")
    assert status == 200
    assert b"hello" in body


def test_serves_regular_file(dev_server):
    server, _, _ = dev_server
    status, body = _raw_get(server, "/app.js")
    assert status == 200
    assert b"console.log(1)" in body


def test_missing_file_inside_root_is_404(dev_server):
    server, _, _ = dev_server
    status, _ = _raw_get(server, "/nope.js")
    assert status == 404


# ── Traversal is refused ─────────────────────────────────────────────────────


def test_traversal_with_dotdot_is_refused(dev_server):
    server, _, _ = dev_server
    status, body = _raw_get(server, "/../secret.txt")
    assert status in (403, 404)
    assert b"TOP SECRET" not in body


def test_traversal_to_etc_passwd_is_refused(dev_server):
    server, _, _ = dev_server
    status, body = _raw_get(server, "/../../../../../../etc/passwd")
    assert status in (403, 404)
    assert b"root:" not in body


def test_percent_encoded_traversal_is_refused(dev_server):
    """Decoding happens before the check, so %2e%2e cannot slip past it."""
    server, _, _ = dev_server
    status, body = _raw_get(server, "/%2e%2e/secret.txt")
    assert status in (403, 404)
    assert b"TOP SECRET" not in body


def test_absolute_path_is_refused(dev_server):
    server, _, _ = dev_server
    status, body = _raw_get(server, "//etc/passwd")
    assert status in (403, 404)
    assert b"root:" not in body


def test_symlink_escaping_root_is_refused(dev_server, tmp_path):
    """A symlink inside the served root pointing outside must not be followed."""
    server, base, frontend = dev_server
    link = frontend / "escape.txt"
    try:
        link.symlink_to(base / "secret.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")

    status, body = _raw_get(server, "/escape.txt")
    assert status in (403, 404)
    assert b"TOP SECRET" not in body


# ── Percent-decoding of legitimate names ─────────────────────────────────────


def test_percent_encoded_space_in_filename_is_served(dev_server):
    server, _, frontend = dev_server
    (frontend / "my file.css").write_text("body{}")
    status, body = _raw_get(server, "/my%20file.css")
    assert status == 200
    assert b"body{}" in body
