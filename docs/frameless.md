# Frameless Windows

A frameless window has no native titlebar or borders — the page is the whole window. It is the starting point for custom titlebars, splash-like tool windows, and widget-style apps.

```python
app = App(
    frameless=True,
    easy_drag=False,          # see "Dragging" below
    min_width=400,
    min_height=300,
)
```

All of these also work on secondary windows via `app.register_window(...)`.

---

## Options

| `App(...)` argument | Default | Description |
|---|---|---|
| `frameless` | `False` | Remove the native titlebar and borders. |
| `easy_drag` | `True` | With `frameless=True`, dragging anywhere moves the window. Turn off when using declared drag regions. |
| `transparent` | `False` | Transparent window background. |
| `vibrancy` | `False` | macOS translucency behind the page. Ignored on other platforms. |
| `min_width` / `min_height` | `None` | Minimum window size; must be set together. |

---

## Dragging

A frameless window has no titlebar to grab, so something must be draggable:

- **`easy_drag=True`** (the default): the entire window is draggable. Fine for splash-style windows; wrong for real UIs, where dragging fights with text selection and controls.
- **`easy_drag=False` + drag regions**: mark the elements that should move the window — the functional equivalent of `-webkit-app-region: drag` in Electron.

Declare regions in HTML with the `data-vesper-drag` attribute (wired automatically when `vesper.js` loads):

```html
<header class="titlebar" data-vesper-drag>
    <span class="title">My App</span>
    <button onclick="vesper.window.minimize()">–</button>
</header>
```

Or from JavaScript, for elements created later:

```js
const undo = vesper.window.makeDraggable("#titlebar")
```

Interactive children (buttons, inputs) inside a drag region stay clickable.

Window controls for the custom titlebar are the ordinary window commands: `vesper.window.minimize()`, `maximize()`, `restore()`, and `vesper.quit()`. See the complete [Custom Titlebar recipe](recipes/custom-titlebar.md).

---

## Transparency

`transparent=True` removes the window background so the page's own background (including alpha) shows through. Combine with `frameless=True` for non-rectangular shapes.

Platform reality:

| Platform | Behaviour |
|---|---|
| Windows | Works with WebView2. |
| macOS | Works; combines with `vibrancy=True` for the native translucent material. |
| Linux | Requires a running compositor. Without one (bare X11, some minimal WMs) the "transparent" area renders black. There is no reliable way to detect this from inside the WebView — provide an opaque fallback background. |

---

## Windows 11 backdrop materials (Mica / Acrylic)

On Windows 11 22H2+ the window background can use the system backdrop materials:

```js
const ok = await vesper.window.setBackdrop("mica")     // or "acrylic", "tabbed", "none"
```

Best-effort by design: it resolves `false` on macOS, Linux, Windows 10, and pre-22H2 builds — nothing to install, it is a platform fact. Ask `vesper.capabilities()` for the `mica` key before offering a toggle in your UI. Apply it once at startup (from a `loaded` hook or early frontend code) while the app window is in the foreground.

---

## Gotchas

- **A frameless window cannot be resized from its edges on all platforms equally** — keep `resizable=True` and provide generous `min_width`/`min_height` so users cannot shrink the app into an unusable sliver.
- **Double-click to maximize** is native titlebar behaviour; a custom titlebar has to implement it (the recipe does).
- **`easy_drag` has no effect on framed windows** — it is only read when `frameless=True`.
