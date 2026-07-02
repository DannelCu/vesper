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

Tray callbacks run in the pystray thread. For anything that touches the PyWebView window (like `window.show()`), the callback is dispatched correctly because PyWebView handles thread-safe calls internally. For long operations, use a background thread:

```python
import threading

def export_action():
    threading.Thread(target=heavy_export, daemon=True).start()

app.tray(
    icon="icon.png",
    menu=[TrayMenuItem("Export", export_action)],
)
```

---

## Lifecycle

- The tray starts in a background thread via `pystray.Icon.run_detached()` before `webview.start()`.
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
