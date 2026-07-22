# Recipe: Menubar / Tray App

A small window that lives near the tray: hidden by default, summoned by the tray icon, positioned in the corner of the monitor the user is working on, dismissed on blur.

**Honesty first:** the exact position of the tray icon is not obtainable — pystray does not expose the icon's coordinates on any platform, so "anchor a popover to the icon" is not buildable. The supported pattern, and what most of the ecosystem ships, is *corner of the active monitor*, which is what this recipe does.

---

## Python

```python
from vesper import App, TrayMenuItem

app = App(
    title="Quick Notes",
    width=360,
    height=480,
    frameless=True,
    on_top=True,
    minimized=True,          # start out of the way; the tray summons it
)

@app.command
def hide_window() -> None:
    app.window.minimize()

app.tray(
    icon="icon.png",
    menu=[
        TrayMenuItem("Show", action=lambda: app.window.restore()),
        None,
        TrayMenuItem("Quit", action=lambda: app.quit()),
    ],
    title="Quick Notes",
)

if __name__ == "__main__":
    app.run()
```

Requires the tray extra: `pip install "vesper[tray]"`.

---

## Frontend

Position into the corner when shown, dismiss on blur:

```js
// Snap to the top-right of the monitor the cursor is on, just off the corner.
async function intoCorner() {
    await vesper.window.position("top-right", {
        screen: "cursor",                 // primary on Linux — see note below
        offset: { x: -12, y: 12 },
    })
}

// The tray "Show" restores the window; reposition every time it comes back.
vesper.on("restore", intoCorner)
intoCorner()

// Menubar apps dismiss when they lose focus.
vesper.on("blur", () => vesper.invoke("hide_window"))
```

---

## Platform notes

- **`screen: "cursor"`** resolves the monitor under the cursor via `ctypes` on Windows and pyobjc on macOS — nothing to install. On Linux there is no dependency-free way to ask, so it falls back to the primary monitor.
- **Corner choice:** `top-right` matches macOS menubar convention; on Windows the tray lives at the bottom-right, so `bottom-right` with a negative y offset feels more native there. Branch on `(await vesper.os.info()).platform` if you care.
- **Dismiss-on-blur** uses the `blur` lifecycle event, which fires when the user clicks elsewhere. Keep the handler idempotent — some backends fire blur more than once.
