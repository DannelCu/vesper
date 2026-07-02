# vesper-shortcuts

Global keyboard shortcuts for Vesper. Shortcuts fire even when the app window is not focused, using [pynput](https://pynput.readthedocs.io/en/latest/) under the hood.

---

## Install

```bash
pip install vesper-shortcuts
```

---

## Setup

```python
from vesper import App
from vesper_shortcuts import ShortcutsPlugin

app = App(
    title="My App",
    frontend="dist/index.html",
    plugins=[ShortcutsPlugin()],
)
```

---

## JavaScript API

Add the SDK:

```toml
[plugins]
shortcuts = "vesper-shortcuts"
```

```bash
vesper sync-sdk
```

```html
<script src="vesper.js"></script>
<script src="vesper-shortcuts.js"></script>
```

### Register a shortcut

```js
await vesper.shortcuts.register("ctrl+shift+s", () => {
    console.log("Shortcut fired!")
    vesper.invoke("save_document")
})
```

The callback receives no arguments. When the shortcut fires, Vesper emits a `shortcut` event with `{ accelerator }` — `vesper.shortcuts.register` wraps this for you.

### Unregister a shortcut

```js
await vesper.shortcuts.unregister("ctrl+shift+s")
```

### Unregister all shortcuts

```js
await vesper.shortcuts.unregisterAll()
```

---

## Accelerator format

Accelerators are strings of modifier keys and a key, joined by `+`:

```
ctrl+s
ctrl+shift+s
alt+f4
cmd+shift+p       ← macOS (cmd = Command key)
ctrl+alt+delete   ← avoid on Windows (reserved by OS)
```

**Supported modifiers**: `ctrl`, `shift`, `alt`, `cmd` (macOS), `win` (Windows), `super` (Linux)

**Supported keys**: letters (`a`–`z`), digits (`0`–`9`), function keys (`f1`–`f12`), `space`, `enter`, `tab`, `escape`, `backspace`, `delete`, `home`, `end`, `page_up`, `page_down`, `up`, `down`, `left`, `right`

Key names are case-insensitive: `Ctrl+S` and `ctrl+s` are equivalent.

---

## Handling the event from Python

```python
@app.on("shortcut")
def on_shortcut(accelerator: str):
    print(f"Shortcut fired: {accelerator}")
    if accelerator == "ctrl+shift+s":
        # do something
        pass
```

Or use IPC commands triggered from the JS callback instead.

---

## Python API

Register shortcuts from Python via IPC:

```python
resp = app.ipc.handle({
    "id": "1",
    "command": "vesper:shortcuts:register",
    "args": {"accelerator": "ctrl+shift+s"},
})
```

When the shortcut fires, Vesper calls `app.window.emit("shortcut", {"accelerator": "ctrl+shift+s"})`. Listen in JS:

```js
vesper.on("shortcut", ({ accelerator }) => {
    if (accelerator === "ctrl+shift+s") {
        // handle it
    }
})
```

---

## IPC command names

| Command | Args | Description |
|---|---|---|
| `vesper:shortcuts:register` | `accelerator: str` | Register a global shortcut |
| `vesper:shortcuts:unregister` | `accelerator: str` | Unregister a specific shortcut |
| `vesper:shortcuts:unregister_all` | — | Unregister all shortcuts |

---

## Platform notes

- **Windows**: Requires no additional setup. Works immediately.
- **macOS**: The app may need the "Accessibility" permission in System Settings → Privacy & Security → Accessibility for global shortcuts to work outside the app.
- **Linux**: Requires X11. Wayland support via pynput is limited — shortcuts may not fire when other apps are focused on pure Wayland sessions.

---

## Common patterns

### Screenshot shortcut

```js
await vesper.shortcuts.register("ctrl+shift+p", async () => {
    await vesper.invoke("take_screenshot")
})
```

### Quick show/hide

```js
await vesper.shortcuts.register("ctrl+shift+space", () => {
    vesper.invoke("toggle_window")
})
```

```python
_visible = True

@app.command
def toggle_window():
    global _visible
    if _visible:
        app.window.minimize()
    else:
        app.window.restore()
    _visible = not _visible
```
