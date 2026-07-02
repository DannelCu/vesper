# Events

Events let Python push data to the JavaScript frontend without waiting for a request. They are one-way: Python emits, JavaScript listens.

---

## Emitting from Python

```python
app.emit("notification", {"title": "Done", "body": "Task complete"})
```

`app.emit(event, payload)` dispatches a `CustomEvent("vesper:<event>", { detail: payload })` to the frontend via `window.evaluate_js`.

The event name is arbitrary — use any string that makes sense for your domain.

---

## Listening in JavaScript

```js
const unsubscribe = vesper.on("notification", (payload) => {
    console.log(payload.title, payload.body)
})
```

`vesper.on(event, handler)` returns an unsubscribe function. Call it when the component unmounts or you no longer need the listener:

```js
const stop = vesper.on("tick", (data) => updateUI(data))

// later:
stop()
```

---

## Common pattern: background worker

```python
import threading, time

@app.command
def start_task():
    def run():
        for i in range(10):
            time.sleep(0.5)
            app.emit("progress", {"percent": (i + 1) * 10})
        app.emit("done", {"result": "finished"})

    threading.Thread(target=run, daemon=True).start()
```

```js
vesper.on("progress", ({ percent }) => {
    progressBar.style.width = percent + "%"
})

vesper.on("done", ({ result }) => {
    console.log("Task:", result)
})

await vesper.invoke("start_task")
```

---

## Emitting from a secondary window

`WindowHandle.emit()` sends an event to that specific window only:

```python
settings_win = app.register_window(title="Settings", ...)

@app.command
def notify_settings(message: str):
    settings_win.emit("message", {"text": message})
```

`app.emit()` sends to the main window. `handle.emit()` sends to a specific secondary window. There is no broadcast-to-all mechanism — emit to each window individually if needed.

---

## Event naming

Vesper prefixes all events with `vesper:` internally. The `vesper.on()` helper and `app.emit()` both strip/add this prefix for you — you only use the short name (`"notification"`, not `"vesper:notification"`).

Built-in events dispatched by the framework:

| Event name | When |
|---|---|
| `theme:change` | OS dark/light mode changes (requires vesper-theme with `watch=True`) |
| `shortcut` | A registered global shortcut fires (requires vesper-shortcuts) |

---

## Payload format

The `payload` argument to `app.emit()` must be JSON-serializable (dict, list, string, number, bool, None). The handler in JavaScript receives the deserialized value directly.

```python
app.emit("data", [1, 2, 3])            # JS receives [1, 2, 3]
app.emit("flag", True)                 # JS receives true
app.emit("result", {"ok": True})       # JS receives { ok: true }
```
