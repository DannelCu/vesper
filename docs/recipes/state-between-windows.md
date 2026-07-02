# Recipe: State Between Windows

Secondary windows in Vesper share the main app's IPC registry — any command registered via `@app.command` or in a controller is callable from any window. This is the primary mechanism for sharing state.

---

## Pattern 1: Python as the source of truth

Keep all state in Python. Both windows read and write through IPC commands. Neither window stores state locally — they always fetch from Python.

```python
# app.py
from vesper import App

app = App(title="Main", frontend="dist/index.html")

settings_win = app.register_window(
    title="Settings",
    width=600,
    height=400,
    frontend="dist/settings.html",
)

# ── Shared state ─────────────────────────────────────────────────────────────

_prefs = {
    "theme": "light",
    "font_size": 14,
    "show_sidebar": True,
}

@app.command
def get_prefs() -> dict:
    return _prefs.copy()

@app.command
def set_pref(key: str, value) -> None:
    _prefs[key] = value
    # Notify both windows of the change
    app.emit("prefs-changed", {key: value})
    settings_win.emit("prefs-changed", {key: value})

@app.command
def open_settings():
    settings_win.show()

if __name__ == "__main__":
    app.run()
```

**In both `index.html` and `settings.html`:**

```js
// Load prefs on startup
const prefs = await vesper.invoke("get_prefs")
applyPrefs(prefs)

// Listen for changes from any window
vesper.on("prefs-changed", (changes) => {
    applyPrefs(changes)
})
```

**In `settings.html` (the settings panel):**

```js
document.getElementById("theme-select").onchange = async (e) => {
    await vesper.invoke("set_pref", { key: "theme", value: e.target.value })
}
```

---

## Pattern 2: Events for one-time notifications

For transient messages that do not need to be persisted, emit an event from one window action and handle it in another.

```python
@app.command
def notify_main(message: str):
    app.emit("notification", {"text": message, "from": "settings"})
```

```js
// In main window
vesper.on("notification", ({ text, from }) => {
    showToast(`${from}: ${text}`)
})

// In settings window
await vesper.invoke("notify_main", { message: "Settings saved!" })
```

---

## Pattern 3: Shared module service

With the module system, a singleton service is the natural shared state holder. All controllers that receive the service via DI see the same instance.

```python
from vesper import Injectable, Controller, command, Module, App

@Injectable()
class AppState:
    def __init__(self):
        self.selected_item = None
        self.filters: dict = {}

    def select(self, item_id: int):
        self.selected_item = item_id

    def set_filter(self, key: str, value):
        self.filters[key] = value


@Controller("state")
class StateController:
    def __init__(self, state: AppState):
        self.state = state

    @command
    def get_selected(self) -> int | None:
        return self.state.selected_item

    @command
    def select_item(self, item_id: int) -> None:
        self.state.select(item_id)

    @command
    def get_filters(self) -> dict:
        return self.state.filters.copy()


@Module(controllers=[StateController], providers=[AppState])
class AppModule:
    pass
```

Both windows call `vesper.invoke("state.select_item", { item_id: 5 })` and `vesper.invoke("state.get_selected")` — they share the same `AppState` singleton instance.

---

## Syncing state on window open

When a secondary window opens, it should load the current state immediately:

```js
// In settings.html — runs when the page loads
async function init() {
    const prefs = await vesper.invoke("get_prefs")
    populateForm(prefs)

    // Register change listener for live sync
    vesper.on("prefs-changed", (changes) => updateForm(changes))
}

init()
```

---

## When to use which pattern

| Pattern | When to use |
|---|---|
| Python source of truth (IPC commands) | Shared, persistent state that multiple windows read and write |
| Events | One-time notifications, transient messages |
| Module service | When using the module system and DI; cleaner for complex state |
