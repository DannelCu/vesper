# Window State Persistence

Remember the window's size and position between runs.

```python
app = App(title="My App", remember_window=True)
```

Geometry is saved when the app closes and restored on the next start. Off by
default, since not every app wants it.

## Where it is stored

A JSON file in the per-user config directory:

| Platform | Location |
|---|---|
| Windows | `%LOCALAPPDATA%\<app>\window-state.json` |
| macOS | `~/Library/Application Support/<app>/window-state.json` |
| Linux | `$XDG_CONFIG_HOME/<app>/window-state.json` (or `~/.config`) |

The directory name comes from the window title.

## Disconnected monitors

The tricky case is a window saved on a monitor that is no longer attached. Restoring
it literally would place the window off-screen, where it is invisible and cannot be
dragged back.

Before restoring, Vesper checks the stored position against the currently connected
screens:

- **Position still on a screen** — size and position are both restored.
- **Position off every screen** — the size is restored and the position dropped, so
  the window is centred. Discarding the user's preferred size too would be a worse
  outcome than losing the position alone.

A window deliberately left half off the edge of a screen still counts as on-screen
and is restored where it was.

Corrupt or hand-edited state files are ignored rather than treated as an error.
