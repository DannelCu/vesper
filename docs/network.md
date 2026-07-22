# Network — File Downloads

`vesper.net.download` streams a file from a URL straight to disk, with progress events and optional checksum verification. It is the updater's download machinery generalised to a caller-chosen destination.

```js
const path = await vesper.net.download(
    "https://example.com/dataset.zip",
    "/home/user/my-app/dataset.zip",
    (percent) => progressBar.value = percent,
)
```

With integrity verification:

```js
await vesper.net.download(url, dest, onProgress, expectedSha256)
```

On a checksum mismatch the promise rejects **and the file is deleted** — a failed verification never leaves the bad artifact behind looking like a finished download.

---

## Scope

The destination passes through the app's `fs_scope` like every other write the frontend can reach. With a scope configured, a download outside the allowed roots rejects with `FsScopeError` before any bytes are fetched.

---

## This is not an HTTP client

Deliberately no headers, methods, sessions, or JSON — one job: large files to disk with progress, which is exactly the case that fits badly through a JSON proxy (Base64 inflation, memory spikes).

| Need | Use |
|---|---|
| Download a file to disk, with progress | `vesper.net.download` (this page) |
| REST calls, headers, auth, JSON | [vesper-http plugin](plugins.md#vesper-http) |
| Send file bytes into the page as a blob | [File Transfers](file-transfers.md) |

---

## Python API

```python
from vesper.core import net

net.download(
    "https://example.com/f.zip",
    "/data/f.zip",
    on_progress=lambda pct: print(pct),
    expected_sha256="ab12...",       # optional
    scope=my_fs_scope,               # optional
)
```

The auto-updater consumes the same machinery (`net.fetch`) internally, so update downloads and file downloads share one implementation.
