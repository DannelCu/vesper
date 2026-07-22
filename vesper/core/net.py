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


def fetch(url: str, dest: str, on_progress: Callable[[int], None] | None = None) -> None:
    """
    Stream *url* to *dest*, reporting integer percentages 0–100.

    The transport primitive shared with the updater; no scope, no checksum —
    callers own their destination policy.
    """

    def _reporthook(block_num: int, block_size: int, total_size: int) -> None:
        if total_size > 0:
            percent = min(100, int(block_num * block_size * 100 / total_size))
            on_progress(percent)

    urllib.request.urlretrieve(
        url, dest, reporthook=_reporthook if on_progress else None
    )


def download(
    url: str,
    dest: str,
    on_progress: Callable[[int], None] | None = None,
    expected_sha256: str = "",
    *,
    scope: FsScope | None = None,
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

    fetch(url, str(dest_path), on_progress)

    if expected_sha256:
        # Lazy import: updater imports this module at load, so the reverse
        # import has to wait until call time to avoid a cycle.
        from vesper.core.updater import verify_checksum

        if not verify_checksum(str(dest_path), expected_sha256):
            dest_path.unlink(missing_ok=True)
            raise ValueError("Downloaded file failed checksum verification.")

    return str(dest_path)
