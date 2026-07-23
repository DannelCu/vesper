# Playing Video (and why some files refuse)

Put a `.mp4` in a Vesper app and it plays. Put a `.avi` next to it and nothing happens
— no error, no picture, just a dead player. The file is fine; VLC opens it. The
problem is that your app's UI is **a browser**, and browsers do not play everything.

This recipe covers what plays, what does not, why, and the two things you can do
about it. The working implementation is [`examples/media-vault`](../../examples/media-vault).

## Why this happens: it is web technology

A Vesper window is a real WebView — WebKit on Linux and macOS, Edge/Chromium on
Windows. Your `<video>` element is the same one a web page uses, and it is bound by
the same rules a web page is. Those rules are narrow **on purpose**: browsers ship
codecs they can license and keep patched, not every codec ever written.

Two separate things have to be supported, and people usually conflate them:

- **The container** — `.mp4`, `.webm`, `.mkv`, `.avi`. The envelope holding the
  streams.
- **The codecs inside** — H.264, VP9, AAC, MP3, DivX. How the picture and sound are
  actually encoded.

A file fails if *either* is unsupported. This is why a `.mp4` can still refuse to
play: an mp4 containing H.265/HEVC is an unsupported codec in a supported container.

### What you can rely on

| Container | Codecs | Support |
|---|---|---|
| `.mp4`, `.m4v` | H.264 video + AAC audio | **Everywhere.** The safe default. |
| `.webm` | VP8/VP9 + Vorbis/Opus | Everywhere. |
| `.ogv` | Theora + Vorbis | Everywhere, rarely worth using. |
| `.mov` | H.264 + AAC | Usually — it is an mp4 relative. |
| `.mkv` | anything | **Unreliable.** Depends on the platform's GStreamer/Media Foundation plugins. |
| `.avi`, `.wmv`, `.flv`, `.mpg`, `.ts`, `.3gp` | — | **No.** Not web formats. |
| any container | H.265/HEVC, AV1 | Patchy; do not depend on it. |

On Linux there is an extra wrinkle: WebKitGTK decodes through **GStreamer**, so what
plays depends on which plugin packages the user has installed. A machine missing
`gstreamer1.0-libav` will refuse H.264 in an mp4 that works fine elsewhere. You cannot
detect this from the page, which is the strongest argument for the approach below.

## The wrong fix: hiding the files

The tempting response is to filter your library to formats you know play. Do not.
The user has a video, they can see it in their file manager, and your app pretending
it does not exist is worse than an honest "this needs converting". A media app that
silently drops half a folder looks broken.

## The fix: transcode on demand with ffmpeg

Convert the unsupported file into an mp4 the WebView can play, cache the result, and
play that. ffmpeg is the tool; it is an external binary, so treat it as optional and
degrade when it is missing.

Split your known video extensions in two — the ones the browser plays directly, and
the ones that need converting first:

```python
WEB_VIDEO_SUFFIXES = {".mp4", ".webm", ".ogv", ".m4v", ".mov"}
OTHER_VIDEO_SUFFIXES = {".avi", ".mkv", ".wmv", ".flv", ".mpg", ".mpeg", ".ts", ".3gp"}
VIDEO_SUFFIXES = WEB_VIDEO_SUFFIXES | OTHER_VIDEO_SUFFIXES
```

Index **both**, and tell the frontend which is which, so the UI can offer "Play" or
"Convert & Play" rather than a button that does nothing:

```python
item = {
    "name": entry.name,
    "path": str(entry),
    "web_playable": entry.suffix.lower() in WEB_VIDEO_SUFFIXES,
}
```

Then the conversion itself:

```python
@app.command("media:transcode")
def transcode(path: str) -> str:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("Playing this format needs ffmpeg to convert it first.")

    source = app.fs_scope.check(path)
    target = cache_dir / (source.stem + ".mp4")

    if not target.is_file():                      # cache: convert once
        argv = [
            "ffmpeg", "-y", "-i", str(source),
            "-c:v", "libx264",                    # the codec browsers agree on
            "-preset", "veryfast",
            "-c:a", "aac",
            "-movflags", "+faststart",            # see below — this one matters
            str(target),
        ]
        result = process.run(argv, scope=app.shell_scope, timeout=1800)
        if result["code"] != 0:
            target.unlink(missing_ok=True)
            raise RuntimeError("Conversion failed.")

    return f"{base_url}/{target.name}"
```

Three details worth keeping:

- **`-c:v libx264 -c:a aac`** — do not trust ffmpeg's defaults. Naming H.264 and AAC
  is what guarantees the output plays.
- **`-movflags +faststart`** moves the `moov` atom to the front of the file. Without
  it the player must download the whole file before it can seek, which throws away
  the byte-range serving you set up.
- **Cache the result.** Converting a feature film takes minutes; doing it twice is
  indefensible. Key the cache on the source name in a dot-folder beside the library.

### Report progress, or it looks frozen

A transcode is long enough that a silent button reads as a hang. `process.run` takes
an `on_output` callback that streams stdout line by line while the process runs; ask
ffmpeg for machine-readable progress and turn it into a percentage:

```python
duration = probe_duration(source)          # ffprobe, once

def on_output(line: str) -> None:
    if not line.startswith("out_time=") or duration <= 0:
        return
    stamp = line.split("=", 1)[1].strip()   # HH:MM:SS.microseconds
    try:
        hours, minutes, seconds = stamp.split(":")
        elapsed = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except ValueError:
        return                              # "N/A" before the first frame
    app.emit("transcode:progress", {"percent": min(99, int(elapsed / duration * 100))})

argv = [..., "-progress", "pipe:1", "-nostats", str(target)]
process.run(argv, scope=app.shell_scope, timeout=1800, on_output=on_output)
```

The frontend turns those events into a live label on the button that started it:

```js
button.disabled = true;
button.textContent = "Converting… 0%";

vesper.on("transcode:progress", ({ percent }) => {
  button.textContent = `Converting… ${percent}%`;
});
```

### Keep the shell scope tight

`process.run` needs a [`ShellScope`](../process.md), and it is worth writing a real
allowlist rather than `"*"`. Every argument must match a pattern, so listing the
suffixes and flags you actually use rejects anything else — `ffmpeg -f mp3 /etc/passwd`
does not get through:

```python
shell_scope={
    "ffmpeg": [
        "-y", "-i", "-c:v", "libx264", "-preset", "veryfast",
        "-c:a", "aac", "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats",
        "*.avi", "*.mkv", "*.mp4", ...          # inputs and outputs
    ],
}
```

## Seeking needs a server, not just a codec

Even a perfectly supported mp4 has a dead scrub bar when loaded over `file://`.
Seeking is an HTTP feature: the browser asks for `bytes=1234-5678` and the server
answers `206 Partial Content`. `file://` is not HTTP, so there is no request to make.

Serve the media over the loopback server and the seek bar comes alive:

```python
app = App(serve_frontend=True)                      # for the app's own files
server, base_url = static_server.start(library_dir, token=static_server.new_token())
```

Vesper's `static_server` speaks byte ranges and streams in blocks, so a 4 GB film does
not become 4 GB of memory. See [project-config.md](../project-config.md).

## When ffmpeg is missing

Do not disable the file quietly. Show it, disable its Play control, and say what would
fix it — the rule from [optional-features.md](../optional-features.md):

```js
if (item.web_playable) {
  return `<button data-act="play">Play</button>`;
}
if (features.ffmpeg) {
  return `<button data-act="convert">Convert &amp; Play</button>`;
}
return `<button disabled title="The browser can't play ${ext};
                install ffmpeg to convert it">Play</button>`;
```

## Why this is not in the core

Vesper could ship `video.transcode()`, and deliberately does not. It would put a
hard dependency on an external binary behind a core API, and every app wants different
answers to the questions that actually matter: convert eagerly or on demand, cache
where, at what quality, delete the cache when. Those are product decisions, not
framework ones — the "would core inclusion be overkill?" test in
[CONTRIBUTING.md](../../CONTRIBUTING.md#where-a-feature-lives).

What the core *does* provide is everything the recipe needs: scoped process execution
with streamed progress ([process.md](../process.md)) and a range-serving static server
([project-config.md](../project-config.md)).

## See also

- [`examples/media-vault`](../../examples/media-vault) — this recipe, working.
- [process.md](../process.md) — `ShellScope` and `process.run(on_output=…)`.
- [media-capture.md](media-capture.md) — the other direction: camera and microphone.
- [optional-features.md](../optional-features.md) — degrading without a backend.
