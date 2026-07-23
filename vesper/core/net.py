"""
File download with progress, generalised out of the updater.

The updater has always known how to fetch a binary with progress events and
verify its checksum; this module is that machinery with a caller-chosen
destination, so apps can download any file to a scope-validated path. It is
deliberately *not* an HTTP client — no headers, sessions, or JSON. For general
HTTP, use the vesper-http plugin; this exists for the one case a proxy fits
badly: large files that should stream to disk with progress, not through JSON.
"""
from __future__ import annotations

import urllib.request
from collections.abc import Callable
from pathlib import Path

from vesper.core.fs_scope import FsScope

# Applied to the connection and to every read, so a stalled network raises
# instead of hanging the caller forever. urllib's default is no timeout at all —
# a download to an unreachable host would block indefinitely with no progress and
# no error, which is exactly the failure a desktop app must not inflict on a user
# who clicked a button. This bounds *inactivity*, not total time: a slow but
# steady download is never interrupted, only one that goes quiet.
DEFAULT_TIMEOUT = 30.0

_CHUNK_BYTES = 64 * 1024


def fetch(
    url: str,
    dest: str,
    on_progress: Callable[[int], None] | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> None:
    """
    Stream *url* to *dest*, reporting integer percentages 0–100.

    The transport primitive shared with the updater; no scope, no checksum —
    callers own their destination policy. Streamed in blocks so a large file
    never becomes a large allocation, and read under a timeout so a dead
    connection surfaces as an error rather than a hang.
    """
    request = urllib.request.Request(url, headers={"User-Agent": "vesper"})
    last_percent = -1
    with urllib.request.urlopen(request, timeout=timeout) as response:
        total = int(response.headers.get("Content-Length") or 0)
        read = 0
        with open(dest, "wb") as out:
            while True:
                chunk = response.read(_CHUNK_BYTES)
                if not chunk:
                    break
                out.write(chunk)
                read += len(chunk)
                if on_progress and total > 0:
                    percent = min(100, int(read * 100 / total))
                    if percent != last_percent:
                        last_percent = percent
                        on_progress(percent)

    # Guarantee a final 100% even when the length was unknown or rounding stopped
    # short, so a caller wiring a progress bar always sees it complete.
    if on_progress and last_percent < 100:
        on_progress(100)


def download(
    url: str,
    dest: str,
    on_progress: Callable[[int], None] | None = None,
    expected_sha256: str = "",
    *,
    scope: FsScope | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """
    Download *url* to *dest*, optionally verifying its SHA-256.

    The destination passes through the filesystem scope like every other
    frontend-reachable write. On checksum mismatch the file is deleted before
    raising — a failed verification must not leave the bad artifact behind
    looking like a finished download.

    Returns the destination path.
    """
    dest_path = Path(scope.check(dest) if scope else Path(dest))
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    fetch(url, str(dest_path), on_progress, timeout=timeout)

    if expected_sha256:
        # Lazy import: updater imports this module at load, so the reverse
        # import has to wait until call time to avoid a cycle.
        from vesper.core.updater import verify_checksum

        if not verify_checksum(str(dest_path), expected_sha256):
            dest_path.unlink(missing_ok=True)
            raise ValueError("Downloaded file failed checksum verification.")

    return str(dest_path)
