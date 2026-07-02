# Native Notifications

Vesper sends native desktop notifications without any extra dependencies. The notification appears in the OS notification center.

---

## From JavaScript

```js
await vesper.notify("Download complete", "report.pdf has been saved.")
```

---

## From Python

```python
app.notify("Download complete", "report.pdf has been saved.")
```

Notifications are fire-and-forget. `app.notify()` returns immediately — the notification runs in a background daemon thread.

---

## Platform implementation

| Platform | Method |
|---|---|
| Windows | PowerShell `ShowBalloonTip` via `System.Windows.Forms.NotifyIcon` |
| macOS | `osascript display notification` |
| Linux | `notify-send` |

No pip dependencies. The Linux implementation requires `notify-send` to be installed on the system (available by default on most desktop distributions).

---

## Special character handling

Special characters in the title and body are escaped per platform:
- Windows: single quotes escaped for PowerShell
- macOS: backslashes and double quotes escaped for AppleScript
- Linux: passed directly to `notify-send`

---

## Limitations

- No click callbacks — Vesper cannot detect when the user clicks a notification
- On Windows, the notification requires a system tray icon to be visible in some configurations; `vesper[tray]` ensures one is present
- On macOS, the app must be signed and notarized for notifications to appear in some system configurations

For rich interactive notifications, consider using the system tray (see [Tray](tray.md)) or a custom in-app notification component in the frontend.
