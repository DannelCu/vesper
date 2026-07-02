# Recipe: Dark / Light Mode Theming

This recipe applies the OS dark/light mode preference to your app's CSS using `vesper-theme` and CSS custom properties. The theme updates in real time when the user switches modes in OS settings.

---

## Setup

```bash
pip install vesper-theme
vesper sync-sdk
```

```toml
# vesper.toml
[plugins]
theme = "vesper-theme"
```

```python
# app.py
from vesper import App
from vesper_theme import ThemePlugin

app = App(
    title="My App",
    frontend="frontend/index.html",
    plugins=[ThemePlugin(watch=True)],   # watch=True for real-time updates
)

if __name__ == "__main__":
    app.run()
```

---

## CSS with custom properties

Define both themes using CSS custom properties on the root element:

```css
/* frontend/style.css */

:root {
    --bg-primary:   #ffffff;
    --bg-secondary: #f9fafb;
    --text-primary: #111827;
    --text-muted:   #6b7280;
    --border:       #e5e7eb;
    --accent:       #3b82f6;
    --accent-hover: #2563eb;
}

:root[data-theme="dark"] {
    --bg-primary:   #111827;
    --bg-secondary: #1f2937;
    --text-primary: #f9fafb;
    --text-muted:   #9ca3af;
    --border:       #374151;
    --accent:       #60a5fa;
    --accent-hover: #93c5fd;
}

body {
    background: var(--bg-primary);
    color:      var(--text-primary);
    transition: background 0.2s, color 0.2s;
}

button {
    background: var(--accent);
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
}

button:hover { background: var(--accent-hover); }

.card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
}
```

---

## JavaScript — initialize and watch

```html
<!-- frontend/index.html -->
<script src="vesper.js"></script>
<script src="vesper-theme.js"></script>
<script>
async function initTheme() {
    const { theme } = await vesper.theme.get()
    applyTheme(theme)
}

function applyTheme(theme) {
    document.documentElement.setAttribute(
        "data-theme",
        theme === "Dark" ? "dark" : "light"
    )
}

// Apply on startup
initTheme()

// Update in real time when OS theme changes
vesper.theme.onChange(({ theme }) => applyTheme(theme))
</script>
```

---

## Manual theme toggle (override OS preference)

Add a toggle button that overrides the OS theme:

```js
let manualTheme = null   // null = follow OS

document.getElementById("theme-toggle").onclick = async () => {
    const { theme } = await vesper.theme.get()
    const current = manualTheme ?? theme
    manualTheme = current === "Dark" ? "Light" : "Dark"
    applyTheme(manualTheme)
}

// Modified applyTheme respects manual override
function applyTheme(theme) {
    const resolved = manualTheme ?? theme
    document.documentElement.setAttribute(
        "data-theme",
        resolved === "Dark" ? "dark" : "light"
    )
    document.getElementById("theme-toggle").textContent =
        resolved === "Dark" ? "☀ Light mode" : "☾ Dark mode"
}

// When OS changes, only update if no manual override
vesper.theme.onChange(({ theme }) => {
    if (!manualTheme) applyTheme(theme)
})
```

Persist the manual override across launches with `vesper-store`:

```js
async function init() {
    manualTheme = await vesper.store.get("manual-theme")   // null if never set
    const { theme } = await vesper.theme.get()
    applyTheme(theme)
}

// On toggle:
await vesper.store.set("manual-theme", manualTheme)
// On reset to OS:
await vesper.store.delete("manual-theme")
manualTheme = null
```

---

## Tailwind CSS

If you are using Tailwind with `darkMode: 'class'`:

```js
// vite.config.js — nothing extra needed, Tailwind handles class-based dark

// In your theme init:
function applyTheme(theme) {
    if (theme === "Dark") {
        document.documentElement.classList.add("dark")
    } else {
        document.documentElement.classList.remove("dark")
    }
}
```

```html
<!-- Example component -->
<div class="bg-white dark:bg-gray-900 text-gray-900 dark:text-white p-4 rounded-lg">
    Content
</div>
```

---

## System default (no plugin required)

If you only need to match the OS theme at startup and do not need real-time change events, CSS media queries alone are sufficient — no plugin required:

```css
@media (prefers-color-scheme: dark) {
    :root {
        --bg-primary: #111827;
        --text-primary: #f9fafb;
    }
}
```

Use `vesper-theme` when you need the theme in JavaScript (to store the preference, show a toggle, or emit events to secondary windows).
