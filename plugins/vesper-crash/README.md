# vesper-crash

Crash reporting for Vesper apps via [Sentry](https://sentry.io) (`sentry-sdk`). Captures Python exceptions and frontend JS errors — without ever altering what the app or the frontend sees.

---

## Install

```bash
pip install vesper-crash
```

---

## Setup

```python
import os
from vesper import App
from vesper_crash import CrashPlugin

app = App(
    frontend="dist/index.html",
    plugins=[CrashPlugin(
        dsn=os.environ.get("SENTRY_DSN"),   # no DSN → silent no-op
        release="my-app@1.2.0",
        environment="production",
    )],
)
```

Reporting is **opt-in twice**: installing the plugin does nothing until you also configure a DSN. Without one, every hook is skipped and the bridge command becomes a no-op — frontend code needs no branch.

---

## What gets captured

| Source | How | Flow impact |
|---|---|---|
| Exceptions in IPC commands, guards, middleware | `app.ipc.on_error` observation hook | None — the frontend receives the exact same IPC error response |
| Unhandled Python exceptions | `sys.excepthook`, chained to the previous hook | None — the prior hook (default traceback) still runs |
| Frontend JS errors | SDK installs `window.onerror` + `unhandledrejection` → `vesper:crash:report` | None — errors propagate in the page as usual |

---

## What gets sent — exactly

Privacy defaults are deliberate and non-configurable through this plugin:

- `send_default_pii=False` — no user context, no request data.
- `default_integrations=False` — none of Sentry's automatic integrations (logging capture, stdlib instrumentation) run. Only what the table above lists is captured.
- `max_breadcrumbs=0` — no breadcrumb trail.

An event therefore contains: the exception type, message, and traceback (which includes source file paths and function names — that is what a traceback is), the failing IPC command name as a tag, the `release`/`environment` you configured, and the Sentry SDK's basic runtime context (OS name/version, Python version). Nothing else. If you enable more via `sentry_sdk` directly, that is your app's decision to document.

Disclose crash reporting to your users — it is network telemetry, however anonymous.

---

## JavaScript

```toml
[plugins]
crash = "vesper-crash"
```

```bash
vesper sync-sdk
```

```html
<script src="vesper.js"></script>
<script src="vesper-crash.js"></script>
```

Loading the SDK installs the global error listeners. Manual reporting:

```js
try {
    riskyThing()
} catch (err) {
    await vesper.crash.report(err)   // resolves false when no DSN is configured
    showFriendlyError()
}
```

A reporting failure never cascades: the bridge swallows its own errors, and a re-entrant error during reporting is dropped.
