"""Tests for the production localhost server (vesper.core.static_server + App wiring)."""
from __future__ import annotations

import socket
import threading
import urllib.request

import pytest

from vesper import App
from vesper.core import static_server
from vesper.core.window import Window


@pytest.fixture
def frontend(tmp_path):
    root = tmp_path / "frontend"
    root.mkdir()
    (root / "index.html").write_text("<body>spa shell</body>")
    (root / "app.js").write_text("export default 1")
    (tmp_path / "secret.txt").write_text("TOP SECRET")
    return root


@pytest.fixture
def served(frontend):
    token = static_server.new_token()
    server, base = static_server.start(frontend, token=token)
    yield server, base, token, frontend
    server.shutdown()
    server.server_close()


def _get(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _raw_get(server, target: str) -> tuple[int, bytes]:
    """Raw HTTP so unnormalized traversal payloads reach the server verbatim."""
    host, port = server.server_address[:2]
    with socket.create_connection((host, port), timeout=5) as sock:
        sock.sendall(f"GET {target} HTTP/1.1\r\nHost: h\r\nConnection: close\r\n\r\n".encode())
        chunks = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    head, _, body = b"".join(chunks).partition(b"\r\n\r\n")
    return int(head.split()[1]), body


# ── serving and token gate ───────────────────────────────────────────────────


def test_binds_loopback_only(served):
    server, _, _, _ = served
    assert server.server_address[0] == "127.0.0.1"


def test_serves_index_with_token(served):
    _, base, _, _ = served
    status, body = _get(f"{base}/index.html")
    assert status == 200
    assert b"spa shell" in body


def test_base_url_root_serves_index(served):
    _, base, _, _ = served
    status, body = _get(base)
    assert status == 200
    assert b"spa shell" in body


def test_request_without_token_is_403(served):
    server, base, token, _ = served
    origin = base[: -len("/" + token)]
    status, body = _get(f"{origin}/index.html")
    assert status == 403
    assert b"spa shell" not in body


def test_wrong_token_is_403(served):
    server, base, token, _ = served
    origin = base[: -len("/" + token)]
    status, _ = _get(f"{origin}/{'x' * len(token)}/index.html")
    assert status == 403


def test_403_carries_no_existence_hint(served):
    """Missing and present assets answer identically without the token."""
    server, base, token, _ = served
    origin = base[: -len("/" + token)]
    status_present, _ = _get(f"{origin}/index.html")
    status_absent, _ = _get(f"{origin}/nope.html")
    assert status_present == status_absent == 403


# ── SPA fallback ─────────────────────────────────────────────────────────────


def test_extensionless_miss_serves_index(served):
    _, base, _, _ = served
    status, body = _get(f"{base}/settings/profile")
    assert status == 200
    assert b"spa shell" in body


def test_missing_asset_with_extension_is_404(served):
    _, base, _, _ = served
    status, _ = _get(f"{base}/missing.js")
    assert status == 404


def test_regular_asset_still_served(served):
    _, base, _, _ = served
    status, body = _get(f"{base}/app.js")
    assert status == 200
    assert b"export default" in body


# ── traversal confinement (same contract as the dev server) ──────────────────


def test_traversal_behind_token_is_refused(served):
    server, base, token, _ = served
    status, body = _raw_get(server, f"/{token}/../secret.txt")
    assert status in (403, 404)
    assert b"TOP SECRET" not in body


def test_percent_encoded_traversal_is_refused(served):
    server, base, token, _ = served
    status, body = _raw_get(server, f"/{token}/%2e%2e/secret.txt")
    assert status in (403, 404)
    assert b"TOP SECRET" not in body


# ── token generation ─────────────────────────────────────────────────────────


def test_tokens_are_unique_and_urlsafe():
    tokens = {static_server.new_token() for _ in range(32)}
    assert len(tokens) == 32
    for t in tokens:
        assert "/" not in t and len(t) >= 16


# ── App wiring ───────────────────────────────────────────────────────────────


def _run_app(monkeypatch, tmp_path, **app_kwargs):
    """Run an App with a mocked window; capture the serve_url Window.create got."""
    frontend = tmp_path / "frontend"
    frontend.mkdir(exist_ok=True)
    index = frontend / "index.html"
    index.write_text("<body>app</body>")

    captured = {}

    def fake_create(self, ipc_handler, config, hooks=None, secondary_windows=None,
                    menu=None, splash=None, serve_url=None):
        captured["serve_url"] = serve_url

    monkeypatch.setattr(Window, "create", fake_create)
    monkeypatch.setattr(Window, "show", lambda self: None)
    monkeypatch.delenv("VESPER_DEV_URL", raising=False)

    app = App(frontend=str(index), **app_kwargs)
    app.run()
    return app, captured


def test_app_without_serve_frontend_passes_no_url(monkeypatch, tmp_path):
    app, captured = _run_app(monkeypatch, tmp_path)
    assert captured["serve_url"] is None
    assert app._static_server is None


def test_app_serve_frontend_starts_and_stops_with_the_run(monkeypatch, tmp_path):
    seen = {}

    real_start = static_server.start

    def spying_start(frontend_dir, **kwargs):
        server, base = real_start(frontend_dir, **kwargs)
        seen["server"] = server
        return server, base

    monkeypatch.setattr(static_server, "start", spying_start)

    app, captured = _run_app(monkeypatch, tmp_path, serve_frontend=True)

    assert captured["serve_url"] is not None
    assert captured["serve_url"].startswith("http://127.0.0.1:")
    # Same lifecycle as the app: run() returned, so the server must be gone.
    assert app._static_server is None
    port = seen["server"].server_address[1]
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", port), timeout=0.5).close()


def test_app_serve_frontend_defers_to_dev_server(monkeypatch, tmp_path):
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    frontend = tmp_path / "frontend"
    frontend.mkdir()
    index = frontend / "index.html"
    index.write_text("<body>app</body>")

    captured = {}

    def fake_create(self, ipc_handler, config, hooks=None, secondary_windows=None,
                    menu=None, splash=None, serve_url=None):
        captured["serve_url"] = serve_url

    monkeypatch.setattr(Window, "create", fake_create)
    monkeypatch.setattr(Window, "show", lambda self: None)

    app = App(frontend=str(index), serve_frontend=True)
    app.run()

    assert captured["serve_url"] is None
    assert app._static_server is None


# ── Window.create URL resolution ─────────────────────────────────────────────


def test_window_uses_serve_url_for_frontend(monkeypatch, tmp_path):
    from unittest.mock import MagicMock
    import vesper.core.window as window_mod
    from vesper.core.config import WindowConfig
    from vesper.core.ipc import IPC
    from vesper.core.registry import CommandRegistry

    index = tmp_path / "index.html"
    index.write_text("<body></body>")

    mock_wv = MagicMock()
    mock_wv.create_window.return_value = MagicMock()
    monkeypatch.setattr(window_mod, "webview", mock_wv)
    monkeypatch.delenv("VESPER_DEV_URL", raising=False)

    w = Window()
    w.create(
        IPC(CommandRegistry()),
        WindowConfig(frontend=str(index)),
        serve_url="http://127.0.0.1:9999/tok",
    )

    assert mock_wv.create_window.call_args[1]["url"] == "http://127.0.0.1:9999/tok/index.html"


def test_window_dev_url_wins_over_serve_url(monkeypatch, tmp_path):
    from unittest.mock import MagicMock
    import vesper.core.window as window_mod
    from vesper.core.config import WindowConfig
    from vesper.core.ipc import IPC
    from vesper.core.registry import CommandRegistry

    mock_wv = MagicMock()
    mock_wv.create_window.return_value = MagicMock()
    monkeypatch.setattr(window_mod, "webview", mock_wv)
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    w = Window()
    w.create(
        IPC(CommandRegistry()),
        WindowConfig(frontend="index.html"),
        serve_url="http://127.0.0.1:9999/tok",
    )

    assert mock_wv.create_window.call_args[1]["url"] == "http://localhost:3000"
