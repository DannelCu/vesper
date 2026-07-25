"""
Ops Console — a local-machine monitoring panel: login with roles, a
dashboard with live CPU/memory charts, a real process table, and
threshold-based alerts with notifications and a taskbar badge.

This is the one example that exercises Vesper's module system for real:
four domain modules (auth, metrics, processes, alerts), each with its own
controller and injected services — see modules/app_module.py and the
README's "Architecture" section for the full DI graph. It is also the only
example with a Node/Vite toolchain (template = "react" in vesper.toml).

Every optional piece degrades honestly with zero plugins installed:
  - no vesper-keychain  -> the session token lives in a JS variable instead
    of the OS keychain; the UI says so.
  - no vesper-sysinfo   -> the dashboard charts show a synthetic wave,
    clearly labelled, instead of real CPU/memory.
  - no vesper-db        -> metrics history covers this session only.
  - no vesper-notify    -> alerts still notify, through the core's
    dependency-free vesper.notify(), just without a "View" action button.
  - no vesper-theme     -> the UI stays in light mode.
  - no vesper-crash     -> nothing changes; it is opt-in twice (see below).

Run with `npm install && vesper dev` from this directory.
"""
from __future__ import annotations

import os

from vesper import App, MenuItem, guard
from vesper.core import badge, paths, shell
from vesper.core.logging import get_logger

from modules.app_module import AppModule
from modules.auth.auth_service import SessionService, session_service
from modules.auth.guards import require_auth
from modules.metrics.metrics_service import MetricsService
from modules.alerts.settings_service import SettingsService
from modules.alerts.alerts_service import AlertsService
from modules.processes.processes_service import ProcessesService
from modules.common import telemetry

logger = get_logger("ops-console")


# ── Optional plugins ─────────────────────────────────────────────────────────
#
# Each is imported defensively so the app runs with none of them installed.
# A missing plugin removes exactly the capability it provides — never the
# app's ability to open, log in, or navigate. See docs/optional-features.md,
# which this app exists to demonstrate rather than just describe.

plugins: list = []

HAS_KEYCHAIN = False
try:
    from vesper_keychain import KeychainPlugin

    plugins.append(KeychainPlugin(service="vesper-ops-console"))
    HAS_KEYCHAIN = True
except ImportError:
    pass

HAS_SYSINFO = False
sysinfo_plugin = None
try:
    from vesper_sysinfo import SysinfoPlugin

    sysinfo_plugin = SysinfoPlugin()
    plugins.append(sysinfo_plugin)
    HAS_SYSINFO = True
except ImportError:
    pass

HAS_DB = False
history_repo = None
try:
    from sqlalchemy import create_engine
    from vesper_db import DatabasePlugin

    # Only imported here: modules/metrics/models.py imports `Base` from
    # vesper_db, so touching it without the plugin installed would break
    # the app at import time rather than degrading.
    from modules.metrics.models import MetricsHistoryRepo

    _db_path = paths.ensure_dir(paths.config_dir("vesper-ops-console")) / "ops-console.db"
    _db_url = f"sqlite:///{_db_path}"

    db_plugin = DatabasePlugin(url=_db_url)
    plugins.append(db_plugin)

    # A second connection to the same file, independent of DatabasePlugin's
    # own scoped_session — see models.py for why the background sampler
    # thread does not reuse it.
    history_repo = MetricsHistoryRepo(create_engine(_db_url))
    HAS_DB = True
except ImportError:
    pass

HAS_NOTIFY = False
notify_plugin = None
try:
    from vesper_notify import NotifyPlugin

    notify_plugin = NotifyPlugin(app_name="Ops Console")
    plugins.append(notify_plugin)
    HAS_NOTIFY = True
except ImportError:
    pass

HAS_THEME = False
try:
    from vesper_theme import ThemePlugin

    plugins.append(ThemePlugin(watch=True))
    HAS_THEME = True
except ImportError:
    pass

HAS_CRASH = False
try:
    from vesper_crash import CrashPlugin

    # Opt-in twice, deliberately: installed but inert without a DSN, and no
    # DSN is set anywhere in this example. See the README's "vesper-crash"
    # section for exactly what it would send if SENTRY_DSN were exported
    # before launch.
    plugins.append(
        CrashPlugin(dsn=os.environ.get("SENTRY_DSN"), release="ops-console@0.1.0")
    )
    HAS_CRASH = True
except ImportError:
    pass


# ── The App ──────────────────────────────────────────────────────────────────

app = App(
    title="Ops Console",
    width=1180,
    height=780,
    min_width=920,
    min_height=600,
    frontend="dist/index.html",
    debug=True,
    plugins=plugins,
    # SPA routing (history.pushState across /dashboard, /processes, /alerts,
    # /settings) 404s on reload under file://, for the same reason
    # media-vault needs this flag for its video seek bar: there is no HTTP
    # request for a bare server-less origin to fall back to index.html with.
    # See the README's "Why the localhost server" section.
    serve_frontend=True,
    remember_window=True,
    # Required for the deep link to route to the already-open window
    # instead of spawning a second one — see docs/single-instance.md.
    single_instance=True,
)


# ── DI composition root ──────────────────────────────────────────────────────
#
# Every cross-module service is built once, here, and handed to the
# container as a global provider (docs/module-system.md's "Plugin DI
# integration", used for app-level services rather than only a plugin's).
# That is what makes AlertsService's `metrics: MetricsService` constructor
# parameter (modules/alerts/alerts_service.py) resolve to the *same* running
# MetricsService instance MetricsController uses — a real DI edge between
# two domain modules, not four independent singletons.
#
# SessionService is the odd one out: it is also read directly (not through
# DI) by modules/auth/guards.py, since guards only ever receive
# (command, args), never an injected service (docs/guards.md).

app.register_global_provider(SessionService, session_service)

metrics_service = MetricsService(
    sysinfo_plugin=sysinfo_plugin,
    emit=app.emit,
    history_repo=history_repo,
)
app.register_global_provider(MetricsService, metrics_service)

settings_service = SettingsService()
app.register_global_provider(SettingsService, settings_service)

alerts_service = AlertsService(metrics=metrics_service, settings=settings_service)
app.register_global_provider(AlertsService, alerts_service)

processes_service = ProcessesService()
app.register_global_provider(ProcessesService, processes_service)

app.register_module(AppModule)

# Sampling starts the moment the app opens, independent of whether the
# dashboard is on screen — an ops console that only measures while someone
# is watching would miss the alerts it exists to raise.
metrics_service.subscribe(interval=2.0)


# ── Alerts -> notification + badge ───────────────────────────────────────────

# notify_id -> alert_id, so a click on the rich notification's "View" button
# can be traced back to which alert it was about. vesper-notify's click/
# action events carry only its own generated id and the button label — no
# room for app data — so this small side table is this app's own doing, not
# something the plugin provides. See the README's friction report.
_notify_alert_map: dict[str, int] = {}


def _send_alert_notification(alert: dict) -> None:
    metric_label = "CPU" if alert["metric"] == "cpu_percent" else "Memory"
    title = f"{metric_label} alert"
    body = f"{metric_label} at {alert['value']:.0f}% (threshold {alert['threshold']:.0f}%)"

    if HAS_NOTIFY and notify_plugin is not None:
        notify_id = notify_plugin.send(title, body, buttons=["View"])
        _notify_alert_map[notify_id] = alert["id"]
    else:
        # The core's notify() has no click callback (docs/notifications.md)
        # — still a real, dependency-free notification either way.
        app.notify(title, body)


alerts_service.on_trigger(_send_alert_notification)
alerts_service.on_change(lambda unresolved: badge.set_badge(unresolved))


@app.command("system:alert_for_notification")
def alert_for_notification(notify_id: str) -> int | None:
    """Resolve a vesper-notify click back to the alert it was about."""
    return _notify_alert_map.get(notify_id)


# ── Deep link: vesper-ops://alert/<id> ───────────────────────────────────────
#
# App already emits a "deeplink" JS event on its own (see App._fire_deeplink
# in vesper/core/app.py) whenever a link arrives — cold start or forwarded
# by single_instance from a second launch. This hook only keeps the *last*
# one queryable, covering the race where the link arrives before the
# frontend's own listener has attached — see system:pending_deeplink below.
_pending_deeplink: dict = {"url": None}


@app.on("deeplink")
def _on_deeplink(url: str) -> None:
    _pending_deeplink["url"] = url


@app.command("system:pending_deeplink")
def pending_deeplink() -> str | None:
    """Consumed once by the frontend on startup, in case it missed the event."""
    url = _pending_deeplink["url"]
    _pending_deeplink["url"] = None
    return url


# ── Multi-window: process detail ─────────────────────────────────────────────
#
# Follows docs/recipes/state-between-windows.md's "Python as the source of
# truth" pattern, the same one media-vault uses for its detached player:
# the selection is stashed in Python and handed to the window over the
# event bus, with a pull command covering the race where the window
# finishes loading just after the event was emitted.

detail_window = app.register_window(
    title="Process Detail",
    width=440,
    height=560,
    frontend="dist/process-detail.html",
)

_now_viewing: dict = {"detail": None}


def _safe(fn, default=""):
    try:
        return fn()
    except Exception:
        return default


def _process_detail(pid: int) -> dict:
    import psutil

    proc = psutil.Process(pid)
    with proc.oneshot():
        return {
            "pid": proc.pid,
            "name": _safe(proc.name),
            "exe": _safe(proc.exe),
            "cmdline": _safe(proc.cmdline, []),
            "status": _safe(proc.status),
            "username": _safe(proc.username),
            "cpu_percent": round(proc.cpu_percent(interval=0.1), 1),
            "memory_percent": round(proc.memory_percent(), 1),
            "num_threads": _safe(proc.num_threads, 0),
            "create_time": _safe(proc.create_time, 0),
        }


@app.command("processes:open_detail")
@guard(require_auth)
def open_detail(token: str, pid: int) -> dict:
    if not processes_service.available():
        raise RuntimeError("psutil is not installed; process detail is unavailable.")

    detail = _process_detail(pid)
    _now_viewing["detail"] = detail
    detail_window.show()
    detail_window.emit("process:detail", detail)
    return detail


@app.command("processes:now_viewing")
def now_viewing() -> dict | None:
    return _now_viewing["detail"]


# ── Middleware: logging + timing panel ───────────────────────────────────────
#
# app.middleware is genuine IPC middleware — it runs before every command,
# for every module alike. Its signature is (command, args), no `next`,
# which is all App.middleware() actually supports (see its docstring in
# vesper/core/app.py) — used here for what that shape can do: observe and
# log the call as it starts.
#
# It cannot also time the call or see its result: there is no `next` to
# await, so nothing runs "after". docs/recipes/logging-middleware.md
# documents a 3-argument `(command, args, next)` signature and shows
# `result = await next(command, args)` — that recipe does not match
# IPC.handle()'s real contract and raises TypeError the moment a middleware
# written that way is registered. See modules/common/telemetry.py for the
# full writeup and the workaround the panel below actually uses.


@app.middleware
def log_invocation(command: str, args: dict) -> None:
    if not command.startswith("vesper:"):
        logger.debug("IPC -> %s %s", command, telemetry.redact(args))


# Runs last, after every module's commands are registered, so it wraps all
# of them — this is what actually feeds the panel's duration/result columns.
telemetry.install(app.registry)


@app.command("system:middleware_log")
def middleware_log(token: str, limit: int = 50) -> list:
    return telemetry.recent(limit)


# ── Feature aggregation for the frontend ─────────────────────────────────────


@app.command("system:features")
def features() -> dict:
    """
    This app's own optional pieces. vesper.capabilities() covers the
    framework's own optional backends (badge, notifications, tray, ...);
    the frontend merges both, same pattern as launcher's and media-vault's
    own `*:features` commands.
    """
    return {
        "keychain": HAS_KEYCHAIN,
        "sysinfo": HAS_SYSINFO,
        "db": HAS_DB,
        "notify": HAS_NOTIFY,
        "theme": HAS_THEME,
        "crash": HAS_CRASH,
        "psutil": processes_service.available(),
    }


# ── Native menu ───────────────────────────────────────────────────────────────


def _open_docs() -> None:
    shell.open_url("https://github.com/DannelCu/vesper")


def _navigate(path: str):
    return lambda: app.emit("menu:navigate", {"path": path})


app.menu(
    [
        MenuItem(
            "Ops Console",
            submenu=[
                MenuItem("Dashboard", action=_navigate("/dashboard")),
                MenuItem("Processes", action=_navigate("/processes")),
                MenuItem("Alerts", action=_navigate("/alerts")),
                MenuItem("Settings", action=_navigate("/settings")),
                None,
                MenuItem("Quit", action=lambda: app.quit()),
            ],
        ),
        MenuItem(
            "Help",
            submenu=[
                MenuItem("Vesper docs", action=_open_docs),
            ],
        ),
    ]
)


if __name__ == "__main__":
    app.run()
