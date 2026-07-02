# Splash Screen

A splash screen is a frameless window that appears while the app loads, then automatically disappears when the main window is ready.

---

## Basic usage

```python
from vesper import App

app = App(title="My App", frontend="dist/index.html")

app.splash("<p style='font-family: sans-serif'>Loading…</p>", width=400, height=300)

if __name__ == "__main__":
    app.run()
```

`app.splash()` must be called before `app.run()`.

When the main window fires its `loaded` event (PyWebView signals this when the page finishes loading), the splash window is destroyed and the main window becomes visible.

---

## Parameters

```python
app.splash(html="", *, width=400, height=300)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `html` | `str` | `""` | Inline HTML string or path to an `.html` file |
| `width` | `int` | `400` | Splash window width in pixels |
| `height` | `int` | `300` | Splash window height in pixels |

---

## Inline HTML

Pass an HTML string to render it directly in the splash window:

```python
app.splash("""
<html>
<body style="margin:0; background:#1a1a2e; display:flex; align-items:center; justify-content:center; height:100vh;">
    <div style="text-align:center; color:white; font-family:sans-serif;">
        <h2>My App</h2>
        <p>Loading…</p>
    </div>
</body>
</html>
""", width=500, height=350)
```

---

## HTML file

Pass a path ending in `.html` to load a file as the splash screen:

```python
app.splash("assets/splash.html", width=600, height=400)
```

The path can be absolute or relative. The splash window is frameless — no titlebar or window chrome is shown.

---

## Empty splash (default loading indicator)

```python
app.splash()   # uses built-in PyWebView blank page
```

An empty `html` string shows a plain white window while the main window loads.

---

## How it works

When `splash` is configured:
1. The main window is created hidden (`hidden=True`)
2. A frameless splash window is created with the provided HTML or URL
3. A `loaded` event handler is registered on the main window
4. When the main window finishes loading, the handler runs: `splash.destroy()` → `main.show()`

The transition is seamless — the splash disappears the moment the main content is ready.

---

## Preloading data before the splash disappears

If you need the app to complete some initialization before dismissing the splash, delay the `app.run()` call or use the `loaded` lifecycle hook:

```python
@app.on("loaded")
def on_loaded():
    # This fires when the main window is ready
    # The splash has already been dismissed at this point
    app.emit("init-complete", {"status": "ready"})
```

For longer initialization that should block the splash, do the work in a background thread before `app.run()`, or use Python's startup sequence naturally — `app.run()` blocks until the window is shown.
