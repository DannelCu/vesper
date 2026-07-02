# Auto-Updates

Vesper supports manifest-based self-updates. The app checks a remote JSON manifest, downloads a new binary if one is available, and replaces itself.

---

## Configuration

```python
app = App(
    title="My App",
    frontend="dist/index.html",
    update_url="https://example.com/releases/manifest.json",
    version="1.0.0",
)
```

`update_url` and `version` enable the auto-update built-ins. Both are required to activate the feature.

---

## Manifest format

Host a JSON file at `update_url` on any static server (S3, GitHub Releases, Cloudflare R2, etc.):

```json
{
  "version": "1.2.0",
  "notes": "Bug fixes and performance improvements.",
  "platforms": {
    "win32":  "https://example.com/releases/myapp-1.2.0.exe",
    "darwin": "https://example.com/releases/myapp-1.2.0",
    "linux":  "https://example.com/releases/myapp-1.2.0"
  }
}
```

- `version` — the new version string (compared to the running app's `version`)
- `notes` — release notes to display to the user
- `platforms` — download URLs keyed by `sys.platform` (`win32`, `darwin`, `linux`)

If the manifest's `version` is greater than the running `version`, an update is available. If the manifest does not have an entry for the current platform, no update is offered.

---

## Checking for updates

**From JavaScript:**

```js
const update = await vesper.invoke("vesper:update:check")
if (update) {
    console.log(`Update available: ${update.version}`)
    console.log(update.notes)
    // update.download_url
}
// null if already up to date or no platform entry in manifest
```

**From Python:**

```python
result = app.check_update()
# {'version': '1.2.0', 'notes': '...', 'download_url': '...'}
# or None if up to date
```

---

## Downloading the update

```js
// Stream download progress
vesper.on("update-progress", ({ percent }) => {
    progressBar.style.width = percent + "%"
})

const path = await vesper.invoke("vesper:update:download", {
    url: update.download_url
})
// path is a temp file path to the downloaded binary
```

**From Python:**

```python
def on_progress(percent: int):
    app.emit("update-progress", {"percent": percent})

path = app.download_update(update["download_url"], on_progress=on_progress)
```

---

## Installing the update

```js
await vesper.invoke("vesper:update:install", { path })
// App restarts immediately — no response is returned
```

**From Python:**

```python
app.install_update(path)
# Replaces sys.executable and restarts the process
```

`install_update` is destructive and immediate:
- **POSIX** (macOS, Linux): uses `os.execv` to replace the current process
- **Windows**: writes and launches a `.bat` swap script as a detached process, then exits

The app restarts automatically. This only works correctly in a packaged app (`vesper package`) — running from source with `python app.py` will not replace the right binary.

---

## Full update flow (JavaScript)

```js
async function checkForUpdates() {
    const update = await vesper.invoke("vesper:update:check")
    if (!update) {
        alert("You are up to date.")
        return
    }

    const confirmed = confirm(
        `Version ${update.version} is available.\n\n${update.notes}\n\nDownload and install now?`
    )
    if (!confirmed) return

    vesper.on("update-progress", ({ percent }) => {
        document.getElementById("progress").textContent = `Downloading… ${percent}%`
    })

    const path = await vesper.invoke("vesper:update:download", {
        url: update.download_url
    })

    document.getElementById("progress").textContent = "Installing…"
    await vesper.invoke("vesper:update:install", { path })
    // App restarts — execution stops here
}
```

---

## Versioning

Vesper compares version strings using Python's `packaging.version.Version` (semantic versioning). The manifest's `version` must be strictly greater than the running `version` to trigger an update. Pre-release versions (e.g. `1.0.0a1`) are supported.

---

## Security note

Always serve the manifest and binaries over HTTPS. Code signing (`vesper sign`) is strongly recommended so the OS verifies the downloaded binary before execution. See [Code Signing](code-signing.md).
