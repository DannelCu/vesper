# Media Vault

A media library for a folder on your disk. Point it at a directory and it lists the
videos and images inside, with durations, resolutions and thumbnails, and plays the
videos in the app — with a working seek bar.

That seek bar is the reason this example exists. It is the difference between loading
a page from `file://` and serving it over HTTP, and it is not a detail you can read
about and really believe until you have dragged a scrub bar that does nothing.

---

## Running it

No Node.js needed — this is a vanilla project.

```bash
pip install -e ../..          # Vesper itself, from this repo
cd examples/media-vault
vesper dev
```

Optional, and the app runs fine without any of it:

```bash
# Thumbnails and duration/resolution metadata
sudo apt install ffmpeg       # macOS: brew install ffmpeg
                              # Windows: winget install Gyan.FFmpeg

# Auto-refresh when files appear in the library folder
pip install -e ../../plugins/vesper-watch

# Copying files to the system clipboard (Linux only; built in elsewhere)
sudo apt install xclip
```

---

## Test data

There is no login. The app asks you to choose a folder on first use.

**Use any folder with a video or two in it.** A folder with a mix of videos and
images shows the most: `~/Videos`, or a downloads folder.

**Nothing to hand?** Open any writable folder and press **Download sample clip** in
the toolbar. It fetches a small Creative Commons test video (~2 MB) straight into the
library and re-indexes, so you have something to play in about ten seconds.

The app writes thumbnails to a `.vault-thumbs/` subfolder inside the library, and
nothing else. Deleting a file goes to the system trash, never a permanent unlink.

---

## Guided tour

1. **On open** you get an empty view and a toolbar. Press **Open folder…** and pick a
   directory. A splash screen shows while it indexes.

2. **The grid fills in.** Each tile shows a name and, underneath, whatever metadata
   is available: duration, resolution and file size. Without ffmpeg you get the size
   only — the tiles still appear, and there is a yellow banner at the top saying why
   the rest is missing.

3. **Thumbnails appear one by one** a moment later, if ffmpeg is installed. They are
   generated on demand and cached, so the second visit to a folder is instant.

4. **Press Play on a video.** A player panel slides up at the bottom.
   **Now drag the scrub bar** — this is the thing to try. It seeks instantly, because
   the file is coming over `http://127.0.0.1` and the browser can ask for byte ranges.
   Load the same file over `file://` and the bar is dead: no HTTP, no ranges, no seek.

5. **Press "Open in own window."** The player detaches into a second native window
   while the library stays browsable in the first. The two windows share no
   JavaScript state; the main one hands the video over as an event.

6. **While a video plays the machine will not sleep.** The app holds a keep-awake
   request for exactly as long as something is playing, and drops it when you stop.
   If the machine suspends anyway — lid closed — playback pauses, and the status bar
   says so when you come back.

7. **Try the per-tile actions.**
   - **Duplicate** copies the file beside itself as `name (2).mp4`.
   - **Rename** opens an in-page field. Press <kbd>Enter</kbd> to confirm,
     <kbd>Esc</kbd> to cancel.
   - **Copy** puts the file on the system clipboard *as a file* — switch to Finder or
     Explorer and paste, and the file lands there.
   - **Trash** asks for confirmation and then moves the file to the system trash.

8. **Press Download sample clip** and watch two progress bars at once: one in the app,
   and one on the taskbar button or dock icon. Switch to another window and you can
   still see how far along it is, which is the point of taskbar progress.

9. **With `vesper-watch` installed**, drop a file into the library folder from your
   file manager. The grid refreshes by itself. Without it, press **Refresh**.

There are no keyboard shortcuts beyond the rename field's <kbd>Enter</kbd> and
<kbd>Esc</kbd>, and whatever the `<video>` element gives you (space to play/pause,
arrows to skip) once the player has focus.

---

## Vesper features on show

| In the app | Feature | Docs |
|---|---|---|
| The seek bar works at all | Production localhost server, `App(serve_frontend=True)` | [project-config.md](../../docs/project-config.md) |
| Indexing, duplicate, rename, trash | Scoped filesystem API | [filesystem.md](../../docs/filesystem.md) |
| Durations, resolutions, thumbnails | Scoped process execution (`ShellScope` over ffprobe/ffmpeg) | [process.md](../../docs/process.md) |
| Download sample clip | `net.download` with progress | [network.md](../../docs/network.md) |
| Progress on the taskbar/dock | Taskbar progress | [badge.md](../../docs/badge.md) |
| No sleep while playing; pause on suspend | Keep-awake and power events | [power.md](../../docs/power.md) |
| Choose folder, confirm delete | Native dialogs | [dialogs.md](../../docs/dialogs.md) |
| Detached player | Multi-window | [multiwindow.md](../../docs/multiwindow.md) |
| Splash during indexing | Splash screen | [splash.md](../../docs/splash.md) |
| Window size remembered between runs | Window state | [window-state.md](../../docs/window-state.md) |
| Second launch focuses the running app | Single instance | [single-instance.md](../../docs/single-instance.md) |
| "Downloaded X" toast | Notifications | [notifications.md](../../docs/notifications.md) |
| Copy button | File clipboard | [clipboard.md](../../docs/clipboard.md) |
| Auto-refresh on new files | `vesper-watch` plugin | [plugins.md](../../docs/plugins.md) |
| Every banner at the top of the window | Capability probing | [optional-features.md](../../docs/optional-features.md) |

### Why the localhost server, concretely

A `<video>` element will only offer a seek bar if the server says
`Accept-Ranges: bytes`, and it seeks by asking for `bytes=1234-5678`. `file://` is not
HTTP: there is no header to send and no request to make, so the browser downloads the
whole file and the scrub bar stays inert until it finishes — if it works at all.

Two servers are running here, for two different trees:

- `App(serve_frontend=True)` serves `frontend/` — the app's own HTML, CSS and JS.
- The app starts a second one, rooted at your chosen library folder, using the same
  `vesper.core.static_server`. That is what the `<video src>` points at.

Both bind to `127.0.0.1` on an ephemeral port behind a random per-session token. See
[`_serve_library` in app.py](app.py) and the threat model in
[project-config.md](../../docs/project-config.md).

---

## Without the optional pieces

| Missing | What you get instead | To enable |
|---|---|---|
| ffmpeg | No thumbnails — a ▶ placeholder tile. A banner explains it. | `apt install ffmpeg` / `brew install ffmpeg` |
| ffprobe (ships with ffmpeg) | No durations or resolutions; file size only. | as above |
| `vesper-watch` | The library does not refresh by itself; the **Refresh** button does. | `pip install -e ../../plugins/vesper-watch` |
| `xclip` (Linux) | The **Copy** button is disabled with a tooltip saying why. | `apt install xclip` |
| No trash backend | **Trash** reports an error instead of silently doing nothing — deleting is destructive, so Vesper refuses rather than pretends. | `pip install "vesper[trash]"` |

`vesper doctor` reports all of these, with the same install commands.

---

## Known limits

- **You cannot drag a file out of the window** into Finder or Explorer. The WebView
  does not expose the native drag cycle — see
  [KNOWN-ISSUES KI1](../../KNOWN-ISSUES.md). The **Copy** button is the supported
  substitute: it puts the real file on the clipboard, so pasting in a file manager
  works. The [drag-out recipe](../../docs/recipes/drag-out.md) covers the alternatives.

- **There is no native menu bar**, though this app wants one. `app.menu()` raises
  `AttributeError` on PyWebView 6.2.1 before the window opens, because Vesper reaches
  for `webview.MenuAction`, which lives in `webview.menu` rather than at the top
  level. Open folder and Refresh are in the toolbar instead. Reported as a finding;
  not worked around here, because an example that patched the framework to boot would
  teach the wrong lesson.

- **The filesystem scope is the home directory, not the library folder.** `fs_scope`
  is fixed when the `App` is constructed and the library is chosen at runtime, and
  Vesper offers no way to narrow a scope afterwards. The app enforces the tighter
  library boundary itself in [`_in_library`](app.py) — every command that touches a
  file goes through it — but the framework-level scope is wider than it should be.

- **No transcoding, no playlists, no subtitles.** The point is the plumbing, not
  competing with VLC.

---

## Files

| File | What is in it |
|---|---|
| [`app.py`](app.py) | All the Python. Start at the `App(...)` call — every option is commented — then read `_serve_library` for the seek story and `shell_scope` for the ffmpeg allowlist. |
| [`frontend/index.html`](frontend/index.html) | The library view and the inline rename dialog. |
| [`frontend/app.js`](frontend/app.js) | The frontend logic. `applyCapabilities()` is where every degradation is decided. |
| [`frontend/player.html`](frontend/player.html) | The detached player window — a separate document that receives its video over the event bus. |
| [`frontend/styles.css`](frontend/styles.css) | Plain CSS, no framework, no CDN. |
| [`vesper.toml`](vesper.toml) | Project metadata. |

Read `app.py` top to bottom; it is ordered the way the app runs.
