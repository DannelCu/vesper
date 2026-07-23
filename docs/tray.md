# System Tray

Vesper can place an icon in the system tray (Windows taskbar notification area, macOS menu bar, Linux status bar) with a right-click context menu.

Requires the `vesper[tray]` extra: `pip install "vesper[tray]"` (installs `pystray` and `Pillow`).

---

## Basic setup

```python
from vesper import App, TrayMenuItem

app = App(title="My App", frontend="dist/index.html")

app.tray(
    icon="assets/icon.png",
    menu=[
        TrayMenuItem("Open",  lambda: app.window.show()),
        None,                                              # separator
        TrayMenuItem("Quit",  lambda: app.quit()),
    ],
    title="My App",   # tooltip shown on hover (optional)
)

if __name__ == "__main__":
    app.run()
```

`app.tray()` must be called before `app.run()`.

---

## TrayMenuItem

```python
from vesper import TrayMenuItem

TrayMenuItem(label="Open", action=lambda: ...)
```

| Parameter | Type | Description |
|---|---|---|
| `label` | `str` | Text shown in the menu |
| `action` | `Callable` | Zero-argument callable invoked when clicked |

`None` in the menu list inserts a visual separator.

---

## Icon

The `icon` parameter accepts a path to an image file. PNG is recommended. The image is loaded with Pillow — any format supported by Pillow works.

For production apps, embed the icon using your bundler:
- PyInstaller: add `datas=[("assets/icon.png", "assets")]` and use `sys._MEIPASS` to locate it at runtime
- Nuitka: `--include-data-files=assets/icon.png=assets/icon.png`

---

## Actions from tray menu items

**Tray callbacks run on a background thread**, one per click, and Vesper guarantees
that on every platform. Window methods are safe to call from them — PyWebView
marshals those onto the GUI thread itself — and slow work does not need wrapping:

```python
def export_action():
    heavy_export()          # already off the GUI thread

app.tray(
    icon="icon.png",
    menu=[TrayMenuItem("Export", export_action)],
)
```

An exception in an action is logged to the `vesper.tray` logger and does not reach
pystray, so one failing item cannot take the menu down with it.

### Why Vesper does this rather than handing you pystray's thread

pystray has no single answer for which thread a menu item runs on. The win32
backend pumps its own message loop on a thread it owns, while the AppIndicator and
GTK backends attach to whatever GLib main loop is already running — which, under
Vesper, is PyWebView's, on the **main** thread.

That difference is not cosmetic. Anything that waits on the GUI loop deadlocks it
when called from the loop itself: `app.emit()` is `evaluate_js`, which schedules
the script with `glib.idle_add` and then blocks until it completes — and the idle
callback cannot run while the loop is blocked waiting for it. A single tray click
that emitted an event froze the entire application: unresponsive window, no further
tray action, not even Quit.

Running each action on its own short-lived thread makes the platforms agree and
makes the rule above simply true.

---

## Lifecycle

- The tray starts via `pystray.Icon.run_detached()` before `webview.start()`. On the
  GTK and AppIndicator backends that attaches the icon to the GLib main loop
  PyWebView goes on to run, rather than starting a thread of its own.
- The tray is stopped in a `finally` block in `app.run()` — it always cleans up on exit, even if the app crashes.

---

## Minimal "background app" pattern

To create an app that lives entirely in the tray without a visible window at startup:

```python
app = App(title="Background App", frontend="dist/index.html")

# Register a secondary window but don't show it immediately
main_win = app.register_window(title="Main", frontend="dist/index.html")

@app.command
def open_main():
    main_win.show()

app.tray(
    icon="icon.png",
    menu=[
        TrayMenuItem("Open", lambda: main_win.show()),
        TrayMenuItem("Quit", lambda: app.quit()),
    ],
)
```

> Note: PyWebView requires at least one window to exist. The primary `App` window is created hidden in this pattern.
