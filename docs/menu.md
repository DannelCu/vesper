# Menu Bar

Vesper supports a native application menu bar — the top-level menus that appear in the application's title bar (Windows/Linux) or the macOS global menu bar.

---

## Basic setup

```python
from vesper import App, MenuItem

app = App(title="My App", frontend="dist/index.html")

app.menu([
    MenuItem("File", submenu=[
        MenuItem("New",  action=lambda: app.emit("new-file", {})),
        MenuItem("Open", action=lambda: app.emit("open-file", {})),
        None,  # separator
        MenuItem("Quit", action=lambda: app.quit()),
    ]),
    MenuItem("Edit", submenu=[
        MenuItem("Cut",   action=lambda: None),
        MenuItem("Copy",  action=lambda: None),
        MenuItem("Paste", action=lambda: None),
    ]),
    MenuItem("Help", submenu=[
        MenuItem("About", action=lambda: about_win.show()),
    ]),
])

if __name__ == "__main__":
    app.run()
```

`app.menu()` must be called before `app.run()`.

---

## MenuItem

```python
from vesper import MenuItem

MenuItem(label, action=None, submenu=None)
```

| Parameter | Type | Description |
|---|---|---|
| `label` | `str` | Menu or item label |
| `action` | `Callable \| None` | Zero-argument callable for leaf items |
| `submenu` | `list \| None` | List of `MenuItem` / `None` for nested menus |

A `MenuItem` with a `submenu` creates a top-level or nested menu. A `MenuItem` with an `action` creates a clickable menu item. `None` in a list inserts a separator.

---

## Nested submenus

```python
MenuItem("Tools", submenu=[
    MenuItem("Database", submenu=[
        MenuItem("Migrate", action=run_migrations),
        MenuItem("Seed",    action=seed_database),
    ]),
    MenuItem("Logs", action=open_logs),
])
```

Arbitrarily deep nesting is supported.

---

## Triggering frontend actions from menu items

Menu item callbacks run in a Python thread. Use `app.emit()` to notify the frontend:

```python
app.menu([
    MenuItem("View", submenu=[
        MenuItem("Toggle Sidebar", action=lambda: app.emit("toggle-sidebar", {})),
    ]),
])
```

```js
vesper.on("toggle-sidebar", () => {
    sidebar.classList.toggle("hidden")
})
```

---

## Platform notes

- **macOS**: The menu replaces the system application menu in the global menu bar at the top of the screen.
- **Windows / Linux**: The menu appears as an inline menu bar within the application window.
- Menu items without an `action` and without a `submenu` are rendered as disabled no-op items. Always provide one or the other.

---

## MenuItem is exported from the package

```python
from vesper import MenuItem   # shortcut
from vesper.core.menu import MenuItem  # same class
```
