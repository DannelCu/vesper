# Recipe: User Preferences with vesper-store

This recipe builds a persistent settings panel using the `vesper-store` plugin. Settings are saved to disk and restored on every launch.

---

## Setup

```bash
pip install vesper-store
vesper sync-sdk   # copies vesper-store.js to frontend/ or public/
```

```toml
# vesper.toml
[plugins]
store = "vesper-store"
```

```python
# app.py
from vesper import App
from vesper_store import StorePlugin

app = App(
    title="My App",
    frontend="frontend/index.html",
    plugins=[StorePlugin(app_name="my-app")],
)

# Default preferences
DEFAULTS = {
    "theme": "system",
    "font_size": 14,
    "language": "en",
    "notifications": True,
    "sidebar_width": 240,
}

@app.command
async def get_all_prefs() -> dict:
    prefs = {}
    for key, default in DEFAULTS.items():
        stored = await app.ipc.handle({
            "id": "pref",
            "command": "store:get",
            "args": {"key": f"pref:{key}"},
        })
        prefs[key] = stored["result"] if stored["ok"] and stored["result"] is not None else default
    return prefs

@app.command
async def set_pref(key: str, value) -> None:
    if key not in DEFAULTS:
        raise ValueError(f"Unknown preference: {key}")
    await app.ipc.handle({
        "id": "pref",
        "command": "store:set",
        "args": {"key": f"pref:{key}", "value": value},
    })
    app.emit("pref-changed", {"key": key, "value": value})

@app.command
async def reset_prefs() -> dict:
    for key, default in DEFAULTS.items():
        await app.ipc.handle({
            "id": "pref",
            "command": "store:set",
            "args": {"key": f"pref:{key}", "value": default},
        })
    app.emit("prefs-reset", DEFAULTS)
    return DEFAULTS

if __name__ == "__main__":
    app.run()
```

---

## Settings panel (HTML)

```html
<!-- frontend/settings.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Settings</title>
    <style>
        body { font-family: system-ui; padding: 24px; max-width: 480px; }
        .setting { display: flex; justify-content: space-between; align-items: center;
                   padding: 12px 0; border-bottom: 1px solid #e5e7eb; }
        label { font-weight: 500; }
        select, input { padding: 4px 8px; border: 1px solid #d1d5db; border-radius: 4px; }
        .actions { margin-top: 24px; display: flex; gap: 8px; }
        button { padding: 8px 16px; border-radius: 4px; cursor: pointer; border: none; }
        .btn-primary { background: #3b82f6; color: white; }
        .btn-secondary { background: #f3f4f6; }
    </style>
</head>
<body>
    <h2>Settings</h2>

    <div class="setting">
        <label>Theme</label>
        <select id="theme">
            <option value="system">System default</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
        </select>
    </div>

    <div class="setting">
        <label>Font size</label>
        <input type="number" id="font-size" min="10" max="24" step="1" />
    </div>

    <div class="setting">
        <label>Language</label>
        <select id="language">
            <option value="en">English</option>
            <option value="es">Spanish</option>
            <option value="fr">French</option>
        </select>
    </div>

    <div class="setting">
        <label>Notifications</label>
        <input type="checkbox" id="notifications" />
    </div>

    <div class="actions">
        <button class="btn-primary" onclick="saveAll()">Save</button>
        <button class="btn-secondary" onclick="resetAll()">Reset to defaults</button>
    </div>

    <script src="vesper.js"></script>
    <script src="vesper-store.js"></script>
    <script>
    let current = {}

    async function load() {
        current = await vesper.invoke("get_all_prefs")
        document.getElementById("theme").value         = current.theme
        document.getElementById("font-size").value     = current.font_size
        document.getElementById("language").value      = current.language
        document.getElementById("notifications").checked = current.notifications
    }

    async function saveAll() {
        const updates = {
            theme:         document.getElementById("theme").value,
            font_size:     parseInt(document.getElementById("font-size").value),
            language:      document.getElementById("language").value,
            notifications: document.getElementById("notifications").checked,
        }

        for (const [key, value] of Object.entries(updates)) {
            if (value !== current[key]) {
                await vesper.invoke("set_pref", { key, value })
            }
        }

        current = { ...current, ...updates }
        alert("Settings saved.")
    }

    async function resetAll() {
        if (!confirm("Reset all settings to defaults?")) return
        current = await vesper.invoke("reset_prefs")
        await load()
    }

    load()
    </script>
</body>
</html>
```

---

## Applying preferences in the main window

```js
// frontend/index.html — apply prefs on load and when changed

async function applyPrefs(prefs) {
    document.documentElement.style.fontSize = prefs.font_size + "px"
    document.documentElement.setAttribute("data-theme", prefs.theme)
    // etc.
}

// Load on startup
const prefs = await vesper.invoke("get_all_prefs")
applyPrefs(prefs)

// Apply changes in real time
vesper.on("pref-changed", ({ key, value }) => {
    if (key === "font_size") document.documentElement.style.fontSize = value + "px"
    if (key === "theme")     document.documentElement.setAttribute("data-theme", value)
})

vesper.on("prefs-reset", (allPrefs) => applyPrefs(allPrefs))
```

---

## Direct JS access via vesper-store

For simple apps that do not need a Python command layer, access the store directly from JS:

```js
// Read a preference
const theme = await vesper.store.get("pref:theme") ?? "system"

// Write a preference
await vesper.store.set("pref:theme", "dark")

// Check existence
const hasTheme = await vesper.store.has("pref:theme")
```

The IPC command names are `store:get`, `store:set`, `store:delete`, `store:has`, `store:clear`, `store:keys`.
