# vesper-theme

OS dark/light mode detection for Vesper. Reads the current system theme and optionally watches for changes in real time using [darkdetect](https://github.com/albertosottile/darkdetect).

---

## Install

```bash
pip install vesper-theme
```

---

## Setup

```python
from vesper import App
from vesper_theme import ThemePlugin

app = App(
    title="My App",
    frontend="dist/index.html",
    plugins=[ThemePlugin(watch=True)],
)
```

`watch=True` (default) starts a background daemon thread that calls `darkdetect.listener()`. When the OS theme changes, Vesper emits a `theme:change` event to the frontend.

Set `watch=False` if you only need to read the theme once at startup and do not need live updates.

---

## JavaScript API

Add the SDK:

```toml
[plugins]
theme = "vesper-theme"
```

```bash
vesper sync-sdk
```

```html
<script src="vesper.js"></script>
<script src="vesper-theme.js"></script>
```

### Get the current theme

```js
const { theme, is_dark } = await vesper.theme.get()
// theme: "Light" | "Dark"
// is_dark: true | false
```

### Listen for theme changes

```js
vesper.theme.onChange(({ theme, is_dark }) => {
    document.documentElement.setAttribute("data-theme", theme.toLowerCase())
    updateUI(is_dark)
})
```

`onChange` is a convenience wrapper around `vesper.on("theme:change", ...)`. It returns an unsubscribe function:

```js
const stop = vesper.theme.onChange(({ theme }) => applyTheme(theme))

// Later, stop listening:
stop()
```

---

## Full initialization pattern

```js
async function initTheme() {
    // Apply the current theme immediately on load
    const { theme } = await vesper.theme.get()
    applyTheme(theme)

    // Update when the OS theme changes
    vesper.theme.onChange(({ theme }) => applyTheme(theme))
}

function applyTheme(theme) {
    document.documentElement.setAttribute(
        "data-theme",
        theme === "Dark" ? "dark" : "light"
    )
}

initTheme()
```

---

## IPC command names

| Command | Args | Returns |
|---|---|---|
| `vesper:theme:get` | — | `{ theme: "Light" \| "Dark", is_dark: bool }` |

The `theme:change` event is emitted automatically when `watch=True` and the OS theme changes.

---

## Fallback behavior

- If `darkdetect.theme()` returns `None` (e.g. on some Linux configurations), the theme defaults to `"Light"`.
- On Linux, `darkdetect` reads from the GTK theme. Some desktop environments or display managers may not expose a reliable dark/light mode signal.

---

## CSS integration

### CSS custom properties

```css
:root { --bg: #fff; --text: #111; }
:root[data-theme="dark"] { --bg: #111; --text: #fff; }
```

### Tailwind CSS (class-based dark mode)

```js
function applyTheme(theme) {
    document.documentElement.classList.toggle("dark", theme === "Dark")
}
```

For a complete dark mode recipe with manual toggle and persistence, see [Recipes — Dark/Light Mode Theming](../../docs/recipes/theming.md).
