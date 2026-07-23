"""
Launcher — a Spotlight/Alfred-style command bar.

A frameless, transparent, always-on-top window that lives off-screen and drops
in on a global hotkey. Type to run a command: do maths, play 2048, grab a
screenshot, search the web, or toggle launch-at-login. The point of this example
is the *shell* — the pieces a launcher needs that a normal window does not:

  • frameless + transparent with a hand-built drag region (App(frameless=True,
    transparent=True, easy_drag=False) + data-vesper-drag)
  • always-on-top, placed with the positioner instead of remembering geometry
  • hide to the tray instead of quitting, and come back on a global shortcut
  • a Windows-11 mica/acrylic backdrop where the platform offers one

Everything optional degrades, and the degradation is never silent — the command
list greys out what this machine cannot do and says why. Without vesper-shortcuts
there is no global hotkey (the tray and the window still work); without the tray
extra the close button quits instead of hiding; without vesper-screenshot the
Screenshot command is gone; without vesper-store the recent list and 2048 best
score live only for this run.

Run with `vesper dev` from this directory.
"""
from __future__ import annotations

import time
from pathlib import Path

from vesper import App
from vesper.core import paths

# ── Optional plugins ─────────────────────────────────────────────────────────
#
# Each is imported defensively so the launcher runs with none of them installed.
# A missing plugin removes a capability (and the command that needs it) rather
# than breaking startup. The frontend merges these flags with
# vesper.capabilities() to decide what to show.

plugins: list = []

HAS_SHORTCUTS = False
try:
    from vesper_shortcuts import ShortcutsPlugin

    plugins.append(ShortcutsPlugin())
    HAS_SHORTCUTS = True
except ImportError:
    pass

HAS_STORE = False
try:
    from vesper_store import StorePlugin

    # A named store so the launcher's settings do not collide with another
    # Vesper app's on the same machine.
    plugins.append(StorePlugin(app_name="vesper-launcher"))
    HAS_STORE = True
except ImportError:
    pass

HAS_SCREENSHOT = False
try:
    from vesper_screenshot import ScreenshotPlugin

    plugins.append(ScreenshotPlugin())
    HAS_SCREENSHOT = True
except ImportError:
    pass


# Screenshots land in a single folder the app owns, and the filesystem scope is
# narrowed to exactly that folder — the screenshot plugin validates its
# destination against fs_scope, so the frontend cannot talk it into writing
# anywhere else.
CAPTURES_DIR = paths.ensure_dir(paths.config_dir("vesper-launcher") / "captures")


app = App(
    title="Launcher",
    width=660,
    # Tall enough for the calculator keypad and the 2048 board without clipping.
    # The palette view does not need it, but one window serves all of them, and a
    # window that cuts its own content off is worse than one with room to spare.
    height=580,
    min_width=420,
    min_height=420,
    # The launcher shell: no OS chrome, a see-through window so the panel can
    # float with rounded corners, and it stays above other windows the way a
    # command bar should. easy_drag is off because the titlebar is ours — the
    # frontend marks its own drag region (data-vesper-drag), which keeps the
    # search input and buttons clickable instead of dragging the window.
    frameless=True,
    transparent=True,
    on_top=True,
    easy_drag=False,
    # Resizable even though it is frameless. A frameless window has no decorations
    # to grab, so whether edge-dragging works is up to the window manager — but
    # refusing outright guarantees the user cannot fix a window that is too small
    # for them, and the layout below adapts either way.
    resizable=True,
    frontend="frontend/index.html",
    debug=True,
    plugins=plugins,
    # One instance only: a second launch should surface the running launcher,
    # not open a rival command bar.
    single_instance=True,
    # No remember_window here on purpose. A launcher always arrives at the same
    # place (top-center of the active screen, via the positioner) rather than
    # wherever it was last dragged — see frontend/app.js reveal().
    remember_window=False,
    # The only path the frontend may write: the captures folder. Everything else
    # the launcher does is in-process, so nothing else needs filesystem reach.
    fs_scope=[str(CAPTURES_DIR)],
)


# ── What this machine can do ─────────────────────────────────────────────────


@app.command("launcher:features")
def features() -> dict:
    """
    This app's optional pieces, for the UI to hide what is missing.

    vesper.capabilities() already reports the framework's own backends (tray,
    mica, global_shortcuts, screenshot…); these three are which *plugins* were
    importable at startup, which the framework cannot know for the app. The
    frontend merges both.
    """
    return {
        "shortcuts": HAS_SHORTCUTS,
        "store": HAS_STORE,
        "screenshot": HAS_SCREENSHOT,
        "captures_dir": str(CAPTURES_DIR),
    }


@app.command("launcher:new_capture_path")
def new_capture_path() -> str:
    """
    A fresh, timestamped destination inside the captures folder.

    The frontend passes this straight to vesper.screenshot.captureToFile(); it
    is inside fs_scope, so the write is allowed, and unique, so captures never
    clobber each other.
    """
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return str(CAPTURES_DIR / f"capture-{stamp}.png")


@app.command("launcher:open_captures")
def open_captures() -> bool:
    """Reveal the captures folder in the native file manager."""
    from vesper.core import shell

    shell.reveal(str(CAPTURES_DIR))
    return True


# ── System tray ──────────────────────────────────────────────────────────────
#
# Optional: the tray needs pystray + Pillow (the vesper[tray] extra). Without
# it the launcher still runs — the close button quits instead of hiding, and the
# window is reached with the global hotkey or by relaunching.
#
# Tray callbacks run on a background thread — Vesper guarantees that on every
# platform, because pystray does not (see docs/tray.md). They mostly emit an event
# and let the frontend do the show/hide/position work through the normal IPC path,
# which keeps window state in one place. "Show launcher" also calls the window
# directly — see _reveal below for why. app.quit() is safe from any thread; it is
# what tears the event loop down.

from vesper.core.capabilities import probe as _probe_caps  # noqa: E402

if _probe_caps().get("tray", {}).get("available"):
    from vesper.core.tray import TrayMenuItem

    def _reveal() -> None:
        """
        Bring the window back, then let the frontend place and focus it.

        Showing the window here rather than only emitting is deliberate. "Show
        launcher" is the one action that must work when everything else has gone
        wrong — if the page threw during boot, or is mid-reload, an event has
        nobody listening and the tray looks broken while the app is fine. The
        window call is safe from this thread: PyWebView marshals it onto the GUI
        loop with glib.idle_add.
        """
        app.window.show_window()
        app.emit("tray:reveal", {})

    app.tray(
        icon=str(Path(__file__).parent / "assets" / "icon.png"),
        title="Launcher",
        menu=[
            TrayMenuItem("Show launcher", _reveal),
            TrayMenuItem("Take screenshot", lambda: app.emit("tray:screenshot", {})),
            None,  # separator
            TrayMenuItem("Quit", lambda: app.quit()),
        ],
    )


if __name__ == "__main__":
    app.run()
