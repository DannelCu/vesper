# Autostart

Launch your app when the user logs in.

```python
from vesper.core import autostart

autostart.enable("My App")
autostart.is_enabled("My App")   # True
autostart.disable("My App")
```

From the frontend:

```js
await vesper.autostart.enable()
await vesper.autostart.isEnabled()
await vesper.autostart.disable()
```

The app name is taken from your window title when called over IPC.

## How it registers

All three are per-user locations, so none of this needs administrator rights.

| Platform | Mechanism |
|---|---|
| Windows | A value under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` |
| macOS | A LaunchAgent plist in `~/Library/LaunchAgents` |
| Linux | A `.desktop` file in `~/.config/autostart` |

## Only works in a packaged app

`enable()` is a no-op that logs a warning when you run from source, and returns
`False`.

The registration has to name an executable. Running from source, `sys.executable` is
the Python interpreter — registering it would start Python at login, not your app.
Rather than write an entry that silently does nothing, Vesper refuses and says why.

Package your app first (`vesper package`), then test autostart on the built binary.

`disable()` is exempt: it works from source too, so a stale entry left by a packaged
build can always be cleared during development.

## Failure behaviour

Every function returns a boolean and never raises. A read-only home directory or a
locked-down registry makes `enable()` return `False` and log the reason.
