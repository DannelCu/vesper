"""
Loopback static file server shared by `vesper dev` and production serving.

Production apps load their frontend over `file://` by default, which breaks ES
modules, `history.pushState` routing, and relative `fetch()`. `App(
serve_frontend=True)` serves the bundled frontend from here instead — bound to
127.0.0.1 on an ephemeral port, guarded by a per-session token, and living and
dying with the app process.

Threat model (documented with the same honesty as the single-instance entry in
KNOWN-ISSUES.md): loopback HTTP is reachable by *any* local process, not just
this app. The random token in the URL path stops another local process from
trivially enumerating the app's assets by scanning ports — but a process that
can read this process's memory or command line was already on the winning side
of every local boundary. The token protects against casual snooping, not
against a hostile local user. What `file://` gave up by moving to HTTP is a
per-app origin: every Vesper app serving on loopback shares the browser origin
`http://127.0.0.1:<port>`, port permitting. See KNOWN-ISSUES.md (KI3) for why a
custom scheme — the real fix — is not currently possible.
"""
from __future__ import annotations

import http.server
import json
import mimetypes
import secrets
import threading
import urllib.parse
from collections.abc import Callable
from pathlib import Path


def new_token() -> str:
    """A URL-safe per-session secret for the path prefix."""
    return secrets.token_urlsafe(16)


# Files are streamed in blocks rather than read whole. A media library served from
# here can hold files far larger than the process should ever hold in memory.
_CHUNK_BYTES = 64 * 1024


def parse_range(header: str | None, size: int) -> tuple[int, int] | None | bool:
    """
    Resolve a Range header against a file of *size* bytes.

    Returns the inclusive ``(start, end)`` to send, None when the whole file
    should be sent, or False when the range cannot be satisfied (416).

    Only the single-range forms browsers actually send for media are handled —
    ``bytes=0-``, ``bytes=100-199`` and the suffix form ``bytes=-500``. A
    multi-range request falls back to the whole file, which is a valid response.
    """
    if not header:
        return None

    units, _, spec = header.partition("=")
    if units.strip().lower() != "bytes" or "," in spec:
        return None

    start_text, sep, end_text = spec.strip().partition("-")
    if not sep:
        return None

    try:
        if not start_text:
            # Suffix form: the last N bytes.
            length = int(end_text)
            if length <= 0:
                return False
            return max(0, size - length), size - 1

        start = int(start_text)
        end = int(end_text) if end_text else size - 1
    except ValueError:
        return None

    if start >= size or start < 0 or end < start:
        return False

    return start, min(end, size - 1)


def make_static_handler(
    frontend_dir: Path,
    *,
    token: str | None = None,
    spa_fallback: bool = False,
    html_postprocess: Callable[[bytes], bytes] | None = None,
    routes: dict[str, Callable[[], dict]] | None = None,
) -> type:
    """
    Build a request handler class serving *frontend_dir*.

    Args:
        token:            When set, every request must carry it as the first path
                          segment; anything else is answered 403 with no hint of
                          whether the asset exists.
        spa_fallback:     Serve index.html for extensionless paths that match no
                          file, so `history.pushState` routes survive a reload.
        html_postprocess: Applied to the bytes of every ``.html`` response — the
                          dev server injects its reload script through this.
        routes:           Extra JSON endpoints, path → zero-arg callable returning
                          a JSON-serialisable dict. Checked before the token so
                          the dev reload endpoint keeps its fixed path.
    """
    root = frontend_dir

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

        def _send(self, status: int, body: bytes = b"", content_type: str | None = None) -> None:
            self.send_response(status)
            if content_type:
                self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def do_GET(self) -> None:
            path = self.path.split("?")[0]

            if routes and path in routes:
                body = json.dumps(routes[path]()).encode()
                self._send(200, body, "application/json")
                return

            if token is not None:
                prefix = "/" + token
                if path != prefix and not path.startswith(prefix + "/"):
                    self._send(403)
                    return
                path = path[len(prefix):] or "/"

            if path == "/":
                path = "/index.html"

            # Percent-decode before resolving, so the traversal check below sees the
            # same path the filesystem will. Decoding after would let %2e%2e slip past.
            path = urllib.parse.unquote(path)

            file_path = root / path.lstrip("/")

            # Confine every request to the frontend directory. resolve() collapses
            # ".." segments and follows symlinks, so this covers both a crafted URL
            # and a symlink inside the project pointing somewhere else.
            try:
                resolved = file_path.resolve()
                resolved.relative_to(root.resolve())
            except (ValueError, OSError):
                self._send(403)
                return

            file_path = resolved

            if not file_path.is_file():
                # An extensionless miss is an SPA route, not a missing asset.
                if spa_fallback and not Path(path).suffix:
                    file_path = (root / "index.html").resolve()
                if not file_path.is_file():
                    self._send(404)
                    return

            self._serve_file(file_path)

        def _serve_file(self, file_path: Path) -> None:
            content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

            # HTML is rewritten in one piece (the dev server injects its reload
            # script), and is small enough that holding it costs nothing. It is
            # also never range-requested.
            if file_path.suffix == ".html" and html_postprocess is not None:
                self._send(200, html_postprocess(file_path.read_bytes()), content_type)
                return

            try:
                size = file_path.stat().st_size
            except OSError:
                self._send(404)
                return

            span = parse_range(self.headers.get("Range"), size)

            if span is False:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

            if span is None:
                start, end = 0, size - 1
                status = 200
            else:
                start, end = span
                status = 206

            length = end - start + 1

            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            # Advertised on every file response, not just partial ones: a <video>
            # element checks this before it will let the user seek at all.
            self.send_header("Accept-Ranges", "bytes")
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()

            self._stream(file_path, start, length)

        def _stream(self, file_path: Path, start: int, length: int) -> None:
            try:
                with file_path.open("rb") as handle:
                    handle.seek(start)
                    remaining = length
                    while remaining > 0:
                        block = handle.read(min(_CHUNK_BYTES, remaining))
                        if not block:
                            break
                        self.wfile.write(block)
                        remaining -= len(block)
            except (BrokenPipeError, ConnectionResetError):
                # A media element that seeks away abandons the response mid-flight.
                # Routine, and there is nobody left to tell.
                pass

    return _Handler


def start(
    frontend_dir: Path,
    *,
    token: str | None = None,
    spa_fallback: bool = True,
    host: str = "127.0.0.1",
) -> tuple[http.server.HTTPServer, str]:
    """
    Serve *frontend_dir* on an ephemeral loopback port in a daemon thread.

    Returns the server (call ``shutdown()`` + ``server_close()`` to stop it) and
    the base URL, token included when one was given.
    """
    handler = make_static_handler(frontend_dir, token=token, spa_fallback=spa_fallback)
    # Threaded, not http.server.HTTPServer, and the distinction is not academic.
    # A single-threaded server handles one connection at a time to completion, so
    # a `<video>` streaming a ranged response holds the whole server for as long as
    # it plays — thumbnails, other media and the SDK itself all stall behind it.
    # An idle connection is worse: browsers routinely open sockets speculatively
    # and send nothing, and the handler blocks in readline() with no timeout, so
    # serve_forever never returns to notice shutdown() and the app hangs on exit.
    # ThreadingHTTPServer sets daemon_threads, so shutdown does not wait on them.
    server = http.server.ThreadingHTTPServer((host, 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    base = f"http://{host}:{server.server_address[1]}"
    if token is not None:
        base += f"/{token}"
    return server, base
