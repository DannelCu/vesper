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

Each entry has `width`, `height`, `x`, and `y` (position of the top-left corner of the monitor).

---

## Custom titlebar pattern

A common use case is to hide the native titlebar and implement a custom one in HTML. Configure the window without a titlebar and wire the drag/close controls yourself:

```python
app = App(
    title="My App",
    frontend="dist/index.html",
    frameless=True,   # removes the native titlebar (PyWebView option)
)
```

In your HTML, implement drag and controls:

```html
<div id="titlebar">
    <span>My App</span>
    <div class="controls">
        <button onclick="vesper.window.minimize()">─</button>
        <button onclick="vesper.window.maximize()">□</button>
        <button onclick="vesper.quit()">✕</button>
    </div>
</div>
```

Add `-webkit-app-region: drag` CSS to make the titlebar draggable:

```css
#titlebar {
    -webkit-app-region: drag;
    height: 32px;
    display: flex;
    align-items: center;
}

#titlebar .controls {
    -webkit-app-region: no-drag;  /* buttons must be no-drag */
}
```

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
- `vesper:screen:list`
- `vesper:app:quit`

All are filtered from `vesper sync-types` output.
