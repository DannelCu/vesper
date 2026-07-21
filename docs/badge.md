# Taskbar Progress & Badges

Show progress on the taskbar button or a count on the dock icon.

```js
await vesper.badge.setProgress(0.4)   // 40%
await vesper.badge.clearProgress()

await vesper.badge.setBadge(3)        // "3" on the dock icon
await vesper.badge.clearBadge()       // setBadge(0) also clears
```

```python
from vesper.core import badge

badge.set_progress(0.4)
badge.clear_progress()
```

## Support is uneven — check the return value

| Platform | Progress | Badge |
|---|---|---|
| macOS | Dock tile percentage (needs pyobjc) | Dock tile count (needs pyobjc) |
| Windows | `ITaskbarList3` (needs comtypes) | Not implemented |
| Linux | Unity LauncherEntry (needs dbus) | Unity LauncherEntry |

Every function returns a boolean and never raises. `False` means the platform could
not do it — a missing native dependency, or a desktop with no such concept.

```js
if (!await vesper.badge.setProgress(0.5)) {
  // Fall back to in-window progress.
}
```

Three caveats worth knowing before you rely on this:

- **Linux is a no-op on most systems.** The Unity LauncherEntry D-Bus protocol is
  implemented by KDE Plasma and by GNOME with Dash-to-Dock, but not by plain GNOME.
- **macOS has no dock progress bar.** `setProgress()` writes a percentage into the
  badge instead, which is visible in the same place.
- **Windows badges are unimplemented.** An overlay icon must be a real `HICON`, so
  rendering a number means generating a bitmap at runtime — more machinery than the
  feature earns. It returns `False` rather than pretending.

Native dependencies are imported lazily inside each backend, so a missing pyobjc or
comtypes degrades to a no-op instead of breaking `import vesper`. Unavailability is
logged once, not on every update, so a progress bar in a loop does not flood the log.

## Clipboard images

Related, and in the same spirit:

```js
const dataUrl = await vesper.clipboard.readImage()   // null when no image
if (dataUrl) document.querySelector("img").src = dataUrl

await vesper.clipboard.writeImage(dataUrl)
```

Images cross the IPC bridge as base64 PNG data URLs, since the bridge is JSON and
cannot carry raw bytes — and a data URL drops straight into an `<img src>`.
`writeImage()` accepts either a full data URL or bare base64.
