from __future__ import annotations

import asyncio
import inspect
import threading
import traceback
from typing import Any

from vesper.exceptions import CommandNotFoundError, ForbiddenError
from vesper.core.logging import get_logger
from vesper.core.registry import CommandRegistry

logger = get_logger("ipc")


def _validate_args(fn, args: dict) -> str | None:
    """Check args match fn's signature. Returns an error message or None."""
    try:
        sig = inspect.signature(fn)
    except (ValueError, TypeError):
        return None

    params = sig.parameters
    has_var_keyword = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
    )

    if not has_var_keyword:
        valid = {
            n for n, p in params.items()
            if p.kind not in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)
        }
        unexpected = set(args) - valid
        if unexpected:
            return f"Unexpected arguments: {', '.join(sorted(unexpected))}"

    missing = [
        n for n, p in params.items()
        if p.kind not in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)
        and p.default is inspect.Parameter.empty
        and n not in args
    ]
    if missing:
        return f"Missing required arguments: {', '.join(missing)}"

    return None


class IPC:
    """
    Inter-Process Communication manager.

    Responsible for:
        - Receiving frontend messages
        - Validating requests
        - Resolving commands from registry
        - Executing commands (sync and async)
        - Returning structured responses
        - Error handling and reporting
    """

    def __init__(
        self,
        registry: CommandRegistry,
        *,
        middleware: list | None = None,
        debug: bool = False,
    ) -> None:
        """
        Initialize IPC with a command registry.

        Args:
            registry:   Command registry containing all registered commands.
            middleware: Shared middleware list. Passed by reference from App
                        so handlers registered after IPC construction are visible.
            debug:      Whether to include debug information in error responses.
        """
        self.registry = registry
        self.debug = debug
        self._middleware: list = middleware if middleware is not None else []

        self._teardown: list = []
        self._error_hooks: list = []

        # The loop is created on first use, not here. It is only ever touched by
        # async guards, middleware and commands, so an app with none never needs
        # one — and building it eagerly cost a thread and three descriptors per
        # App, which nothing but close() could reclaim. Tests construct Apps
        # without ever calling run(), so they ran the process out of descriptors.
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._loop_lock = threading.Lock()

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        """
        The async event loop, started on first use.

        handle() can be entered from more than one thread, so the check is
        double-checked under a lock: two callers must not each build a loop and
        leave one orphaned.
        """
        if self._loop is not None:
            return self._loop

        with self._loop_lock:
            if self._loop is not None:
                return self._loop

            loop = asyncio.new_event_loop()
            started = threading.Event()

            def _run() -> None:
                asyncio.set_event_loop(loop)
                loop.call_soon(started.set)
                loop.run_forever()

            thread = threading.Thread(target=_run, daemon=True, name="vesper-async")
            thread.start()
            started.wait(timeout=5)

            # Published only once running, so a concurrent reader outside the lock
            # never sees a loop whose thread has not started yet.
            self._loop_thread = thread
            self._loop = loop
            return loop

    def on_error(self, fn) -> None:
        """
        Observe exceptions raised while handling IPC calls.

        *fn* is called with ``(command_name, exception)`` for every exception a
        command, guard, or middleware raises — but not for policy denials
        (``ForbiddenError``), which are outcomes rather than defects. Purely an
        observation point for error-reporting plugins: the error response the
        frontend receives is built exactly as before, and a hook that itself
        raises is logged and ignored.
        """
        self._error_hooks.append(fn)

    def _notify_error(self, command_name: str, exc: Exception) -> None:
        for fn in self._error_hooks:
            try:
                fn(command_name, exc)
            except Exception:
                logger.exception("IPC error hook %r failed", fn)

    def close(self, timeout: float = 2.0) -> None:
        """
        Stop the async event loop and join its thread.

        The loop thread is a daemon, so the process can exit without this — but only
        by abandoning the thread mid-task. Calling close() lets in-flight work settle
        and releases the loop's resources deterministically, which also keeps test
        runs from accumulating a live loop thread per App they construct.

        Safe to call more than once, and on an IPC whose loop was never started —
        an app with no async commands never builds one.
        """
        if self._loop is None or self._loop.is_closed():
            return

        self._loop.call_soon_threadsafe(self._loop.stop)
        self._loop_thread.join(timeout=timeout)

        if self._loop_thread.is_alive():
            # A command is still blocking the loop. Leaving the loop open is the
            # lesser evil: closing it underneath a running task raises there and can
            # lose the task's own cleanup.
            logger.warning(
                "IPC loop thread did not stop within %.1fs; leaving it running", timeout
            )
            return

        try:
            self._loop.close()
        except Exception:
            logger.exception("Failed to close the IPC event loop")

    def handle(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        Handle an incoming IPC message from the frontend.

        Expected message format:
            {
                "id": <request_id>,
                "command": "<command_name>",
                "args": {...}  # optional
            }

        Args:
            message: Dictionary containing the request

        Returns:
            Response dictionary with one of these formats:
            - Success: {"id": id, "ok": True, "result": result}
            - Error: {"id": id, "ok": False, "error": {"type": type, "message": message}}
        """
        if not isinstance(message, dict):
            return {
                "id": None,
                "ok": False,
                "error": {
                    "type": "InvalidMessageError",
                    "message": "IPC message must be a dictionary"
                }
            }

        request_id = message.get("id")
        command_name = message.get("command")
        args = message.get("args", {})

        if request_id is None:
            return {
                "id": None,
                "ok": False,
                "error": {
                    "type": "InvalidRequestError",
                    "message": "Missing request id"
                }
            }

        if not command_name:
            return {
                "id": request_id,
                "ok": False,
                "error": {
                    "type": "InvalidRequestError",
                    "message": "Missing command name"
                }
            }

        try:
            command = self.registry.get(command_name)
        except CommandNotFoundError as e:
            return {
                "id": request_id,
                "ok": False,
                "error": {
                    "type": "CommandNotFoundError",
                    "message": str(e)
                }
            }

        if not isinstance(args, dict):
            return {
                "id": request_id,
                "ok": False,
                "error": {"type": "ValidationError", "message": "args must be an object/dict."},
            }

        err = _validate_args(command, args)
        if err:
            return {
                "id": request_id,
                "ok": False,
                "error": {"type": "ValidationError", "message": err},
            }

        # Each phase reports failures under its own error type. A guard rejecting a
        # call is policy and the frontend may act on it; a guard or middleware raising
        # is a bug in the app. Collapsing both into the command's error shape, as this
        # did before, left the frontend unable to tell "you may not do this" apart from
        # "the check itself broke".
        try:
            try:
                for guard_fn in self.registry._guards.get(command_name, []):
                    if inspect.iscoroutinefunction(guard_fn):
                        future = asyncio.run_coroutine_threadsafe(
                            guard_fn(command_name, args), self._ensure_loop()
                        )
                        ok = future.result()
                    else:
                        ok = guard_fn(command_name, args)
                    if ok is not True and ok is not None:
                        raise ForbiddenError("Forbidden")
            except ForbiddenError as e:
                # Denial — either ours above or raised deliberately by the guard.
                return self._error(request_id, "ForbiddenError", str(e))
            except Exception as e:
                self._notify_error(command_name, e)
                return self._error(
                    request_id, "GuardError", str(e), cause=e.__class__.__name__
                )

            try:
                for mw in self._middleware:
                    if inspect.iscoroutinefunction(mw):
                        future = asyncio.run_coroutine_threadsafe(
                            mw(command_name, args), self._ensure_loop()
                        )
                        future.result()
                    else:
                        mw(command_name, args)
            except ForbiddenError as e:
                # Middleware is also allowed to reject a call outright.
                return self._error(request_id, "ForbiddenError", str(e))
            except Exception as e:
                self._notify_error(command_name, e)
                return self._error(
                    request_id, "MiddlewareError", str(e), cause=e.__class__.__name__
                )

            try:
                if inspect.iscoroutinefunction(command):
                    future = asyncio.run_coroutine_threadsafe(
                        command(**args), self._ensure_loop()
                    )
                    result = future.result()
                else:
                    result = command(**args)
            except Exception as e:
                self._notify_error(command_name, e)
                return self._error(request_id, e.__class__.__name__, str(e))

            return {
                "id": request_id,
                "ok": True,
                "result": result
            }
        finally:
            for fn in self._teardown:
                try:
                    fn()
                except Exception:
                    logger.exception("Teardown callback %r failed", fn)

    def _error(
        self,
        request_id: Any,
        error_type: str,
        message: str,
        *,
        cause: str | None = None,
    ) -> dict[str, Any]:
        """Build an error response for the exception currently being handled."""
        error: dict[str, Any] = {"type": error_type, "message": message}

        # The original exception class, when it is not already the reported type.
        # Lets a frontend log the real cause without losing the phase distinction.
        if cause is not None and cause != error_type:
            error["cause"] = cause

        if self.debug:
            error["traceback"] = traceback.format_exc()

        return {"id": request_id, "ok": False, "error": error}
