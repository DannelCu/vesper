"""
The "last N commands" ring buffer behind the middleware panel.

The plan asks for IPC logging + timing middleware with a panel showing what
just ran — the textbook use case for docs/recipes/logging-middleware.md,
which documents middleware as `async def mw(command, args, next): result =
await next(command, args); ...`.

That recipe does not match what actually runs. `IPC.handle()` (vesper/core/
ipc.py) calls every registered middleware as `mw(command_name, args)` —
**two** arguments, no `next` — and `App.middleware()`'s own docstring agrees:
"Signature: fn(command: str, args: Any) -> None". A middleware written the
way the recipe shows raises `TypeError: mw() missing 1 required positional
argument: 'next'` on the very first IPC call. There is no way, with the
middleware hook as implemented, to wrap the command and observe its result
or duration — middleware can only run *before* the command and reject by
raising. See the friction report in README.md for the reproduction.

The workaround here is a decorator-free one: `install()` runs once, after
every module is registered, and replaces each user command in the registry
with a timed wrapper. That is IPC-level in the sense that it covers every
command uniformly without touching the four modules' own code, even though
it is not literally the `app.middleware()` hook, which cannot do this.
"""
from __future__ import annotations

import functools
import time
from collections import deque

LOG_LIMIT = 200
log: deque = deque(maxlen=LOG_LIMIT)

# Never put a raw password in the panel, even redacted-elsewhere-but-here.
_SENSITIVE_ARGS = {"password"}


def redact(args: dict) -> dict:
    return {k: ("<redacted>" if k in _SENSITIVE_ARGS else v) for k, v in (args or {}).items()}


def _wrap(name: str, fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.monotonic()
        try:
            result = fn(*args, **kwargs)
            log.appendleft({
                "command": name,
                "args": redact(kwargs),
                "ok": True,
                "duration_ms": round((time.monotonic() - start) * 1000, 2),
                "ts": time.time(),
            })
            return result
        except Exception as exc:
            log.appendleft({
                "command": name,
                "args": redact(kwargs),
                "ok": False,
                "error": str(exc),
                "error_type": exc.__class__.__name__,
                "duration_ms": round((time.monotonic() - start) * 1000, 2),
                "ts": time.time(),
            })
            raise

    return wrapper


def install(registry) -> None:
    """
    Wrap every registered app command (not the framework's own ``vesper:*``
    ones) with timing + result logging. Call once, after the last module is
    registered, so every command in ``registry._commands`` already exists.

    Guard rejections never reach here: ``IPC.handle()`` checks guards before
    it looks the command up and calls it, so a ForbiddenError never runs the
    wrapped function at all — exactly the phase distinction the plan wants
    visible. The frontend panel shows only commands whose bodies actually ran.
    """
    for command_name, fn in list(registry._commands.items()):
        if command_name.startswith("vesper:"):
            continue
        registry._commands[command_name] = _wrap(command_name, fn)


def recent(limit: int = 50) -> list[dict]:
    return list(log)[:limit]
