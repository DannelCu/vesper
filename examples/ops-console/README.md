# Ops Console

A monitoring panel for the machine it runs on. Log in with a role, watch live CPU and
memory charts, browse a real process table, and get alerted when a threshold is
crossed — with a notification, a taskbar badge, and a deep link that jumps straight to
the alert.

Of the Vesper examples, this is the one built around the
**module system**: `@Module`, `@Controller`, `@Injectable`, dependency injection,
guards and middleware — the architecture the other examples never needed and that
the project's README leads with. It is also the only example with a Node/Vite
toolchain (React), so it is where `sync-sdk` and `sync-types` actually get exercised.

---

## Running it

Unlike media-vault and launcher, **this one needs Node.js** — it is a `template =
"react"` project.

```bash
pip install -e ../..           # Vesper itself, from this repo
cd examples/ops-console
npm install
vesper dev
```

`vesper dev` starts Vite and the Python backend together, with hot reload on the
frontend and a Python restart on backend changes — see [Flow of a change](#flow-of-a-change).

Optional, and the app opens, lets you log in, and lets you navigate with **none** of
this installed:

```bash
# Session token in the OS keychain instead of a JS variable
pip install -e ../../plugins/vesper-keychain

# Real CPU/memory instead of a synthetic wave
pip install -e ../../plugins/vesper-sysinfo

# Metrics history that survives a restart
pip install -e ../../plugins/vesper-db

# Rich notifications with a "View" action button
pip install -e ../../plugins/vesper-notify

# Dark/light mode that follows the OS
pip install -e ../../plugins/vesper-theme

# Crash reporting — installed here but inert without a DSN, see below
pip install -e ../../plugins/vesper-crash

# The process table needs psutil — an ordinary Python dependency of this
# example, not a Vesper plugin (the same relationship media-vault has with
# ffmpeg). Without it the table says so and stays empty; nothing else breaks.
pip install psutil
```

After installing any plugin, run `vesper sync-sdk` to copy its JavaScript into
`public/`. The `[plugins]` section of [`vesper.toml`](vesper.toml) is what that reads.

---

## Credentials

Burned into [`modules/auth/auth_service.py`](modules/auth/auth_service.py) for this
demo — no signup flow, no database of users:

- **`admin` / `admin`** — full access. Can terminate processes and change alert
  thresholds.
- **`viewer` / `viewer`** — read-only. **Try terminating a process with this
  account** (right-click a row → Terminate process). The guard denies it, and the
  banner that appears is the policy-denial message, not a generic error — see
  [Guards in action](#guards-in-action).

A real app would check credentials against a user store or an identity provider and
issue a short-lived, signed token instead of a `secrets.token_hex()` string in a
process-lifetime dict. What is real here: the guard mechanics, the role check, and the
three-way error split the frontend renders differently — see
[`modules/auth/guards.py`](modules/auth/guards.py).

---

## Guided tour

1. **Log in as `admin`.** The dashboard loads with two live charts, CPU and memory.
   Without `vesper-sysinfo` a yellow banner says the data is synthetic — it is a
   smooth fake wave, not random noise, so it still looks like something worth
   watching.

2. **Open Processes.** A real table: sortable columns (click a header), a text filter,
   pagination. Without `psutil` installed the table says so and stays empty — nothing
   else in the app is affected.

3. **Right-click a row.** A context menu appears — Vesper has no native one to give
   you (see [The context menu](#the-context-menu-and-why-it-has-to-exist)). Try **View
   detail in new window**: a second, real OS window opens with that process's detail.

4. **Open Settings** and lower the CPU threshold to something your machine is already
   above (try `1`) and the duration to `0`. Within a couple of seconds an alert fires:
   a notification appears (with a **View** button if `vesper-notify` is installed),
   and the Alerts nav item grows a badge. If your desktop supports it, the taskbar/dock
   icon gets a badge too (`vesper.capabilities().badge` — uneven across desktops, see
   [docs/badge.md](../../docs/badge.md)).

5. **Open the Alerts page.** Right-click an alert for **Resolve** / **Copy detail**.
   Resolving clears the badge count.

6. **Try the deep link** while the app is running (see
   [Deep link](#deep-link-vesper-opsalertid) for the exact command per OS) — it routes
   to the **already-open** window and jumps to that alert, highlighted.

7. **Log out and back in as `viewer`.** Right-click a process row and choose
   **Terminate process**. The guard denies it — the banner reads *"This action needs
   the admin role. You are signed in as viewer."*, not a generic failure. Compare that
   with what happens if you stop the process yourself from a terminal before the
   click lands: a different message, from the command itself, not the guard.

8. **Open the middleware panel** (the button next to your role in the header). It
   lists the last commands that ran — including the ones from this tour — each with
   its duration and result. See
   [The middleware panel, and the gap behind it](#the-middleware-panel-and-the-gap-behind-it)
   for why it is built the way it is.

---

## Architecture

Four domain modules, each with its own controller and injected services — the module
tree lives in [`modules/app_module.py`](modules/app_module.py):

```
AppModule
├── AuthModule       SessionService              → AuthController
├── MetricsModule    MetricsService               → MetricsController
├── ProcessesModule  ProcessesService              → ProcessesController
└── AlertsModule     SettingsService, AlertsService → AlertsController
```

**The DI edge that matters:** `AlertsService.__init__(self, metrics: MetricsService,
settings: SettingsService)` — alerts evaluates thresholds against the *same* running
`MetricsService` instance the dashboard reads from, not a second poller of its own.
That only works because `MetricsService` is registered as a **global** DI provider
(`app.register_global_provider`, [app.py](app.py)) rather than left to each module's
own container — see [Two framework gaps this app found](#two-framework-gaps-this-app-found--since-fixed-upstream)
for why that matters more than it looks.

`SessionService` is the odd one out: it is also read directly, outside DI, by
[`modules/auth/guards.py`](modules/auth/guards.py) — guards only ever receive
`(command, args)`, never an injected service (see
[docs/guards.md](../../docs/guards.md)), so the shared session state has to be reached
some other way.

**Where the guards run:**

| Guard | Applied to | Effect |
|---|---|---|
| `require_auth` | Every command in `MetricsController`, `ProcessesController`, `AlertsController` (controller-level `guards=[]`) | Rejects any call without a valid session token |
| `require_admin` | `ProcessesController.terminate`, `AlertsController.set_thresholds` (method-level `@guard`) | Rejects viewers specifically — the guided tour's step 7 |

Controller-level guards run before method-level ones, so `terminate` and
`set_thresholds` check auth *and* role, in that order — see
[docs/guards.md](../../docs/guards.md#controller-level-guards).

---

## Guards in action

The plan for this app came with a specific thing to notice: three IPC failure phases,
not one. `docs/guards.md` describes them; this app is where you can actually trigger
all three back to back.

```js
try {
  await vesper.invoke("processes.terminate", { token, pid })
} catch (err) {
  // err.name is one of:
  //   "ForbiddenError" — the guard ran and said no. A policy decision,
  //                       not a bug. This is what a viewer gets.
  //   "GuardError"      — the guard itself threw. A bug in the check,
  //                       not a decision about the request.
  //   anything else      — the command ran and failed on its own terms
  //                       (e.g. the PID was already gone).
}
```

`src/lib/vesperClient.js`'s `classifyError()` is the one place this app turns that
into three different banners instead of one generic "Something went wrong."

---

## The context menu, and why it has to exist

PyWebView has no context-menu API — right-click either shows the engine's own menu or,
under `security.lockdown()`, nothing at all. [KNOWN-ISSUES KI2](../../KNOWN-ISSUES.md#ki2)
covers why, and [docs/recipes/context-menus.md](../../docs/recipes/context-menus.md)
is the substitute this app follows: an HTML/CSS menu
([`src/components/ContextMenu.jsx`](src/components/ContextMenu.jsx)) positioned inside
the viewport, closing on an outside click or <kbd>Escape</kbd>, with arrow-key
navigation.

`src/main.jsx` calls `vesper.security.lockdown({ force: true })` in production. That
call is *why* the custom menu has to exist at all — with the browser's own menu turned
off, this is the only one left. It is deliberately not called unconditionally, though
— see the note in that file and [Two framework gaps this app found](#two-framework-gaps-this-app-found--since-fixed-upstream)
for why `force: true` is necessary here specifically.

---

## Deep link: `vesper-ops://alert/<id>`

Cold start or already running, the link routes to the alert. With the app already
open, `single_instance=True` hands the second launch's argv to the running window
instead of opening a rival one — deep link and single-instance demonstrated together,
which is the point.

Test it from a terminal:

```bash
# Linux/macOS, app running from source
python app.py "vesper-ops://alert/1"

# Windows (PowerShell)
python app.py "vesper-ops://alert/1"
```

Registering the protocol with the OS so a *browser* link launches the app (rather than
typing the URL as an argv, which always works and is what the tour above uses) is:

```bash
vesper register-protocol vesper-ops
```

macOS requires the `CFBundleURLTypes` entry at build time — `register-protocol` prints
the exact `Info.plist` snippet; see [docs/deeplink.md](../../docs/deeplink.md).

---

## The middleware panel, and the gap behind it

The plan asked for IPC logging and timing middleware with a panel showing what just
ran. Writing it exposed a real gap between what `app.middleware()` is documented to do
and what it actually does — worth reading before you copy this pattern into your own
app.

[`docs/recipes/logging-middleware.md`](../../docs/recipes/logging-middleware.md) shows:

```python
@app.middleware
async def timing_middleware(command, args, next):
    result = await next(command, args)
    ...
```

`vesper/core/ipc.py`'s `IPC.handle()` calls every middleware as `mw(command_name,
args)` — **two** arguments, never three, and nothing is ever passed as `next`.
`App.middleware()`'s own docstring agrees: *"Signature: fn(command: str, args: Any) ->
None."* A middleware written the way the recipe shows raises `TypeError:
timing_middleware() missing 1 required positional argument: 'next'` on the very first
IPC call — there is no way,
with the hook as implemented, to wrap a command and see its result or duration.

This app's middleware
([`log_invocation` in app.py](app.py)) uses the signature that actually works, for what
that shape can do: logging that a command started. The panel's duration and
success/failure columns come from a different mechanism —
[`modules/common/telemetry.py`](modules/common/telemetry.py) wraps every registered
command once, after the module tree is built, entirely outside the `app.middleware()`
hook. Read that file's docstring for the full reasoning. Reproducing the recipe's
literal example is a two-line way to see the `TypeError` yourself.

---

## Two framework gaps this app found — since fixed upstream

Building this app surfaced two real framework issues. Both were fixed in the
framework itself (not worked around here) once found — noted below for the record,
since the app's own code no longer needs to route around either.

**DI container silently building a phantom instance.** `Container.resolve()`
(`vesper/core/module.py`) used to be unable to tell "no provider is registered for
this type" apart from "here is a freshly-constructed, empty instance." For a type
with a trivial constructor — `vesper_db.DbSession` is exactly this shape, `class
DbSession: pass` — resolving it when the plugin that is supposed to provide it was
never installed used to silently construct a blank `DbSession()` instead of raising,
which then failed confusingly on the first real `.query()` call rather than failing
clearly at startup. `Container.resolve()` now raises `MissingProviderError` for any
type that is neither `@Injectable()`/`@Controller()` nor registered as a provider —
see [docs/module-system.md](../../docs/module-system.md#dependency-injection). This
app's `MetricsService` database persistence was already wired directly in
`app.py`/`modules/metrics/models.py` with its own SQLAlchemy engine rather than
through `db: DbSession` DI, so it was never affected either way.

**`security.lockdown()`'s dev-detection couldn't tell `vesper dev` apart from this
app's own production mode.** Its runtime heuristic treated any `http(s)://
localhost`/`127.0.0.1` origin as "dev." `App(serve_frontend=True)` — needed for this
app's SPA routing, see [below](#why-the-localhost-server) — serves the *production*
build from `http://127.0.0.1:<port>` too, indistinguishable by hostname alone. Worse,
the framework's own `window.VESPER_DEV_URL` check (meant to be the reliable signal)
turned out never to fire in practice — nothing set that browser global; it only ever
existed as a Python-side environment variable. Fixed upstream: `vesper dev`'s vanilla
server now actually injects `window.VESPER_DEV_URL`, and `vesper init`'s React/Vue/
Svelte templates now scaffold their lockdown call gated on `import.meta.env.DEV` —
Vite's own build-time flag, the reliable signal for a bundled app either way. See
[docs/security-lockdown.md](../../docs/security-lockdown.md). This app's
`src/main.jsx`/`detail-main.jsx` use that same `import.meta.env.DEV` check.

---

## Why the localhost server

Same feature as media-vault, different reason. There, `file://` breaks the `<video>`
element's byte-range seeking. Here, `file://` breaks **SPA routing**:
`history.pushState` paths like `/processes` 404 on a hard reload, because there is no
server to fall back to `index.html` — see
[docs/project-config.md](../../docs/project-config.md#serving-the-frontend-over-localhost-in-production).
`App(serve_frontend=True)` in [app.py](app.py) is what makes `/dashboard`,
`/processes`, `/alerts` and `/settings` survive a reload, and it is also what makes
the `security.lockdown()` interaction above worth knowing.

---

## Session persistence: what keychain actually buys you here

With `vesper-keychain` installed, the login token is stored with
`vesper.keychain.set()` instead of a plain JS variable, and restored with
`vesper.keychain.get()` on the next launch — see
[`src/lib/session.js`](src/lib/session.js). Without it, the token lives only in
memory, and the login screen says so.

**What this does not do:** make you arrive already logged in after restarting the
Python process. `SessionService` ([`modules/auth/auth_service.py`](modules/auth/auth_service.py))
keeps sessions in a plain in-memory dict, which resets every launch — so a token
recovered from the keychain after a restart calls `auth.me(token)` and gets `null`
back, same as if keychain were not installed. Combining the two — a token that
survives in the keychain *and* a backend that still recognizes it after a restart —
would mean persisting `SessionService`'s own state (to disk, or through
`vesper-store`), which is a reasonable next step this example does not take, so as not
to conflate "where is the token cached" with "does the server remember you." Both
matter for a real login system; only the first is what `vesper-keychain` is for.

---

## Without the optional pieces

| Missing | What you get instead |
|---|---|
| `vesper-keychain` | Token lives in a JS variable — gone on reload/restart. Login screen says so. |
| `vesper-sysinfo` | Dashboard charts show a synthetic wave, labelled as such. Alerts still work against it. |
| `vesper-db` | Metrics history covers this session only — empty charts on a fresh launch instead of picking up where you left off. |
| `vesper-notify` | Alerts still notify, through the core's dependency-free `vesper.notify()` — no "View" action button, no click callback. |
| `vesper-theme` | Fixed light theme. No manual toggle either — see [docs/recipes/theming.md](../../docs/recipes/theming.md). |
| `vesper-crash` | Nothing changes — see below, it is opt-in twice regardless. |
| `psutil` | Processes page and the process-detail window say it is unavailable; nothing else in the app is affected. |

`system:features` (this app's own command, [app.py](app.py)) reports all seven;
`vesper.capabilities()` reports the framework's own optional backends (badge,
notifications, tray, ...) separately. Settings renders both.

### vesper-crash — opt-in twice, on purpose

`CrashPlugin` is always in the plugins list, but constructed with
`dsn=os.environ.get("SENTRY_DSN")` — unset in this example, so it stays a silent
no-op even when installed. Exporting a real DSN before launch would start sending: the
exception type, message and traceback of any IPC command, guard, or middleware
failure; the failing command's name as a tag; and the release/environment strings —
never PII, never breadcrumbs, never args (see
[plugins/vesper-crash/README.md](../../plugins/vesper-crash/README.md)). Nothing about
this app needed to change to add it; that is the point of the plugin boundary.

---

## Module system, DI, and middleware — the numbers

- **4 modules**, each with one controller and its own service(s):
  auth (`SessionService`), metrics (`MetricsService`), processes
  (`ProcessesService`), alerts (`SettingsService`, `AlertsService`).
- **1 real cross-module DI edge**: `AlertsService` injects `MetricsService` — see
  [Architecture](#architecture) above.
- **2 guards**, applied in **5 places**: `require_auth` at controller level on three
  controllers; `require_admin` at method level on `processes.terminate` and
  `alerts.set_thresholds`.
- **1 middleware function** (`log_invocation`) plus the registry-wrapping workaround
  in `modules/common/telemetry.py` for the half the real hook cannot do — see
  [above](#the-middleware-panel-and-the-gap-behind-it).

---

## Vesper features on show

| In the app | Feature | Docs |
|---|---|---|
| Login, role check, viewer denied on terminate | Guards, three-phase IPC errors | [guards.md](../../docs/guards.md), [recipes/auth.md](../../docs/recipes/auth.md) |
| Four domain modules, injected services | Module system & DI | [module-system.md](../../docs/module-system.md) |
| The middleware panel | IPC middleware (and its real limits) | [middleware.md](../../docs/middleware.md), [recipes/logging-middleware.md](../../docs/recipes/logging-middleware.md) |
| Live CPU/memory charts | Real-time push over events | [recipes/real-time.md](../../docs/recipes/real-time.md) |
| Process detail in its own window | Multi-window, shared IPC state | [multiwindow.md](../../docs/multiwindow.md), [recipes/state-between-windows.md](../../docs/recipes/state-between-windows.md) |
| Alert thresholds in Settings | User preferences (in-memory variant) | [recipes/user-preferences.md](../../docs/recipes/user-preferences.md) |
| Right-click menus everywhere | Context menus (PyWebView has none) | [recipes/context-menus.md](../../docs/recipes/context-menus.md), [KI2](../../KNOWN-ISSUES.md#ki2) |
| Fixed light / follows-OS dark mode | Theming | [recipes/theming.md](../../docs/recipes/theming.md) |
| `/dashboard` etc. survive a reload | Production localhost server | [project-config.md](../../docs/project-config.md) |
| Session token storage | vesper-keychain | [plugins.md](../../docs/plugins.md#vesper-keychain) |
| Notification with a "View" button | vesper-notify | [plugins.md](../../docs/plugins.md#vesper-notify) |
| Taskbar/dock alert count | Badge | [badge.md](../../docs/badge.md) |
| Deep link + single-instance together | Deep linking | [deeplink.md](../../docs/deeplink.md), [single-instance.md](../../docs/single-instance.md) |
| Native "Ops Console" / "Help" menu | Menu bar | [menu.md](../../docs/menu.md) |
| Window size remembered between runs | Window state | [window-state.md](../../docs/window-state.md) |
| Crash reporting, installed but inert | vesper-crash | [plugins/vesper-crash/README.md](../../plugins/vesper-crash/README.md) |

---

## Flow of a change

```bash
npm install
vesper dev              # Vite + the Python backend, together, hot-reloading
```

After changing anything in `modules/` that adds or renames a command:

```bash
vesper sync-types        # regenerates src/types/vesper.d.ts from the live registry
```

After installing or removing a plugin:

```bash
vesper sync-sdk          # re-copies vesper.js + plugin JS into public/
```

`vesper build` (PyInstaller by default, per `vesper.toml`) produces the packaged app;
`vesper package --installer` adds a platform installer. Both run `vite build` first,
emitting `dist/index.html` **and** `dist/process-detail.html` — the two-entry-point
build `vite.config.js` declares for the detached window.

---

## Known limits

- **Alert thresholds reset on restart.** No plugin in this app's set persists them —
  `vesper-store` would, following
  [recipes/user-preferences.md](../../docs/recipes/user-preferences.md), but this app
  keeps to the five plugins the plan specifies. A clearly-scoped limitation, not a bug.
- **Session state does not survive a restart even with vesper-keychain** — see
  [above](#session-persistence-what-keychain-actually-buys-you-here).
- **The context menu is not a native one** — [KI2](../../KNOWN-ISSUES.md#ki2); nothing
  in this app tries to make it look more native than it is.
- **`app.middleware()` cannot wrap a command** — see
  [above](#the-middleware-panel-and-the-gap-behind-it); this is the framework's real
  behavior, not something this app works around badly.
- Everything in [KNOWN-ISSUES.md](../../KNOWN-ISSUES.md) applies generally; KI2 is the
  one this app's UI is built around.

---

## Files

| File | What is in it |
|---|---|
| [`app.py`](app.py) | The composition root: plugin detection, DI wiring, middleware, deep link, multi-window, native menu. Read this top to bottom first. |
| [`modules/app_module.py`](modules/app_module.py) | The root module — imports the four domain modules. |
| [`modules/auth/`](modules/auth/) | `SessionService`, the two guards, `AuthController`. |
| [`modules/metrics/`](modules/metrics/) | `MetricsService` (sysinfo or synthetic, optional DB-backed history), `MetricsController`, the optional SQLAlchemy model. |
| [`modules/processes/`](modules/processes/) | `ProcessesService` (psutil), `ProcessesController` — where `require_admin` gates `terminate`. |
| [`modules/alerts/`](modules/alerts/) | `SettingsService`, `AlertsService` (the cross-module DI consumer), `AlertsController`. |
| [`modules/common/telemetry.py`](modules/common/telemetry.py) | The middleware panel's real data source, and the write-up of why `app.middleware()` alone cannot provide it. |
| [`src/App.jsx`](src/App.jsx) | Boot sequence: features, theme, deep link, session restore, then the router. |
| [`src/lib/`](src/lib/) | The hand-rolled router, the token-aware IPC client with error-phase classification, session storage, feature loading, theming. |
| [`src/pages/`](src/pages/) | Dashboard, Processes, Alerts, Settings — one file each. |
| [`src/components/ContextMenu.jsx`](src/components/ContextMenu.jsx) | The recipe, implemented once and reused on both the process table and the alert list. |
| [`src/components/MiddlewarePanel.jsx`](src/components/MiddlewarePanel.jsx) | Polls `system:middleware_log` and renders it. |
| [`src/ProcessDetail.jsx`](src/ProcessDetail.jsx) + [`src/detail-main.jsx`](src/detail-main.jsx) | The detached window's page and entry point. |
| [`vite.config.js`](vite.config.js) | The two-HTML-entry-point build (`index.html` + `process-detail.html`) multi-window needs. |
| [`vesper.toml`](vesper.toml) | Project metadata and the `[plugins]` list `vesper sync-sdk` reads. |

Read `app.py` first, then `modules/app_module.py`, then follow the imports down into
one module at a time — it is ordered the way the app actually starts.
