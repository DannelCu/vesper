# Recipe: Custom Titlebar

A complete, working titlebar for a frameless Vesper window: drag to move, window control buttons, double-click to maximize, and per-platform button placement.

Background reading: [Frameless Windows](../frameless.md).

---

## Python

```python
from vesper import App

app = App(
    title="My App",
    frameless=True,
    easy_drag=False,      # the titlebar declares its own drag region
    min_width=480,
    min_height=320,
)

if __name__ == "__main__":
    app.run()
```

---

## HTML

```html
<header id="titlebar" data-vesper-drag>
    <span class="titlebar-title">My App</span>
    <div class="titlebar-controls">
        <button id="btn-min" title="Minimize">&#x2013;</button>
        <button id="btn-max" title="Maximize">&#x25A1;</button>
        <button id="btn-close" class="danger" title="Close">&#x2715;</button>
    </div>
</header>

<main>
    <!-- your app -->
</main>

<script src="vesper.js"></script>
<script src="titlebar.js"></script>
```

`data-vesper-drag` makes the header a drag region; buttons inside it stay clickable.

---

## CSS

```css
:root {
    --titlebar-height: 36px;
}

body {
    margin: 0;
    font-family: system-ui, sans-serif;
    /* Leave room for the fixed titlebar. */
    padding-top: var(--titlebar-height);
}

#titlebar {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: var(--titlebar-height);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 12px;
    background: #1f2430;
    color: #e6e6e6;
    user-select: none;          /* dragging must not select the title text */
    -webkit-user-select: none;
}

.titlebar-title {
    font-size: 13px;
    pointer-events: none;
}

.titlebar-controls button {
    width: 34px;
    height: 26px;
    margin-left: 4px;
    border: none;
    border-radius: 4px;
    background: transparent;
    color: inherit;
    font-size: 13px;
    cursor: default;
}

.titlebar-controls button:hover { background: rgba(255, 255, 255, 0.12); }
.titlebar-controls button.danger:hover { background: #e81123; color: #fff; }
```

---

## JavaScript (`titlebar.js`)

```js
let maximized = false

document.getElementById("btn-min").onclick = () => vesper.window.minimize()

function toggleMaximize() {
    if (maximized) {
        vesper.window.restore()
    } else {
        vesper.window.maximize()
    }
    maximized = !maximized
}

document.getElementById("btn-max").onclick = toggleMaximize

// Double-click on the titlebar = native maximize behaviour.
document.getElementById("titlebar").addEventListener("dblclick", (e) => {
    // Only when the double-click was on the bar itself, not on a button.
    if (e.target.closest("button")) return
    toggleMaximize()
})

document.getElementById("btn-close").onclick = () => vesper.quit()
```

---

## Platform differences

- **macOS** puts window controls on the **left**, as traffic lights. If you want the app to feel native there, detect the platform and flip the layout:

  ```js
  const { platform } = await vesper.os.info()
  if (platform === "Darwin") {
      document.getElementById("titlebar").classList.add("mac")
  }
  ```

  ```css
  #titlebar.mac { flex-direction: row-reverse; }
  ```

- **Double-click to maximize** is convention on Windows and Linux. On macOS the convention is double-click to zoom *or minimize* depending on a system preference — the simple toggle above is an accepted middle ground.
- **Snap/tiling**: OS features driven by dragging the native titlebar (Windows Snap, GNOME edge tiling) generally still work when the drag starts in a drag region, but Aero Shake and titlebar context menus do not exist for a frameless window. That is the trade-off of owning the titlebar.
- **Linux without a compositor**: if you also use `transparent=True`, give the titlebar (and body) an opaque fallback background — see [Frameless Windows](../frameless.md#transparency).
