# vesper-notify

Rich notifications for Vesper: click callbacks, action buttons, custom icons and sound, via [desktop-notifier](https://github.com/samschott/desktop-notifier).

The core's `vesper.notify(title, body)` stays untouched as the minimal, dependency-free fallback (PowerShell / osascript / notify-send). This plugin adds the one thing those backends cannot do: telling you the user responded. `vesper.capabilities().notifications` reflects which backend is active.

---

## Install

```bash
pip install vesper-notify
```

---

## Setup

```python
from vesper import App
from vesper_notify import NotifyPlugin

app = App(
    frontend="dist/index.html",
    plugins=[NotifyPlugin(app_name="My App")],
)
```

`app_name` is what the OS shows as the notification's source.

---

## JavaScript API

```toml
[plugins]
notify = "vesper-notify"
```

```bash
vesper sync-sdk
```

```html
<script src="vesper.js"></script>
<script src="vesper-notify.js"></script>
```

```js
const id = await vesper.notifyRich.send("Export finished", {
    body: "report.pdf is ready",
    buttons: ["Open", "Reveal"],
    icon: "/path/to/icon.png",
    sound: true,
    onClick: () => focusReport(),                 // body clicked
    onAction: (button) => {                       // button pressed
        if (button === "Open") openReport()
        if (button === "Reveal") vesper.shell.reveal("/path/report.pdf")
    },
})
```

The namespace is `vesper.notifyRich` (the core owns `vesper.notify`). Raw events are also available: `vesper.on("notify:clicked", ...)` and `vesper.on("notify:action", ...)`, both carrying the notification `id`.

---

## Python API

```python
plugin = NotifyPlugin(app_name="My App")
app = App(plugins=[plugin])

notify_id = plugin.send(
    "Export finished",
    "report.pdf is ready",
    buttons=["Open"],
    icon="icon.png",
    sound=True,
)
```

---

## Platform limitations

### macOS: callbacks require a signed bundle — read this

The macOS notification centre **ignores callbacks from unsigned processes**. In development (`python app.py`, `vesper dev`) notifications appear, but `onClick`/`onAction` never fire — this is macOS policy, not a bug. For callbacks to work the app must be:

1. Packaged as an `.app` bundle (`vesper package`), and
2. Signed — `vesper sign` with a `[sign]` section in `vesper.toml`; see [docs/code-signing.md](../../docs/code-signing.md). The entitlements that `vesper sign` applies are sufficient; no extra ones are needed for notifications.

Clicking the notification brings the app to the foreground before the callback fires.

### Windows

Buttons and callbacks are delivered through WinRT toasts. On an unpackaged Python process, Windows attributes the toast to Python rather than your app; packaging fixes attribution.

### Linux

Requires a notification server implementing the freedesktop spec with action support (GNOME and KDE both qualify). Servers without action support show the notification but drop the buttons.

---

## Verification note

CI covers the calls this plugin builds and the event wiring, with the notifier mocked; the visible bubble and real click delivery are verified manually per platform — see the coverage table in KNOWN-ISSUES.md.
