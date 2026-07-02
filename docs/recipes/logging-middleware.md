# Recipe: IPC Logging Middleware

Add structured logging and timing to every IPC call during development. This middleware is safe to leave in place for production — it just becomes a no-op when `debug=False` or a log level filter is applied.

---

## Simple timing middleware

```python
import time
import logging

log = logging.getLogger("vesper.ipc")

@app.middleware
async def timing_middleware(command: str, args: dict, next):
    start = time.monotonic()
    try:
        result = await next(command, args)
        elapsed = (time.monotonic() - start) * 1000
        log.debug("%-40s %6.1f ms  OK", command, elapsed)
        return result
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        log.warning("%-40s %6.1f ms  ERROR: %s", command, elapsed, exc)
        raise
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
    async def dev_logger(command: str, args: dict, next):
        print(f"→ {command}  args={args}")
        result = await next(command, args)
        print(f"← {command}  result={result!r}")
        return result
```

---

## Structured JSON logging

For production observability (log aggregation, Datadog, etc.):

```python
import json, time, logging

log = logging.getLogger("vesper.ipc")

@app.middleware
async def structured_logger(command: str, args: dict, next):
    start = time.monotonic()
    try:
        result = await next(command, args)
        log.info(json.dumps({
            "command": command,
            "duration_ms": round((time.monotonic() - start) * 1000, 2),
            "ok": True,
        }))
        return result
    except Exception as exc:
        log.error(json.dumps({
            "command": command,
            "duration_ms": round((time.monotonic() - start) * 1000, 2),
            "ok": False,
            "error": str(exc),
        }))
        raise
```

---

## Filtering sensitive commands

Avoid logging args for commands that handle passwords or secrets:

```python
SENSITIVE = {"login", "set_password", "vesper:keychain:set"}

@app.middleware
async def safe_logger(command: str, args: dict, next):
    safe_args = "<redacted>" if command in SENSITIVE else args
    print(f"→ {command}  {safe_args}")
    result = await next(command, args)
    print(f"← {command}  ok")
    return result
```

---

## Middleware execution order

If you register multiple middlewares, they wrap in registration order. The logger should be registered first so it wraps everything including other middleware:

```python
@app.middleware
async def logger(command, args, next): ...       # outermost — logs the full duration

@app.middleware
async def auth_checker(command, args, next): ... # inner — checked after logger starts

@app.middleware
async def cache(command, args, next): ...        # innermost — before the command
```

Order of execution: `logger → auth_checker → cache → command → cache → auth_checker → logger`
