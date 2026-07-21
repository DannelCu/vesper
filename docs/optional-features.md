# Optional Features

Some of what Vesper offers depends on a tool or package that may not be present.
Rather than refusing to start, most of those features **degrade to a no-op**. This
page is the contract: what each one needs, and what happens when it is absent.

The one dependency that is not optional is the native WebView — see
[Platform Requirements](platform-requirements.md).

## The degradation rule

> An optional feature degrades to a no-op and returns a falsy value when its backend
> is missing, unless doing nothing would be worse than failing.

**Tray** raises, by design: it is explicitly opt-in — you call `app.tray(...)` — and
an app that asked for a tray icon and silently did not get one is worse off than one
told immediately. **Trash** raises for the same reason, since reporting "nothing
happened" for a delete the user requested is worse than an error.

Everything else can be called speculatively.

A no-op is never an exception, and never a log line per call. Unavailability is
logged **once** at debug level, so an app polling the clipboard does not flood its
own log.

## Feature matrix

| Feature | Windows | macOS | Linux | Missing → |
|---|---|---|---|---|
| Clipboard (text) | built in | built in | `xclip` | no-op, returns `""` |
| Clipboard (images) | built in | built in | `xclip` | no-op, returns `null` |
| Notifications | built in | built in | `notify-send` (`libnotify`) | no-op |
| Move to trash | built in | built in | `send2trash` or `gio` | **raises** `RuntimeError` |
| Keep awake | built in | `caffeinate` | `systemd-inhibit` or `xdg-screensaver` | no-op, returns `false` |
| System tray | `pystray` + `Pillow` | same | same | **raises** `RuntimeError` |
| Taskbar / dock badge | `comtypes` (+ `Pillow`) | `pyobjc` | not supported | no-op, returns `false` |
| Power events | built in | `pyobjc` | `jeepney` | no-op, no events fire |
| Global shortcuts | `pynput` | `pynput` | `pynput` | no-op |

"built in" means the platform ships the tool Vesper shells out to — `pbcopy`,
PowerShell, `osascript` — so there is nothing to install.

Install lines:

```bash
# Linux system tools
sudo apt install xclip libnotify-bin        # Fedora: dnf install xclip libnotify

# Python extras
pip install "vesper[tray]"                  # pystray + Pillow
pip install "vesper[trash]"                 # send2trash
pip install jeepney                         # Linux power events
pip install vesper-shortcuts                # pynput
```

Two rows deviate from the general rule and are worth reading twice:

- **Trash raises.** `fs.trash()` falls back to platform tools, and if none works it
  raises rather than returning False. Deleting a file is destructive: reporting
  "nothing happened" when the user asked for a delete would be worse than an error.
- **Linux badges are unavailable, not missing.** There is no cross-desktop protocol.
  Vesper speaks Unity LauncherEntry, which KDE Plasma and Dash-to-Dock implement and
  plain GNOME does not — so there is nothing to install, and `vesper doctor` offers no
  fix for it. Note that the D-Bus signal is *sent* successfully on a desktop with a
  session bus — nothing listens, so nothing renders. `capabilities` reports it
  unavailable because that is the outcome the user sees.

## Finding out at install time

`vesper doctor` prints the whole matrix for the current machine, with the exact
install command for anything missing:

```console
$ vesper doctor
...
Optional features
-----------------
[WARN] Clipboard (images): xclip not found
     Fix: sudo apt install xclip  (Fedora: dnf install xclip, Arch: pacman -S xclip)
[OK] Notifications: notify-send
[OK] System tray: pystray + Pillow
```

These are `[WARN]`, not `[FAIL]`: a missing optional backend does not make `vesper
doctor` exit non-zero. Only the critical checks do.

## Finding out at runtime, from the frontend

Ask before you offer. A disabled button explains itself; a button that does nothing
looks like a bug in your app:

```js
const caps = await vesper.capabilities()

if (!caps.clipboard_image) {
  pasteButton.disabled = true
  pasteButton.title = "Image clipboard unavailable on this system"
}
```

The keys are booleans, one per row of the matrix above:

`clipboard_text`, `clipboard_image`, `notifications`, `trash`, `keep_awake`, `tray`,
`badge`, `power_events`, `global_shortcuts`.

Install instructions are deliberately **not** exposed to the frontend — telling a user
inside your app's UI to run `pip install` is rarely the right move. They go to
`vesper doctor` and to the startup log instead.

From Python the same answers are available directly:

```python
from vesper.core import capabilities

capabilities.is_available("tray")   # bool
capabilities.probe()                # full report, with detail and fix strings
```

## Finding out at startup

When an app configures a feature whose backend is missing, Vesper logs a warning once
before the window opens:

```text
WARNING vesper.app: system tray is configured but unavailable on this system
        (missing: pystray). Fix: pip install "vesper[tray]"
```

Only what the app configured explicitly is checked. Vesper does not guess at intent,
because a startup that warns about everything trains people to ignore it.

## Plugin requirements

Plugins have environmental requirements that no amount of `pip install` resolves:

- **vesper-keychain** on Linux needs a running secrets backend — GNOME Keyring or
  KWallet. On a headless box or a bare window manager there may be none, and `keyring`
  raises rather than silently losing the secret.
- **vesper-shortcuts** on macOS requires the user to grant **Accessibility**
  permission (System Settings → Privacy & Security → Accessibility). Until they do,
  shortcuts register without error and never fire.
- **vesper-shortcuts on Wayland** is limited: `pynput` relies on X11 APIs, so global
  shortcut capture is unreliable or unavailable depending on the compositor. It works
  under XWayland for X11 clients only.
- **vesper-mongodb** needs a reachable MongoDB server. The driver connects lazily, so
  a wrong URI surfaces on first query rather than at startup.
