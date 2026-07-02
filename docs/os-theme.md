# OS Info & Theme

## OS information

Get details about the host operating system:

```js
const info = await vesper.os.info()
// {
//   platform: "win32" | "darwin" | "linux",
//   version: "Windows 11 Pro 10.0.22000",
//   machine: "AMD64",
//   python_version: "3.11.2"
// }
```

```python
from vesper.core import os_info
info = os_info.get_info()
```

Fields:

| Field | Description |
|---|---|
| `platform` | `sys.platform` — `"win32"`, `"darwin"`, or `"linux"` |
| `version` | Full OS version string from `platform.version()` |
| `machine` | CPU architecture from `platform.machine()` — e.g. `"AMD64"`, `"arm64"` |
| `python_version` | Running Python version from `platform.python_version()` |

This is a built-in IPC command (`vesper:os:info`) registered automatically.

---

## Dark / light mode detection

Dark/light mode detection requires the `vesper-theme` plugin:

```bash
pip install vesper-theme
```

```python
from vesper import App
from vesper_theme import ThemePlugin

app = App(
    plugins=[ThemePlugin(watch=True)],
)
```

`watch=True` starts a background thread that listens for OS theme changes and emits a `theme:change` event when the mode switches.

### Get current theme

```js
const { theme, is_dark } = await vesper.theme.get()
// theme: "Light" | "Dark"
// is_dark: true | false
```

```python
# Direct IPC call
resp = app.ipc.handle({"id": "1", "command": "vesper:theme:get", "args": {}})
# resp["result"] = {"theme": "Light", "is_dark": False}
```

### Listen for theme changes

```js
vesper.theme.onChange(({ theme, is_dark }) => {
    document.documentElement.setAttribute("data-theme", theme.toLowerCase())
})
```

The callback receives `{ theme, is_dark }` whenever the OS switches between dark and light mode.

From JS (raw event listener):

```js
vesper.on("theme:change", ({ theme, is_dark }) => {
    applyTheme(theme)
})
```

### Applying the theme with CSS variables

```css
:root[data-theme="light"] {
    --bg: #ffffff;
    --text: #1a1a1a;
}

:root[data-theme="dark"] {
    --bg: #1a1a1a;
    --text: #ffffff;
}

body {
    background: var(--bg);
    color: var(--text);
}
```

```js
async function initTheme() {
    const { theme } = await vesper.theme.get()
    document.documentElement.setAttribute("data-theme", theme.toLowerCase())
}

vesper.theme.onChange(({ theme }) => {
    document.documentElement.setAttribute("data-theme", theme.toLowerCase())
})

initTheme()
```

For a complete recipe with Tailwind's `darkMode: 'class'` and CSS variable patterns, see [Recipes — Dark/Light Mode Theming](recipes/theming.md).

### JS SDK setup

After installing vesper-theme and adding it to `vesper.toml`, sync the SDK:

```toml
[plugins]
theme = "vesper-theme"
```

```bash
vesper sync-sdk
```

Then include it in your HTML:

```html
<script src="vesper.js"></script>
<script src="vesper-theme.js"></script>
```

---

## Platform constants

Use `vesper.os.info().platform` to conditionally run platform-specific logic in the frontend:

```js
const { platform } = await vesper.os.info()

if (platform === "darwin") {
    // macOS-specific UI adjustments (e.g. traffic light buttons spacing)
    document.body.classList.add("macos")
}
```
