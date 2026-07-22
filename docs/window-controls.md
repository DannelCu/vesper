# Window Controls

Vesper exposes window management commands for minimizing, maximizing, resizing, and moving the application window from either Python or JavaScript.

---

## Minimize

```js
await vesper.window.minimize()
```

```python
app.window.minimize()
```

---

## Maximize / Restore

```js
await vesper.window.maximize()   // maximize
await vesper.window.restore()    // restore to previous size
```

```python
app.window.maximize()
app.window.restore()
```

---

## Toggle Fullscreen

```js
await vesper.window.fullscreen()
```

```python
app.window.toggle_fullscreen()
```

Toggles between fullscreen and the previous window state. Call again to exit fullscreen.

---

## Resize

```js
await vesper.window.resize(1200, 800)   // width, height in pixels
```

```python
app.window.resize(1200, 800)
```

---

## Move

```js
await vesper.window.move(100, 200)   // x, y from top-left corner of the primary screen
```

```python
app.window.move(100, 200)
```

---

## Screen information

Get a list of connected monitors:

```js
const screens = await vesper.screen.list()
// [{ width, height, x, y }, ...]
```

```python
screens = app.window.list_screens()
# [{'width': 1920, 'height': 1080, 'x': 0, 'y': 0}, ...]
```

Each entry has `width`, `height`, `x`, and `y` (position of the top-left corner of the monitor). Coordinates can be negative — a monitor arranged to the left of or above the primary one starts at negative x/y.

---

## Semantic positioning

Place the window at a named position instead of computing pixels:

```js
await vesper.window.position("bottom-right")
await vesper.window.position("top-center", { screen: 1 })
await vesper.window.position("top-right", {
    screen: "cursor",              // the monitor the cursor is on
    offset: { x: -12, y: 12 },     // nudge off the corner
})
```

Positions: `top-left`, `top-center`, `top-right`, `center-left`, `center`, `center-right`, `bottom-left`, `bottom-center`, `bottom-right`.

- `screen` is a monitor index (`0` is primary), or `"cursor"` for the monitor under the cursor. Asking for the cursor needs nothing installed on Windows and macOS; on Linux there is no dependency-free way to know, so `"cursor"` falls back to the primary monitor.
- `offset` is added to the computed position as-is — use negative values to pull a bottom/right-anchored window away from the edge.
- Multi-monitor layouts with negative coordinates work: positioning on a monitor left of the primary produces negative x, as it should.

**Tray apps:** the exact position of *your tray icon* is not obtainable — pystray does not expose it on any platform. The supported pattern for a menubar/tray-style app is "corner of the monitor the user is working on" (`{ screen: "cursor" }`), which is what most of the ecosystem ships. See the [Menubar App recipe](recipes/menubar-app.md).

```python
# From Python
from vesper.core import positioner

screens = app.window.list_screens()
geo = app.window.get_geometry()
x, y = positioner.compute("bottom-right", (geo["width"], geo["height"]), screens)
app.window.move(x, y)
```

---

## Custom titlebar pattern

A common use case is to hide the native titlebar and implement a custom one in HTML: configure `App(frameless=True, easy_drag=False)`, mark your titlebar as a drag region with the `data-vesper-drag` attribute, and wire the buttons to `vesper.window.minimize()` / `maximize()` / `restore()` and `vesper.quit()`.

Note that `-webkit-app-region: drag` is an Electron/Chromium convention — it does **not** work in the system WebViews Vesper renders in. Use the drag-region attribute instead.

The full pattern — options, dragging, transparency, platform differences — lives in [Frameless Windows](frameless.md), with a complete working example in the [Custom Titlebar recipe](recipes/custom-titlebar.md).

---

## Quit the app

```js
await vesper.quit()
```

```python
app.quit()
```

Destroys the main window, which stops the PyWebView event loop and exits the application. Secondary windows are also closed.

---

## IPC command names

All window controls are registered as built-in commands:
- `vesper:window:minimize`
- `vesper:window:maximize`
- `vesper:window:restore`
- `vesper:window:fullscreen`
- `vesper:window:resize`
- `vesper:window:move`
- `vesper:window:position`
- `vesper:window:set_backdrop`
- `vesper:screen:list`
- `vesper:app:quit`

All are filtered from `vesper sync-types` output.
