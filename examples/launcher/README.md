# Launcher

A Spotlight/Alfred-style command bar. A frameless, transparent, always-on-top window
that lives off-screen and drops in on a global hotkey. Type to run a command: do
maths, play 2048, grab a screenshot, search the web, toggle launch-at-login.

The point of this example is the **shell** — the pieces a launcher needs that a normal
window does not. A window with no OS chrome still has to be draggable. A window that
"closes" to the tray has to be summonable again. A window that is always on top has to
know where to put itself. None of that is hard, but all of it is easy to get subtly
wrong, and it is what this example exists to show working.

It is also where the calculator lives, and the calculator never calls `eval()` — the
one place in these examples where a user-typed string is executed, done the way it
should be.

---

## Running it

No Node.js needed — this is a vanilla project.

```bash
pip install -e ../..           # Vesper itself, from this repo
cd examples/launcher
vesper dev
```

Optional, and the app runs with none of it:

```bash
# The global hotkey. Without it the launcher works, but only from the tray/window.
pip install -e ../../plugins/vesper-shortcuts

# Remembers recent commands, your 2048 best score and your hotkey between runs.
pip install -e ../../plugins/vesper-store

# The screenshot command.
pip install -e ../../plugins/vesper-screenshot

# The tray icon (pystray + Pillow).
pip install "vesper[tray]"

# Clipboard on Linux (built in on Windows and macOS).
sudo apt install xclip
```

After installing a plugin, run `vesper sync-sdk` to copy its JavaScript into
`frontend/`. The `[plugins]` section of [`vesper.toml`](vesper.toml) is what that reads.

---

## What to try

There is no login and no data to set up. The one thing worth knowing:

**The global hotkey is `Ctrl + Alt + K`.** Press it anywhere — the launcher drops
in at the top of the screen under your cursor. Press it again and it disappears.
Without `vesper-shortcuts` installed the hotkey is inactive and Settings says so.

If that combination is taken on your machine, **Settings → Global hotkey → Change**
rebinds it: press the new combination and it is registered and remembered. The
default is deliberately not `Ctrl + Alt + Space` — that one is popular enough to
collide (Claude Desktop takes it, among others), and a collision is silent: both
apps respond. See [Known limits](#known-limits).

Everything else is discoverable by typing. Screenshots are written to
`~/.config/vesper-launcher/captures/`, which is the **only** path the app can write to.

---

## Guided tour

1. **On launch** the window drops in at the top-centre of the screen under your
   cursor, with the search field focused. It has no title bar — the dark strip with
   "Launcher" on it is ours, and dragging it moves the window.

2. **Type `12 * (3 + 4)`.** A banner shows `= 84` as you type, and the result list
   narrows to what you do with a number: copy it, or open it in the calculator.
   Press <kbd>Enter</kbd> to copy `84` to the clipboard, and the launcher gets out of
   your way. **Nothing here runs `eval()`** — see [The calculator](#the-calculator).

3. **Type `calc` and press <kbd>Enter</kbd>** for the full keypad. It takes physical
   keyboard input too: digits, operators, <kbd>Enter</kbd> to evaluate,
   <kbd>Backspace</kbd> to delete, <kbd>Esc</kbd> to go back.

4. **Type `2048`** and play. Arrow keys or WASD. Your best score survives a restart if
   `vesper-store` is installed; without it, it lasts the session and Settings says so.

5. **Press <kbd>Esc</kbd> in the palette** and the launcher hides — to the tray if
   there is one. Bring it back with the hotkey or the tray's **Show launcher**.
   If there is *neither* a tray nor a hotkey, it minimizes instead of hiding, so the
   taskbar can still bring it back rather than the window becoming unreachable.

6. **Right-click the tray icon.** Show launcher, Take screenshot, Quit. These run on
   a background thread — Vesper guarantees that, because pystray does not, and an
   action running on the GUI loop deadlocks it ([tray.md](../../docs/tray.md)) —
   so they mostly emit an event and let the frontend do the window work.
   **Show launcher** is the exception: it shows the window itself *and* emits,
   because it is the one action that has to work when the page is broken or
   mid-reload, otherwise the tray looks dead while the app is fine.

7. **Type `screenshot`.** The launcher hides itself first (so it is not in its own
   shot), captures, then **comes back** and tells you where the file went. Coming
   back matters: a window that hides for an action and never returns is
   indistinguishable from one that crashed, and an error message painted onto a
   hidden window is an error nobody reads. Without `vesper-screenshot` the command
   is still listed but greyed out with the reason.

8. **Type anything that is not a command** — `vesper framework`, say — and the last
   entry offers to search the web for it, opening your real browser.

9. **Open Settings** (the gear, or type `settings`). It shows the hotkey, a
   launch-at-login toggle, and a table of what this machine can and cannot do, which is
   `vesper.capabilities()` rendered directly. **Change** next to the hotkey listens
   for the next combination you press and rebinds to it — the new one is registered
   before the old one is dropped, so a combination the backend rejects leaves you
   with the hotkey you already had rather than none.

10. **Try launch-at-login.** Running from source it resolves to your Python
    interpreter, so it is a no-op and reports so honestly rather than pretending. It
    only means something for a packaged build.

### The calculator

The calculator is the one place in these examples where a **string the user typed is
evaluated**, and it does it without `eval()` or `new Function()`.

Running user input through `eval` hands the page's full authority to whatever was
typed — in a desktop app that is the same process holding your filesystem bridge.
[`calc.js`](frontend/calc.js) tokenises the expression and evaluates it with the
shunting-yard algorithm, so the worst a hostile string can do is throw. It supports
`+ - * / % ^`, parentheses, unary minus, decimals and the constants `pi` and `e`.

---

## Vesper features on show

| In the app | Feature | Docs |
|---|---|---|
| No title bar; dragging the top strip | Frameless window with a hand-built drag region | [frameless.md](../../docs/frameless.md) |
| The floating translucent panel | `transparent=True` + a semi-opaque panel | [frameless.md](../../docs/frameless.md) |
| Stays above other windows | `on_top=True` | [window-controls.md](../../docs/window-controls.md) |
| Drops in at the top of the active screen | Positioner, `window.position("top-center", {screen:"cursor"})` | [window-controls.md](../../docs/window-controls.md) |
| Hiding to the tray and back | `window.hide()` / `window.show()` | [window-controls.md](../../docs/window-controls.md) |
| Tray icon and its menu | System tray | [tray.md](../../docs/tray.md) |
| `Ctrl+Alt+K` from anywhere, and rebinding it | `vesper-shortcuts` plugin | [plugins.md](../../docs/plugins.md) |
| Recents, 2048 best score, chosen hotkey | `vesper-store` plugin | [plugins.md](../../docs/plugins.md) |
| The screenshot command | `vesper-screenshot` plugin | [plugins.md](../../docs/plugins.md) |
| Copying a result | Text clipboard | [clipboard.md](../../docs/clipboard.md) |
| "Saved …" toast | Notifications | [notifications.md](../../docs/notifications.md) |
| Launch-at-login toggle | Autostart | [autostart.md](../../docs/autostart.md) |
| Search opening your browser | `shell.openUrl` | [shell.md](../../docs/shell.md) |
| Captures folder is the only writable path | Filesystem scope | [filesystem.md](../../docs/filesystem.md) |
| A second launch surfaces this one | Single instance | [single-instance.md](../../docs/single-instance.md) |
| Windows 11 acrylic backdrop | Window effects | [window-controls.md](../../docs/window-controls.md) |
| Every greyed-out command | Capability probing | [optional-features.md](../../docs/optional-features.md) |

### Why the window is frameless *and* draggable

`App(frameless=True)` removes the OS title bar, which also removes the thing you drag.
This app sets `easy_drag=False` and marks its own titlebar with `data-vesper-drag`,
which `vesper.js` wires on load. The buttons inside it stay clickable — only empty
titlebar space drags.

Leaving `easy_drag` at its default would make the **whole window** a drag handle,
including the search field, which is not what you want in a window built around a text
input. The full pattern, including platform quirks, is in the
[custom titlebar recipe](../../docs/recipes/custom-titlebar.md).

---

## Without the optional pieces

| Missing | What you get instead | To enable |
|---|---|---|
| `vesper-shortcuts` (pynput) | No global hotkey. The launcher still runs; reach it from the tray, or relaunch. Settings says it is inactive and why. | `pip install -e ../../plugins/vesper-shortcuts` |
| `vesper[tray]` (pystray + Pillow) | No tray icon. The close button quits outright instead of hiding, because with nothing to summon it, hiding would strand the window. | `pip install "vesper[tray]"` |
| `vesper-store` | Recent commands, the 2048 best score and a rebound hotkey live in memory for the session only. | `pip install -e ../../plugins/vesper-store` |
| `vesper-screenshot` (mss) | The screenshot command is listed but disabled, with the reason on the row. | `pip install -e ../../plugins/vesper-screenshot` |
| Both tray *and* hotkey | Actions that would hide the window minimize it instead, so the taskbar can bring it back. | either of the above |
| `xclip` (Linux) | Copying a result is disabled and says so. | `sudo apt install xclip` |
| Windows 11 / mica | The CSS translucent panel is the look. Nothing is missing visually on Linux or macOS. | n/a — Windows 11 only |

`vesper doctor` reports all of these, with the same install commands.

---

## Known limits

- **A frameless window has no resize grips.** The window is `resizable=True`, but with
  no OS decorations whether edge-dragging works is up to the window manager. The layout
  adapts either way: the keypad rows share whatever height there is, and views scroll
  rather than clip when the window is small.

- **`transparent=True` depends on a compositor.** Without one the window renders on a
  solid background instead of blending. The panel is drawn by the app, so the launcher
  is fully usable either way — only the blur behind it is lost.

- **Nothing can tell you a hotkey is already taken.** pynput *observes* keystrokes
  instead of asking the OS to reserve them, so registering a combination another
  app already uses succeeds — and then both apps respond to it. There is no
  cross-platform way to ask, which is why the launcher ships a quiet default and a
  Change button instead of pretending its hotkey is exclusive. Your choice is
  remembered by `vesper-store`; without that plugin it lasts the session.

- **No dock menu or jump list** — right-clicking the taskbar/dock icon shows the OS
  default, not app actions. That needs `comtypes`/`pyobjc` and belongs in a plugin;
  see [KNOWN-ISSUES KI6](../../KNOWN-ISSUES.md). The tray menu is the cross-platform
  substitute this app uses.

- **Launch-at-login is a no-op from source.** It registers the current executable, which
  when running `vesper dev` is your Python interpreter. It is meaningful only for a
  packaged build — see [autostart.md](../../docs/autostart.md).

---

## Files

| File | What is in it |
|---|---|
| [`app.py`](app.py) | All the Python. Start at the `App(...)` call — every option is commented — then the three commands and the tray block at the bottom. |
| [`frontend/index.html`](frontend/index.html) | The shell: titlebar drag region, palette, and the calculator, 2048 and settings views. |
| [`frontend/app.js`](frontend/app.js) | The frontend logic: the command palette, capability wiring, hotkey and tray handling, and where the window decides to hide or minimize. |
| [`frontend/calc.js`](frontend/calc.js) | The safe expression evaluator. Tokeniser plus shunting-yard, no `eval()`. |
| [`frontend/game2048.js`](frontend/game2048.js) | The game, self-contained: it owns none of the app's chrome. |
| [`frontend/styles.css`](frontend/styles.css) | Plain CSS, no framework, no CDN. The floating panel and the responsive keypad live here. |
| [`assets/icon.png`](assets/icon.png) | The tray icon. |
| [`vesper.toml`](vesper.toml) | Project metadata and the `[plugins]` list `vesper sync-sdk` reads. |

Read `app.py` top to bottom; it is ordered the way the app starts.
