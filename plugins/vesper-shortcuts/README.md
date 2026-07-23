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

`register` takes the accelerator and nothing else. Every shortcut arrives as a
single `shortcut` event carrying the accelerator that fired, so listen once and
branch on it:

```js
await vesper.shortcuts.register("ctrl+shift+s")

vesper.on("shortcut", ({ accelerator }) => {
    if (accelerator === "ctrl+shift+s") vesper.invoke("save_document")
})
```

`register` rejects if the accelerator cannot be parsed (see
[Accelerator format](#accelerator-format)). Shortcuts already registered are
unaffected by the failure — don't swallow the rejection, or the app will claim a
hotkey it does not have.

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

```text
ctrl+s
ctrl+shift+s
alt+f4
ctrl+alt+space
cmd+shift+p       ← macOS (cmd = Command key)
ctrl+alt+delete   ← avoid on Windows (reserved by OS)
```

**Supported modifiers**: `ctrl`, `shift`, `alt`, `cmd` (macOS), `win` (Windows), `super` (Linux)

**Supported keys**: letters (`a`–`z`), digits (`0`–`9`), punctuation (`/`, `,`, …),
function keys (`f1`–`f20`), `space`, `enter`, `tab`, `esc`, `backspace`, `delete`,
`insert`, `home`, `end`, `page_up`, `page_down`, `up`, `down`, `left`, `right`,
`caps_lock`, `num_lock`, `scroll_lock`, `print_screen`, `pause`, `menu`, and the
`media_*` keys.

Common alternative spellings are accepted and normalised: `escape` → `esc`,
`return` → `enter`, `del` → `delete`, `pgup` → `page_up`, `arrowleft` → `left`.
Key names are case-insensitive: `Ctrl+S` and `ctrl+s` are equivalent.

An accelerator the backend cannot parse raises `ValueError` at registration,
naming the offending key and listing the valid ones — it never fails silently at
key-press time.

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

### Conflicts are invisible

pynput *observes* keystrokes rather than asking the OS to reserve them. Nothing
fails when another application already uses your accelerator — both act on it.
Registration succeeding is not evidence that the shortcut is yours alone.

There is no cross-platform way to ask "is this combination taken?", so an app
whose hotkey matters should let the user change it rather than hard-code one.
[`examples/launcher`](../../examples/launcher/) does exactly that: a default that
is unlikely to clash, and a Change button that rebinds and persists it.

Popular combinations to think twice about: `ctrl+alt+space` (Claude Desktop, some
IMEs), `alt+space` (window menu), `super+space` (input-source switch),
`ctrl+alt+l` (lock screen), `ctrl+alt+t` (terminal), `ctrl+alt+delete`.

---

## Common patterns

### Several shortcuts, one listener

```js
await vesper.shortcuts.register("ctrl+shift+p")
await vesper.shortcuts.register("ctrl+shift+space")

vesper.on("shortcut", ({ accelerator }) => {
    if (accelerator === "ctrl+shift+p") vesper.invoke("take_screenshot")
    if (accelerator === "ctrl+shift+space") vesper.invoke("toggle_window")
})
```

### Rebinding at runtime

```js
async function setHotkey(next) {
    try {
        await vesper.shortcuts.register(next)   // rejects if unparseable
        await vesper.shortcuts.unregister(current)
        current = next
    } catch (err) {
        // The old shortcut is still registered and still works.
        showError(err.message)
    }
}
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
