# Power Management

Two separate things: asking the machine to **stay awake**, and being **told** when it
sleeps, wakes, locks or unlocks.

## Keeping the machine awake

Keep the machine awake while your app is doing something the user is waiting on — a
long export, a download, a render.

```python
from vesper.core import power

power.prevent_sleep("Exporting video")
try:
    do_long_work()
finally:
    power.allow_sleep()
```

From the frontend:

```js
await vesper.power.preventSleep("Exporting video")
// ...
await vesper.power.allowSleep()
```

### Platform backends

| Platform | Mechanism |
|---|---|
| macOS | A `caffeinate -d -i` subprocess, terminated on release |
| Windows | `SetThreadExecutionState` via ctypes |
| Linux | `systemd-inhibit`, falling back to `xdg-screensaver` |

The `reason` string is shown by the OS where it surfaces inhibitors — `systemd-inhibit
--list` on Linux, for example.

### Degradation

`prevent_sleep()` returns `True` when the request was registered and `False` when the
platform offers no way to do it. It never raises: a missing helper binary must not be
able to take down `app.run()`.

Check the return value when it matters:

```python
if not power.prevent_sleep("Rendering"):
    log.info("Sleep prevention unavailable; the machine may suspend")
```

The `xdg-screensaver` fallback is weaker than the others — it defers the screensaver
but is not a true sleep inhibitor. It is used only when `systemd-inhibit` is absent.

### Notes

- Calls are idempotent: a second `prevent_sleep()` while one is held does not stack
  another inhibitor, and a single `allow_sleep()` releases it.
- Always release in a `finally`, or the machine stays awake after your task fails.

---

## Listening for power events

Opt in with `power_events=True`. The app then emits four events to the frontend:

```python
app = App(title="My App", power_events=True)
```

```js
vesper.on("power:suspend", () => saveDraft())
vesper.on("power:resume",  () => reconnect())
vesper.on("power:lock",    () => blurSensitiveData())
vesper.on("power:unlock",  () => refresh())
```

It is off by default because it costs a D-Bus connection or a hidden message window,
and most apps do not need it.

Typical uses: flush unsaved work before the machine suspends, re-open a socket that
died while it slept, and hide sensitive content while the screen is locked.

### What each platform actually delivers

Read this table before relying on an event. It is **best-effort**: where a platform
does not publish a signal, the event simply never fires — there is no error and no
fallback.

| Event | macOS | Windows | Linux |
|---|---|---|---|
| `power:suspend` | `NSWorkspaceWillSleepNotification` | `WM_POWERBROADCAST` / `PBT_APMSUSPEND` | logind `PrepareForSleep(true)` |
| `power:resume` | `NSWorkspaceDidWakeNotification` | `PBT_APMRESUME*` | logind `PrepareForSleep(false)` |
| `power:lock` | `com.apple.screenIsLocked` | `WTS_SESSION_LOCK` | screensaver `ActiveChanged(true)` |
| `power:unlock` | `com.apple.screenIsUnlocked` | `WTS_SESSION_UNLOCK` | screensaver `ActiveChanged(false)` |

Requirements and caveats per platform:

- **macOS** needs **pyobjc**, which pywebview already installs. Observers are attached
  to the main run loop, so events arrive only while `app.run()` is running. The
  lock/unlock notification names are undocumented by Apple — they have been stable for
  many years, but they are not a supported API.
- **Windows** needs nothing extra. Vesper creates a message-only window (`HWND_MESSAGE`,
  never displayed) to receive the broadcasts. A user-initiated wake sends *two* resume
  messages; Vesper collapses them into one `power:resume`.
- **Linux** needs **jeepney** (`pip install jeepney`) and a D-Bus session.
  Suspend/resume come from systemd-logind on the system bus; lock/unlock come from
  whichever screensaver the desktop publishes. Vesper matches the GNOME, Cinnamon and
  freedesktop interfaces — a desktop that publishes none of them reports no lock
  events. Without jeepney the monitor logs once at debug level and does nothing.

`power:suspend` gives you very little time. The OS does not wait for your handler —
write the file, do not start a network request.

### Degradation

`start_power_monitor()` returns `False` when nothing is available. The `App` wiring
logs this at debug level and carries on; an app that cannot function without the
events should check for itself:

```python
from vesper.core import power

if not power.start_power_monitor(app.window.emit):
    log.info("Power events unavailable; falling back to periodic autosave")
```
