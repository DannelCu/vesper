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
VIDEO_SUFFIXES = {".mp4", ".webm", ".mkv", ".mov", ".m4v", ".ogv"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
MEDIA_SUFFIXES = VIDEO_SUFFIXES | IMAGE_SUFFIXES

# A small, permissively licensed clip, for trying the app with an empty folder.
SAMPLE_VIDEO_URL = (
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/"
    "sample/ForBiggerBlazes.mp4"
)

THUMB_DIR_NAME = ".vault-thumbs"


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
    # The library folder is chosen at runtime, but fs_scope is fixed when the App
    # is built, so the scope is the widest place a library could live and the app
    # narrows it to the chosen folder itself (see _in_library). Noted in the
    # README: a runtime-narrowable scope is something the framework does not
    # currently offer.
    fs_scope=[str(Path.home())],
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
            "*.mp4", "*.webm", "*.mkv", "*.mov", "*.m4v", "*.ogv",
        ],
        "ffmpeg": [
            "-y", "-ss", "1", "-i", "-vframes", "-vf", "scale=320:-1",
            "*.mp4", "*.webm", "*.mkv", "*.mov", "*.m4v", "*.ogv", "*.jpg",
        ],
    },
)


# ── Library state ────────────────────────────────────────────────────────────

state: dict = {
    "root": None,        # Path of the chosen library folder
    "server": None,      # its loopback file server
    "base_url": None,    # …and the URL the player loads from
}


def _in_library(path: str) -> Path:
    """
    Resolve *path* and require it to be inside the chosen library folder.

    fs_scope already stops the frontend escaping the home directory; this is the
    narrower check the app enforces on top, and every command that touches a file
    goes through it.
    """
    root = state["root"]
    if root is None:
        raise RuntimeError("No library folder is open yet.")

    resolved = Path(path).expanduser().resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise RuntimeError(f"Path is outside the library: {path}") from error
    return resolved


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
        is_video = entry.suffix.lower() in VIDEO_SUFFIXES
        item = {
            "name": entry.name,
            "path": str(entry),
            "url": f"{state['base_url']}/{entry.name}",
            "kind": "video" if is_video else "image",
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


# ── Downloading a sample ─────────────────────────────────────────────────────


@app.command("vault:download_sample")
def download_sample() -> str:
    """
    Fetch a sample clip into the library, reporting progress two ways.

    The taskbar/dock progress bar is the point: a download is exactly the case
    where the user has switched to another window and wants to know from there.
    """
    from vesper.core import badge, net

    root = state["root"]
    if root is None:
        raise RuntimeError("Open a library folder first.")

    target = root / "sample-big-buck-bunny.mp4"

    def on_progress(percent: int) -> None:
        # net.download reports whole percentages; badge.set_progress wants 0..1.
        badge.set_progress(percent / 100)
        app.emit("download:progress", {"percent": percent})

    try:
        net.download(SAMPLE_VIDEO_URL, str(target), on_progress=on_progress,
                     scope=app.fs_scope)
    finally:
        badge.clear_progress()

    from vesper.core import notify

    notify.send("Media Vault", f"Downloaded {target.name}")
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

    The second window is a separate document, so the selection is handed over as
    an event rather than shared state.
    """
    player_window.show()
    app.emit("player:load", {"url": url, "name": name})
    return True


# ── Native menu: deliberately absent ─────────────────────────────────────────
#
# This app wants a File menu, and `app.menu([...])` is the API for it — but on
# PyWebView 6.2.1 it raises AttributeError before the window opens, because
# vesper/core/window.py reaches for `webview.MenuAction`, which lives in
# `webview.menu`, not at the top level. Vesper's menu tests mock the whole
# webview module, so a MagicMock invents the missing attribute and they pass.
#
# Reported as a finding rather than worked around here: an example that monkey-
# patched the framework to boot would teach the wrong thing. Open folder and
# Refresh live in the toolbar instead, which is where a user looks first anyway.


app.splash(html="""
  <div style="font:600 18px system-ui;display:grid;place-items:center;
              height:100vh;background:#12131a;color:#e8e8ef">
    Media Vault — indexing…
  </div>
""", width=360, height=180)


if __name__ == "__main__":
    app.run()
