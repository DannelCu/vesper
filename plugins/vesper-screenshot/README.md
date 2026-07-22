# vesper-screenshot

Screen capture for Vesper via [mss](https://github.com/BoboTiG/python-mss): full virtual screen, individual monitors, or a pixel region — returned as a PNG data URL or written straight to a scope-validated file.

---

## Install

```bash
pip install vesper-screenshot
```

---

## Setup

```python
from vesper import App
from vesper_screenshot import ScreenshotPlugin

app = App(
    frontend="dist/index.html",
    fs_scope=["/home/user/my-app-data"],
    plugins=[ScreenshotPlugin()],
)
```

---

## JavaScript API

```toml
[plugins]
screenshot = "vesper-screenshot"
```

```bash
vesper sync-sdk
```

```html
<script src="vesper.js"></script>
<script src="vesper-screenshot.js"></script>
```

```js
// Whole virtual screen, as a data URL — drop straight into an <img>.
img.src = await vesper.screenshot.capture()

// One monitor (1..N; 0 is the whole virtual screen)
img.src = await vesper.screenshot.capture({ monitor: 1 })

// A region, in pixels
img.src = await vesper.screenshot.capture({
    region: { left: 100, top: 100, width: 800, height: 600 },
})

// Straight to disk (path honours the app's fs scope)
const path = await vesper.screenshot.captureToFile("/home/user/my-app-data/shot.png")

// Monitor geometry as the capture backend sees it
const monitors = await vesper.screenshot.monitors()
```

Check availability before offering the feature in your UI:

```js
const caps = await vesper.capabilities()
captureButton.hidden = !caps.screenshot
```

---

## Platform limitations — read before shipping

### macOS: Screen Recording permission (manual)

Captures require the **Screen Recording** permission, which cannot be granted programmatically:

1. macOS prompts the first time the app attempts a capture.
2. The user enables the app under **System Settings → Privacy & Security → Screen Recording**.
3. The app must be **restarted** — the permission is read at process start.

Without it, captures fail or come back black. The plugin surfaces this as an explanatory error, and `vesper.capabilities().screenshot` notes the requirement in `vesper doctor`.

### Linux: Wayland does not work

mss reads X11/XRandR. Under a **pure Wayland session there is nothing for it to read** — captures fail with a clear error, and `vesper doctor` reports the capability as N/A (there is nothing to install; it is a session fact). X11 sessions and XWayland-visible content work. The correct Wayland route is the XDG desktop portal (`org.freedesktop.portal.Screenshot`), which is a candidate future backend for this plugin, not a current one.

### Windows

Works without extra permissions. DPI-scaled monitors report physical pixels.
