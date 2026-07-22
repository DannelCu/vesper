from __future__ import annotations

import sys
from pathlib import Path

from vesper.core.plugin import VesperPlugin


class CrashPlugin(VesperPlugin):
    """
    Error reporting for Vesper apps via Sentry.

    Captures three things, and nothing else:

    - Exceptions raised inside IPC commands, guards and middleware (observed
      through ``app.ipc.on_error`` — the frontend still receives the normal
      IPC error response; reporting never alters the error flow).
    - Unhandled Python exceptions (``sys.excepthook``, chained to the previous
      hook so default behaviour is preserved).
    - Frontend JS errors, bridged by the SDK's ``window.onerror`` /
      ``unhandledrejection`` listeners through the ``vesper:crash:report``
      command.

    **Privacy by default.** Reporting is opt-in twice over: installing the
    plugin *and* configuring a DSN — without a DSN the plugin is a silent
    no-op. Sentry's automatic integrations are disabled
    (``default_integrations=False``), ``send_default_pii=False``, and no
    breadcrumbs are collected, so an event contains: exception type, message
    and traceback (file paths and function names included — that is what a
    traceback is), the release/environment you configure, and the SDK's basic
    runtime context (OS, Python version). Tell your users.

    Usage::

        from vesper_crash import CrashPlugin

        app = App(plugins=[CrashPlugin(
            dsn=os.environ.get("SENTRY_DSN"),   # None → no-op
            release="my-app@1.2.0",
            environment="production",
        )])
    """

    def __init__(
        self,
        dsn: str | None = None,
        *,
        release: str | None = None,
        environment: str | None = None,
    ) -> None:
        self._dsn = dsn
        self._release = release
        self._environment = environment
        self._enabled = bool(dsn)
        self._previous_excepthook = None

    def register(self, app) -> None:
        if not self._enabled:
            # Same commands, no capture: the frontend code does not need to
            # know whether reporting is configured.
            def _report_noop(message: str = "", stack: str = "", kind: str = "") -> bool:
                return False

            app.registry.register(_report_noop, name="vesper:crash:report")
            return

        import sentry_sdk

        sentry_sdk.init(
            dsn=self._dsn,
            release=self._release,
            environment=self._environment,
            send_default_pii=False,
            default_integrations=False,
            max_breadcrumbs=0,
        )

        def _on_ipc_error(command_name: str, exc: Exception) -> None:
            try:
                with sentry_sdk.new_scope() as scope:
                    scope.set_tag("vesper.command", command_name)
                    sentry_sdk.capture_exception(exc)
            except Exception:
                # Reporting must never make an error worse.
                pass

        app.ipc.on_error(_on_ipc_error)

        previous = sys.excepthook
        self._previous_excepthook = previous

        def _excepthook(exc_type, exc_value, exc_tb) -> None:
            try:
                sentry_sdk.capture_exception(exc_value)
            except Exception:
                pass
            previous(exc_type, exc_value, exc_tb)

        sys.excepthook = _excepthook

        def _report(message: str = "", stack: str = "", kind: str = "") -> bool:
            try:
                with sentry_sdk.new_scope() as scope:
                    scope.set_tag("vesper.source", "frontend")
                    if kind:
                        scope.set_tag("vesper.js_kind", kind)
                    if stack:
                        scope.set_extra("stack", stack)
                    sentry_sdk.capture_message(f"[frontend] {message}", level="error")
                return True
            except Exception:
                return False

        app.registry.register(_report, name="vesper:crash:report")

    @classmethod
    def sdk_path(cls) -> Path | None:
        from importlib.resources import files
        return Path(str(files("vesper_crash").joinpath("sdk/vesper-crash.js")))
