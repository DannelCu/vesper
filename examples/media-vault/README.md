# Media Vault

A media library for a folder on your disk. Point it at a directory and it lists the
videos and images inside, with durations, resolutions and thumbnails, and plays the
videos in the app — with a working seek bar.

That seek bar is the reason this example exists. It is the difference between loading
a page from `file://` and serving it over HTTP, and it is not a detail you can read
about and really believe until you have dragged a scrub bar that does nothing.

The second reason is the one nobody warns you about: **your app's UI is a browser, so
it will not play every video file.** A `.avi` that VLC opens without complaint shows
nothing at all. This app indexes those files anyway and converts them on demand —
see [Why some videos need converting](#why-some-videos-need-converting).

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
# Thumbnails, duration/resolution metadata, converting non-web formats,
# and generating the sample clip. The one worth installing.
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
images shows the most: `~/Videos`, or a downloads folder. A folder with a `.avi` or
`.mkv` in it shows the conversion path as well.

**Nothing to hand?** Open any writable folder and press **Generate sample clip**. It
synthesises a 30-second test video with ffmpeg — locally, offline, in a few seconds —
and re-indexes so you have something to play.

> It generates rather than downloads on purpose. This button used to fetch a clip from
> a public bucket; that URL now answers `403`, which broke the example for everyone.
> An example that depends on a third-party URL staying up is an example that breaks.

The app writes thumbnails to `.vault-thumbs/` and converted copies to
`.vault-transcodes/`, both inside the library folder, and nothing else. Deleting a
file goes to the system trash, never a permanent unlink.

The filesystem scope starts empty — before you open a folder, every path is refused —
and narrows to exactly the folder you pick. Try it: with a library open, nothing
outside it is reachable, including its own parent directory.

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

   Tiles for `.avi`, `.mkv`, `.wmv` and friends show **Convert & Play** instead of
   Play, because the WebView cannot open those. Press it and the button becomes a live
   `Converting… 42%` — real progress parsed from ffmpeg — then plays the converted
   copy, seek bar and all. The result is cached in `.vault-transcodes/`, so the second
   time is instant. Without ffmpeg the button is disabled and says what would fix it.

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

8. **Use the Library menu** in the native menu bar — Open Folder and Refresh are
   there too, and Quit closes the app including the detached player window.

9. **Press Generate sample clip** and watch two progress bars at once: one in the app,
   and one on the taskbar button or dock icon. Switch to another window and you can
   still see how far along it is, which is the point of taskbar progress. Both are fed
   by the same ffmpeg progress stream.

10. **With `vesper-watch` installed**, drop a file into the library folder from your
   file manager. The grid refreshes by itself. Without it, press **Refresh**.

There are no keyboard shortcuts beyond the rename field's <kbd>Enter</kbd> and
<kbd>Esc</kbd>, and whatever the `<video>` element gives you (space to play/pause,
arrows to skip) once the player has focus.

---

## Vesper features on show

| In the app | Feature | Docs |
|---|---|---|
| The seek bar works at all | Production localhost server, `App(serve_frontend=True)` | [project-config.md](../../docs/project-config.md) |
| Indexing, duplicate, rename, trash | Scoped filesystem API, narrowed to the chosen folder at runtime | [filesystem.md](../../docs/filesystem.md) |
| Durations, resolutions, thumbnails | Scoped process execution (`ShellScope` over ffprobe/ffmpeg) | [process.md](../../docs/process.md) |
| `Converting… 42%` on the button | Streamed process output, `process.run(on_output=…)` | [process.md](../../docs/process.md) |
| Playing a `.avi` at all | Transcoding on demand | [video-playback.md](../../docs/recipes/video-playback.md) |
| Progress on the taskbar/dock | Taskbar progress | [badge.md](../../docs/badge.md) |
| No sleep while playing; pause on suspend | Keep-awake and power events | [power.md](../../docs/power.md) |
| Choose folder, confirm delete | Native dialogs | [dialogs.md](../../docs/dialogs.md) |
| Detached player | Multi-window | [multiwindow.md](../../docs/multiwindow.md) |
| Splash during indexing | Splash screen | [splash.md](../../docs/splash.md) |
| Window size remembered between runs | Window state | [window-state.md](../../docs/window-state.md) |
| Second launch focuses the running app | Single instance | [single-instance.md](../../docs/single-instance.md) |
| "Created X" toast | Notifications | [notifications.md](../../docs/notifications.md) |
| Copy button | File clipboard | [clipboard.md](../../docs/clipboard.md) |
| Auto-refresh on new files | `vesper-watch` plugin | [plugins.md](../../docs/plugins.md) |
| Library and Help menus | Native menu bar | [menu.md](../../docs/menu.md) |
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

## Why some videos need converting

Open a folder holding `Movie.avi` and this app lists it — but the Play button says
**Convert & Play**. That is not a limitation of Vesper. It is what your UI *is*.

A Vesper window is a real WebView — WebKit on Linux and macOS, Edge/Chromium on
Windows — and the `<video>` element in it is the same one a web page uses, bound by
the same rules. Browsers ship the codecs they can license and keep patched, not every
codec ever written. **It is web technology, so it plays web formats.**

Two things have to be supported, and they are easy to conflate:

- **The container** — `.mp4`, `.webm`, `.mkv`, `.avi`: the envelope holding the streams.
- **The codecs inside** — H.264, VP9, AAC, DivX: how picture and sound are encoded.

Either one being unsupported kills playback, which is why even a `.mp4` can refuse to
play if it holds H.265/HEVC.

| What it is | Plays directly? |
|---|---|
| `.mp4` / `.m4v` with H.264 + AAC | **Yes** — the safe default everywhere |
| `.webm` (VP8/VP9), `.ogv` (Theora) | Yes |
| `.mov` with H.264 | Usually — an mp4 relative |
| `.mkv` | Unreliable; depends on the platform's codec plugins |
| `.avi`, `.wmv`, `.flv`, `.mpg`, `.ts`, `.3gp` | **No** — not web formats |
| Anything in H.265/HEVC or AV1 | Patchy; do not depend on it |

On Linux there is an extra wrinkle: WebKitGTK decodes through **GStreamer**, so what
plays depends on which plugin packages are installed. A machine without
`gstreamer1.0-libav` refuses H.264 that works fine elsewhere.

### What this app does about it

The tempting response is to filter the library down to formats that work. This app
does not, because a user who can see `Movie.avi` in their file manager is not helped
by an app pretending it does not exist.

Instead it indexes every known video format and splits them in two — the ones the
browser plays directly, and the ones needing conversion first
(`WEB_VIDEO_SUFFIXES` / `OTHER_VIDEO_SUFFIXES` at the top of [`app.py`](app.py)). The
index marks each item `web_playable`, and the UI offers the honest control:

- **web-playable** → **Play**, straight from the loopback server.
- **needs converting, ffmpeg present** → **Convert & Play**. ffmpeg re-encodes to
  H.264/AAC mp4 with `-movflags +faststart` (so the converted copy still seeks),
  caches it in `.vault-transcodes/`, and plays that. Progress is parsed from ffmpeg's
  own `-progress` stream and shown live on the button.
- **needs converting, no ffmpeg** → **Play, disabled**, with a tooltip saying the
  browser cannot play that format and ffmpeg would convert it.

Nothing is ever offered that would silently do nothing. The full pattern, including
the `ShellScope` allowlist and the progress parsing, is written up as a recipe:
[Playing Video](../../docs/recipes/video-playback.md).

---

## Without the optional pieces

| Missing | What you get instead | To enable |
|---|---|---|
| ffmpeg | No thumbnails — a ▶ placeholder tile. A banner explains it. | `apt install ffmpeg` / `brew install ffmpeg` |
| ffmpeg, for `.avi`/`.mkv`/… | Those files are still listed, but Play is disabled with a tooltip saying the browser cannot play the format and ffmpeg would convert it. | as above |
| ffmpeg, for the sample clip | **Generate sample clip** reports that it needs ffmpeg instead of doing nothing. | as above |
| ffprobe (ships with ffmpeg) | No durations or resolutions; file size only. Conversion still works, but its progress bar cannot show a percentage without a known duration. | as above |
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

- **Renaming uses an in-page field, not a native dialog.** Vesper's dialogs are file
  pickers and yes/no boxes; there is no native text prompt, because PyWebView does not
  expose one — and `window.prompt()` does not exist inside a WebView either. See
  [KNOWN-ISSUES KI7](../../KNOWN-ISSUES.md).

- **Formats the WebView cannot play are converted, not played directly.** This is a
  property of building UI on web technology, not a Vesper bug — the full explanation is
  in [Why some videos need converting](#why-some-videos-need-converting) and the
  [Playing Video recipe](../../docs/recipes/video-playback.md). Conversion needs ffmpeg
  and takes real time on a long film; the result is cached so it happens once.

- **No playlists, no subtitles.** Subtitles would also need
  `gstreamer1.0-plugins-bad` on Linux — WebKit logs a warning about a missing WebVTT
  encoder at startup, which is harmless and unrelated to playback. The point here is
  the plumbing, not competing with VLC.

---

## Files

| File | What is in it |
|---|---|
| [`app.py`](app.py) | All the Python. Start at the `App(...)` call — every option is commented — then read the suffix sets at the top for the format story, `_serve_library` for the seek story, `transcode` for the conversion, and `shell_scope` for the ffmpeg allowlist. |
| [`frontend/index.html`](frontend/index.html) | The library view and the inline rename dialog. |
| [`frontend/app.js`](frontend/app.js) | The frontend logic. `applyCapabilities()` is where every degradation is decided; `playButton()` is where a file's format decides its control. |
| [`frontend/player.html`](frontend/player.html) | The detached player window — a separate document that receives its video over the event bus, and pulls the current selection on load in case it missed the event. |
| [`frontend/styles.css`](frontend/styles.css) | Plain CSS, no framework, no CDN. |
| [`vesper.toml`](vesper.toml) | Project metadata. |

Read `app.py` top to bottom; it is ordered the way the app runs.
