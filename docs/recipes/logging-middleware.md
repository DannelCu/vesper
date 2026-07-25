# Recipe: IPC Logging Middleware

Add structured logging to every IPC call during development. This middleware is safe
to leave in place for production — it just becomes a no-op when `debug=False` or a log
level filter is applied.

**What middleware can and cannot do here.** `app.middleware()` runs a function
*before* every command, guard denials included — see [Middleware](../middleware.md).
It is not a wrapper around the command: there is no `next` to call, so a middleware
function cannot see the command's result or measure its duration. Everything below
logs the *invocation* (command name and args) as the call starts. If you also want
duration and result/failure per call, see
["Timing and result, not just invocation"](#timing-and-result-not-just-invocation)
further down — that part is not middleware, it is a small wrapper around the command
registry.

---

## Simple invocation logging

```python
import logging

log = logging.getLogger("vesper.ipc")

@app.middleware
def log_invocation(command: str, args: dict) -> None:
    log.debug("-> %s %s", command, args)
```

Configure logging before `app.run()`:

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s %(name)s — %(message)s",
)
```

---

## Dev-only middleware

Only activate the middleware in development:

```python
import os

if os.environ.get("VESPER_DEV_URL"):   # set by vesper dev
    @app.middleware
    def dev_logger(command: str, args: dict) -> None:
        print(f"-> {command}  args={args}")
```

---

## Structured JSON logging

For production observability (log aggregation, Datadog, etc.):

```python
import json
import logging

log = logging.getLogger("vesper.ipc")

@app.middleware
def structured_logger(command: str, args: dict) -> None:
    log.info(json.dumps({"command": command, "args": args}))
```

---

## Filtering sensitive commands

Avoid logging args for commands that handle passwords or secrets:

```python
SENSITIVE = {"login", "set_password", "keychain:set"}

@app.middleware
def safe_logger(command: str, args: dict) -> None:
    safe_args = "<redacted>" if command in SENSITIVE else args
    print(f"-> {command}  {safe_args}")
```

---

## Rejecting a call from middleware

Raise `ForbiddenError` to deny a call outright — the same policy-denial phase a guard
rejection produces (see [Guards](../guards.md)):

```python
from vesper import ForbiddenError

@app.middleware
def rate_limit(command: str, args: dict) -> None:
    if too_many_calls():
        raise ForbiddenError("Rate limit exceeded")
```

Raising anything else is reported as a `MiddlewareError` — a bug in the middleware,
not a rejected call — and the command never runs. See
[Middleware — "When middleware fails"](../middleware.md#when-middleware-fails).

---

## Middleware execution order

Multiple middleware run in registration order, all before the command:

```python
@app.middleware
def first(command, args): ...   # runs first

@app.middleware
def second(command, args): ...  # runs second

# order: first -> second -> command
```

---

## Timing and result, not just invocation

Measuring how long a command took, or whether it succeeded, needs to run code *after*
the command returns — which middleware, as implemented, cannot do. The workaround is a
small wrapper installed once around every registered command, after your modules are
registered:

```python
import functools
import time

def log_command(name, fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.monotonic()
        try:
            result = fn(*args, **kwargs)
            log.debug("%-30s %6.1f ms  OK", name, (time.monotonic() - start) * 1000)
            return result
        except Exception as exc:
            log.warning("%-30s %6.1f ms  ERROR: %s", name, (time.monotonic() - start) * 1000, exc)
            raise
    return wrapper

# After app.register_module(...) / all @app.command registrations:
for name, fn in list(app.registry._commands.items()):
    if not name.startswith("vesper:"):
        app.registry._commands[name] = log_command(name, fn)
```

A guard rejection never reaches this wrapper — `IPC.handle()` checks guards before it
looks the command up and calls it, so `ForbiddenError`/`GuardError` responses are
never logged as if the command ran. See `examples/ops-console/modules/common/telemetry.py`
for a complete, tested version of this pattern feeding a live "last commands" panel.
