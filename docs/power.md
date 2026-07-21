# Power Management

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

## Platform backends

| Platform | Mechanism |
|---|---|
| macOS | A `caffeinate -d -i` subprocess, terminated on release |
| Windows | `SetThreadExecutionState` via ctypes |
| Linux | `systemd-inhibit`, falling back to `xdg-screensaver` |

The `reason` string is shown by the OS where it surfaces inhibitors — `systemd-inhibit
--list` on Linux, for example.

## Degradation

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

## Notes

- Calls are idempotent: a second `prevent_sleep()` while one is held does not stack
  another inhibitor, and a single `allow_sleep()` releases it.
- Always release in a `finally`, or the machine stays awake after your task fails.
