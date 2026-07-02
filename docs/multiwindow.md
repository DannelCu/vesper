# Multi-Window

Vesper supports multiple windows sharing the same IPC registry. Secondary windows start hidden and are shown on demand via a `WindowHandle`.

---

## Registering a secondary window

```python
from vesper import App

app = App(title="Main", frontend="dist/index.html")

settings = app.register_window(
    title="Settings",
    width=600,
    height=400,
    frontend="dist/settings.html",
)
```

`app.register_window(**kwargs)` accepts the same parameters as `App.__init__` (except `frontend` is required). It returns a `WindowHandle`.

Secondary windows share the main app's IPC registry — all `@app.command` functions and module commands are reachable from any window.

---

## Showing and hiding windows

```python
@app.command
def open_settings():
    settings.show()

@app.command
def close_settings():
    settings.hide()
```

Windows start hidden. Call `handle.show()` to make them visible. `handle.hide()` hides without destroying (the window can be shown again). `handle.close()` destroys the window permanently.

---

## WindowHandle API

| Method | Description |
|---|---|
| `show()` | Show the window |
| `hide()` | Hide the window (preserves state) |
| `close()` | Destroy the window |
| `emit(event, payload)` | Push an event to this specific window |

All methods are no-ops before `app.run()` starts.

---

## Emitting events to a specific window

```python
@app.command
def send_to_settings(message: str):
    settings.emit("update", {"message": message})
```

In `settings.html`:

```js
vesper.on("update", ({ message }) => {
    document.getElementById("msg").textContent = message
})
```

`handle.emit()` dispatches only to that window. `app.emit()` dispatches only to the main window. There is no broadcast mechanism — emit to each window you need individually.

---

## Dev mode

In development (`vesper dev`), secondary windows also use `VESPER_DEV_URL`. The URL is constructed as `{VESPER_DEV_URL}/{filename}` using the basename of the `frontend` path. The disk existence check is skipped.

For example, if `VESPER_DEV_URL=http://localhost:5173` and `frontend="dist/settings.html"`, the dev URL becomes `http://localhost:5173/settings.html`.

This means your Vite project must serve `settings.html` as a separate entry point (add it to `vite.config.js` as a second input).

---

## Full example

```python
from vesper import App

app = App(title="My App", frontend="dist/index.html")

settings_win = app.register_window(
    title="Settings",
    width=700,
    height=500,
    frontend="dist/settings.html",
)

about_win = app.register_window(
    title="About",
    width=400,
    height=300,
    frontend="dist/about.html",
)

@app.command
def open_settings():
    settings_win.show()

@app.command
def open_about():
    about_win.show()

if __name__ == "__main__":
    app.run()
```

```js
// In main window (index.html)
document.getElementById("settings-btn").onclick = () =>
    vesper.invoke("open_settings")

document.getElementById("about-btn").onclick = () =>
    vesper.invoke("open_about")
```

For sharing state across windows see [Recipes — State Between Windows](recipes/state-between-windows.md).
