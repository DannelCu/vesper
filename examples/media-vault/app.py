"""
Media Vault — a media library with an in-app video player.

The point of this example is the production localhost server. A <video> element
loading from file:// cannot seek: seeking needs HTTP byte ranges, and file://
has no HTTP. Serving the library over 127.0.0.1 gives the player a real seek
bar. See the README for the full explanation.

Everything here degrades: without ffmpeg there are no thumbnails or durations,
without vesper-watch the library does not auto-refresh, and the app opens and
plays video either way. That is deliberate — it is the contract in
docs/optional-features.md, demonstrated rather than described.

Run with `vesper dev` from this directory.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from vesper import App
from vesper.core import process, static_server

# Files we offer to index. Anything else in the folder is ignored rather than
# listed as "unknown" — a library view full of .DS_Store helps nobody.
#
# Two classes of video. The browser's <video> element only plays a handful of
# formats; the rest are real videos it cannot open, so listing them and pretending
# Play works would be the lie these examples avoid. They are indexed all the same
# and transcoded to mp4 on demand (vault:transcode), so a .avi in the library is
# a video you can watch, not a video that silently vanishes.
WEB_VIDEO_SUFFIXES = {".mp4", ".webm", ".ogv", ".m4v", ".mov"}
OTHER_VIDEO_SUFFIXES = {".avi", ".mkv", ".wmv", ".flv", ".mpg", ".mpeg", ".ts", ".m2ts", ".3gp"}
VIDEO_SUFFIXES = WEB_VIDEO_SUFFIXES | OTHER_VIDEO_SUFFIXES
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
MEDIA_SUFFIXES = VIDEO_SUFFIXES | IMAGE_SUFFIXES

# One glob per known video suffix, for the shell scope below — ffmpeg and ffprobe
# must be allowed to read every format the library indexes, transcoding included.
_VIDEO_GLOBS = sorted(f"*{suffix}" for suffix in VIDEO_SUFFIXES)

THUMB_DIR_NAME = ".vault-thumbs"
TRANSCODE_DIR_NAME = ".vault-transcodes"


# ── Optional plugins ─────────────────────────────────────────────────────────
#
# Imported defensively so the app runs on a machine with none of them. The UI
# asks vesper.capabilities() and its own vault:features command to decide what
# to show, so a missing plugin removes a button rather than breaking a screen.

plugins = []
HAS_WATCH = False
try:
    from vesper_watch import WatchPlugin

    plugins.append(WatchPlugin(debounce=0.4))
    HAS_WATCH = True
except ImportError:
    pass


app = App(
    title="Media Vault",
    width=1180,
    height=760,
    min_width=880,
    min_height=560,
    frontend="frontend/index.html",
    debug=True,
    plugins=plugins,
    # Serve the frontend over HTTP rather than file://. Required here for the
    # same reason as the media itself, and the reason the library server below
    # exists at all.
    serve_frontend=True,
    remember_window=True,
    single_instance=True,
    power_events=True,
    # An empty list, not None: None means "no scope, check nothing", while a
    # scope with no roots refuses every path. Nothing should be readable before
    # a library is open. open_library() then narrows it to the chosen folder
    # with app.fs_scope.set_roots(), so the frontend can never reach outside the
    # library the user actually picked.
    fs_scope=[],
    # The canonical allowlist case: two binaries and nothing else, and each only
    # with the arguments this app actually uses.
    #
    # The patterns are deliberately tighter than a bare "*". Allowing "*" would
    # let every argument through and reduce the scope to "which binaries" —
    # `ffmpeg -f mp3 out.mp3` would pass. Listing the media suffixes instead
    # rejects any invocation that is not thumbnailing or probing, which is the
    # point of having patterns rather than a plain list of binaries.
    shell_scope={
        "ffprobe": [
            "-v", "error", "-show_entries",
            "format=duration:stream=width,height", "-of", "json",
            *_VIDEO_GLOBS,
        ],
        "ffmpeg": [
            # Thumbnailing: one frame, scaled.
            "-y", "-ss", "1", "-i", "-vframes", "-vf", "scale=320:-1",
            # Transcoding a non-web format to a web-playable mp4, with a
            # machine-readable progress stream on stdout.
            "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac",
            "-movflags", "+faststart", "-progress", "pipe:1", "-nostats",
            # Synthesising the sample clip from ffmpeg's own generators. "-f" is
            # only ever paired with "lavfi" — no other value is listed, so
            # `ffmpeg -f mp3 …` is still rejected.
            "-f", "lavfi", "-shortest", "testsrc=*", "sine=*",
            # Inputs (every indexed video) and outputs (.jpg thumb, .mp4 result).
            *_VIDEO_GLOBS, "*.jpg",
        ],
    },
)


# ── Library state ────────────────────────────────────────────────────────────

state: dict = {
    "root": None,        # Path of the chosen library folder
    "server": None,      # its loopback file server
    "base_url": None,    # …and the URL the player loads from
    "now_playing": None, # what the detached player window should show
}


def _in_library(path: str) -> Path:
    """
    Resolve *path* and require it to be inside the chosen library folder.

    This is the same boundary app.fs_scope enforces for the frontend's own
    vesper.fs calls; going through it here means the app's Python commands
    cannot be tricked into stepping outside it either.
    """
    if state["root"] is None:
        raise RuntimeError("No library folder is open yet.")
    return app.fs_scope.check(path)


def _serve_library(root: Path) -> str:
    """
    Start a loopback server rooted at the library folder and return its base URL.

    The framework's own static server, reused: it speaks byte ranges, so the
    player gets a working seek bar, and it streams rather than buffering, so a
    4 GB film does not become 4 GB of RSS.

    App(serve_frontend=True) serves the *frontend* directory, which is a
    different tree — the library lives wherever the user keeps it.
    """
    if state["server"] is not None:
        state["server"].shutdown()
        state["server"].server_close()

    server, base = static_server.start(root, token=static_server.new_token())
    state["server"] = server
    state["base_url"] = base
    return base


@app.on("close")
def _stop_library_server() -> None:
    """The library server lives and dies with the window, like the app's own."""
    if state["server"] is not None:
        state["server"].shutdown()
        state["server"].server_close()
        state["server"] = None


# ── ffprobe / ffmpeg, both optional ──────────────────────────────────────────


def _has(binary: str) -> bool:
    return shutil.which(binary) is not None


@app.command("vault:features")
def features() -> dict:
    """
    What this machine can do, for the UI to hide what it cannot.

    vesper.capabilities() covers the framework's own optional backends; these are
    this app's, and the frontend merges the two.
    """
    return {
        "ffprobe": _has("ffprobe"),
        "ffmpeg": _has("ffmpeg"),
        "watch": HAS_WATCH,
    }


def _probe(path: Path) -> dict:
    """
    Duration and resolution via ffprobe, or an empty dict without it.

    Not an error: a library with no metadata is still a usable library, so the
    caller renders the row either way.
    """
    if not _has("ffprobe"):
        return {}

    argv = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration:stream=width,height",
        "-of", "json", str(path),
    ]
    try:
        # Through the framework's runner, not subprocess directly: this is what
        # enforces the shell_scope allowlist declared on the App. Calling
        # subprocess here would work and would quietly bypass it.
        result = process.run(argv, scope=app.shell_scope, timeout=20)
        if result["code"] != 0:
            return {}
        data = json.loads(result["stdout"] or "{}")
    except (OSError, ValueError, process.ShellScopeError, subprocess.TimeoutExpired):
        return {}

    streams = data.get("streams") or [{}]
    duration = (data.get("format") or {}).get("duration")

    return {
        "duration": round(float(duration), 1) if duration else None,
        "width": streams[0].get("width"),
        "height": streams[0].get("height"),
    }


@app.command("vault:thumbnail")
def thumbnail(path: str) -> str | None:
    """
    Grab a frame one second in, cached beside the library.

    Returns a URL the frontend can use as an <img src>, or None when ffmpeg is
    absent — the caller shows a placeholder tile instead.
    """
    if not _has("ffmpeg"):
        return None

    source = _in_library(path)
    if source.suffix.lower() not in VIDEO_SUFFIXES:
        return None

    thumbs = state["root"] / THUMB_DIR_NAME
    thumbs.mkdir(exist_ok=True)
    target = thumbs / (source.stem + ".jpg")

    if not target.is_file():
        argv = [
            "ffmpeg", "-y", "-ss", "1", "-i", str(source),
            "-vframes", "1", "-vf", "scale=320:-1", str(target),
        ]
        try:
            process.run(argv, scope=app.shell_scope, timeout=30)
        except (OSError, process.ShellScopeError, subprocess.TimeoutExpired):
            return None

    if not target.is_file():
        return None
    return f"{state['base_url']}/{THUMB_DIR_NAME}/{target.name}"


@app.command("vault:transcode")
def transcode(path: str) -> str:
    """
    Convert a non-web video (.avi, .mkv, .wmv, …) to a web-playable mp4.

    The <video> element plays mp4/webm/ogv and nothing else, so a .avi in the
    library is a real video the browser cannot open. ffmpeg bridges that: the
    result is an H.264/AAC mp4 with the moov atom moved to the front (so it
    streams and seeks), cached beside the library like thumbnails, so the second
    Play is instant. Returns a URL the player can load.

    Raises without ffmpeg — there is no way to play the file otherwise, and
    saying so is better than a dead Play button. Web-native files never reach
    here; the frontend only calls this for the formats that need it.
    """
    if not _has("ffmpeg"):
        raise RuntimeError(
            "Playing this format needs ffmpeg to convert it first, and ffmpeg "
            "is not installed."
        )

    source = _in_library(path)
    if source.suffix.lower() not in OTHER_VIDEO_SUFFIXES:
        # Already web-playable — hand back the direct URL rather than transcoding.
        return f"{state['base_url']}/{source.name}"

    cache = state["root"] / TRANSCODE_DIR_NAME
    cache.mkdir(exist_ok=True)
    target = cache / (source.stem + ".mp4")

    if not target.is_file():
        # Total length, so the progress stream can be turned into a percentage.
        duration = _probe(source).get("duration") or 0

        def on_output(line: str) -> None:
            # ffmpeg -progress writes key=value lines; out_time is the position
            # reached so far as HH:MM:SS.microseconds. Percentage needs a known
            # duration — without one (ffprobe missing) the bar just stays at 0.
            if not line.startswith("out_time=") or duration <= 0:
                return
            stamp = line.split("=", 1)[1].strip()
            try:
                hours, minutes, seconds = stamp.split(":")
                elapsed = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            except ValueError:
                return  # "N/A" early in the run
            percent = max(0, min(99, int(elapsed / duration * 100)))
            app.emit("transcode:progress", {"path": path, "percent": percent})

        argv = [
            "ffmpeg", "-y", "-i", str(source),
            "-c:v", "libx264", "-preset", "veryfast",
            "-c:a", "aac", "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats",
            str(target),
        ]
        try:
            # A full-length film is a long job; the wide timeout is deliberate.
            result = process.run(argv, scope=app.shell_scope, timeout=1800,
                                  on_output=on_output)
        except (OSError, process.ShellScopeError, subprocess.TimeoutExpired) as error:
            target.unlink(missing_ok=True)
            raise RuntimeError(f"Conversion failed: {error}")
        if result["code"] != 0:
            target.unlink(missing_ok=True)
            raise RuntimeError("Conversion failed — see the console for ffmpeg's output.")

        app.emit("transcode:progress", {"path": path, "percent": 100})

    return f"{state['base_url']}/{TRANSCODE_DIR_NAME}/{target.name}"


# ── Opening and indexing a library ───────────────────────────────────────────


@app.command("vault:open_library")
def open_library(path: str) -> dict:
    """
    Point the vault at a folder: start its server and index what is inside.

    Returns the library root, the base URL the player loads from, and the items.
    """
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise RuntimeError(f"Not a folder: {path}")

    state["root"] = root
    # Narrow the filesystem scope to what the user just opened. Every
    # vesper.fs.* call from the frontend is now confined to this folder — before
    # a library is open the scope is empty and every path is refused.
    app.fs_scope.set_roots([str(root)])
    base = _serve_library(root)

    if HAS_WATCH:
        # Refresh on change instead of making the user press a button. The
        # plugin emits vesper:fs:changed; the frontend re-indexes on it.
        app.ipc.handle({
            "id": "watch", "command": "vesper:fs:watch",
            "args": {"path": str(root), "recursive": False},
        })

    return {"root": str(root), "base_url": base, "items": index_library()}


@app.command("vault:index")
def index_library() -> list[dict]:
    """
    List the media in the library with whatever metadata is available.

    Sorted by name so the view is stable between refreshes.
    """
    root = state["root"]
    if root is None:
        return []

    items = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_file() or entry.suffix.lower() not in MEDIA_SUFFIXES:
            continue

        stat = entry.stat()
        suffix = entry.suffix.lower()
        is_video = suffix in VIDEO_SUFFIXES
        item = {
            "name": entry.name,
            "path": str(entry),
            "url": f"{state['base_url']}/{entry.name}",
            "kind": "video" if is_video else "image",
            # Whether the <video> element can play it as-is. When False the file
            # is still a video — the frontend offers "Convert & Play", which goes
            # through vault:transcode. None for images.
            "web_playable": (suffix in WEB_VIDEO_SUFFIXES) if is_video else None,
            "size": stat.st_size,
            "modified": stat.st_mtime,
        }
        if is_video:
            item.update(_probe(entry))
        items.append(item)

    return items


# ── File operations, all inside the library ──────────────────────────────────


@app.command("vault:duplicate")
def duplicate(path: str) -> str:
    """Copy a file next to itself, finding a free "name (2).mp4" style name."""
    source = _in_library(path)
    target = source.with_name(f"{source.stem} (2){source.suffix}")
    counter = 2
    while target.exists():
        counter += 1
        target = source.with_name(f"{source.stem} ({counter}){source.suffix}")

    shutil.copy2(source, target)
    return str(target)


@app.command("vault:rename")
def rename(path: str, new_name: str) -> str:
    """
    Rename within the library.

    The new name is taken as a bare filename, never a path: a frontend that sent
    "../elsewhere.mp4" would otherwise move the file out of the library, and the
    scope check below would only catch it after the fact.
    """
    source = _in_library(path)
    target = _in_library(str(source.with_name(Path(new_name).name)))

    if target.exists():
        raise RuntimeError(f"Already exists: {target.name}")

    source.rename(target)
    return str(target)


@app.command("vault:trash")
def trash_item(path: str) -> bool:
    """
    Move a file to the system trash.

    fs.trash raises when no backend is available — deleting is destructive, so
    "nothing happened" would be worse than an error. The frontend surfaces it.
    """
    from vesper.core import fs

    target = _in_library(path)
    fs.trash(str(target), scope=app.fs_scope)
    return True


@app.command("vault:copy_to_clipboard")
def copy_to_clipboard(paths: list) -> bool:
    """
    Put files on the clipboard as files, so they paste into Finder/Explorer.

    Dragging out of the window would be the natural gesture, but the WebView does
    not expose the native drag cycle (KNOWN-ISSUES KI1). This is the supported
    substitute.
    """
    from vesper.core import clipboard

    return clipboard.write_files([str(_in_library(p)) for p in paths])


# ── Making a sample clip ─────────────────────────────────────────────────────
#
# Generated locally with ffmpeg rather than downloaded. An example that needs a
# working internet connection — and a third-party URL that stays up — is an
# example that breaks: the sample this once fetched from Google's public bucket
# now answers 403. ffmpeg synthesises the same thing offline, deterministically,
# with a real duration and audio track so the seek bar has something to seek.


@app.command("vault:generate_sample")
def generate_sample(seconds: int = 30) -> str:
    """
    Synthesise a sample clip into the library, reporting progress two ways.

    The taskbar/dock progress bar is the point: a long job is exactly the case
    where the user has switched to another window and wants to know from there.
    Progress comes from ffmpeg's own -progress stream via process.run(on_output=).
    """
    from vesper.core import badge

    root = state["root"]
    if root is None:
        raise RuntimeError("Open a library folder first.")
    if not _has("ffmpeg"):
        raise RuntimeError(
            "Generating a sample clip needs ffmpeg, which is not installed."
        )

    target = root / "sample-clip.mp4"

    def on_output(line: str) -> None:
        if not line.startswith("out_time="):
            return
        stamp = line.split("=", 1)[1].strip()
        try:
            hours, minutes, secs = stamp.split(":")
            elapsed = int(hours) * 3600 + int(minutes) * 60 + float(secs)
        except ValueError:
            return  # "N/A" before the first frame
        percent = max(0, min(99, int(elapsed / seconds * 100)))
        badge.set_progress(percent / 100)
        app.emit("sample:progress", {"percent": percent})

    argv = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size=1280x720:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-shortest", "-c:v", "libx264", "-preset", "veryfast",
        "-c:a", "aac", "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats",
        str(target),
    ]
    try:
        result = process.run(argv, scope=app.shell_scope, timeout=600,
                             on_output=on_output)
    except (OSError, process.ShellScopeError, subprocess.TimeoutExpired) as error:
        target.unlink(missing_ok=True)
        raise RuntimeError(f"Could not generate the sample: {error}")
    finally:
        badge.clear_progress()

    if result["code"] != 0:
        target.unlink(missing_ok=True)
        raise RuntimeError("ffmpeg could not generate the sample clip.")

    app.emit("sample:progress", {"percent": 100})

    from vesper.core import notify

    notify.send("Media Vault", f"Created {target.name}")
    return str(target)


# ── Playback: power behaviour ────────────────────────────────────────────────
#
# Two halves of the same idea. While a video plays the machine should not sleep,
# and if it sleeps anyway the video should not still be running on wake.


@app.command("vault:playback_started")
def playback_started() -> bool:
    from vesper.core import power

    return power.prevent_sleep("Playing video in Media Vault")


@app.command("vault:playback_stopped")
def playback_stopped() -> bool:
    from vesper.core import power

    return power.allow_sleep()


# ── Player window ────────────────────────────────────────────────────────────

player_window = app.register_window(
    title="Media Vault — Player",
    frontend="frontend/player.html",
    width=900,
    height=560,
)


@app.command("vault:open_player")
def open_player(url: str, name: str) -> bool:
    """
    Show the detached player and tell it what to play.

    The second window is a separate document with its own JS context, so the
    selection is handed over the event bus. Crucially the event goes to the
    player window — ``app.emit`` only reaches the main window, which is why the
    detach button did nothing at first. It is also stashed in state and served by
    ``vault:now_playing`` so the player can pull it on load, covering the race
    where the window finishes loading just after the event was dispatched.
    """
    state["now_playing"] = {"url": url, "name": name}
    player_window.show()
    player_window.emit("player:load", {"url": url, "name": name})
    return True


@app.command("vault:now_playing")
def now_playing() -> dict | None:
    """What the detached player should show — pulled by the player on load."""
    return state["now_playing"]


# ── Native menu ──────────────────────────────────────────────────────────────

from vesper.core.menu import MenuItem  # noqa: E402  (after app, by design)


def _open_docs() -> None:
    from vesper.core import shell

    shell.open_url("https://github.com/DannelCu/vesper")


app.menu([
    MenuItem("Library", submenu=[
        MenuItem("Open Folder…", lambda: app.emit("menu:open_folder", {})),
        MenuItem("Refresh", lambda: app.emit("menu:refresh", {})),
        None,                                   # separator
        MenuItem("Quit", lambda: app.quit()),
    ]),
    MenuItem("Help", submenu=[
        MenuItem("Vesper docs", _open_docs),
    ]),
])


app.splash(html="""
  <div style="font:600 18px system-ui;display:grid;place-items:center;
              height:100vh;background:#12131a;color:#e8e8ef">
    Media Vault — indexing…
  </div>
""", width=360, height=180)


if __name__ == "__main__":
    app.run()
