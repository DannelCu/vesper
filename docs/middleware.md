# Middleware

Middleware wraps every IPC call. It runs after guards and before the command, giving you a place to observe, log, time, or transform requests and responses.

---

## Registering middleware

```python
@app.middleware
async def log_middleware(command: str, args: dict, next):
    print(f"→ {command} {args}")
    result = await next(command, args)
    print(f"← {command} {result}")
    return result
```

`@app.middleware` accepts both `async def` and plain `def` functions. The `next` parameter is always awaitable.

---

## Signature

```python
async def my_middleware(command: str, args: dict, next) -> any:
    ...
    result = await next(command, args)
    ...
    return result
```

- `command` — the IPC command name (e.g. `"users.get_user"`)
- `args` — the validated argument dictionary
- `next` — call this to pass control to the next middleware or the command itself
- Return value — must return the result (either from `next` or a replacement)

Not calling `next()` short-circuits the pipeline and returns whatever you return instead — useful for caching:

```python
@app.middleware
async def cache_middleware(command: str, args: dict, next):
    key = f"{command}:{args}"
    if key in cache:
        return cache[key]
    result = await next(command, args)
    cache[key] = result
    return result
```

---

## Execution order

Middleware registered first wraps outermost:

```python
@app.middleware
async def first(command, args, next):    # runs first (outermost)
    ...

@app.middleware
async def second(command, args, next):   # runs second (innermost)
    ...
```

Execution order for a call: `first → second → command → second → first`

---

## Error handling in middleware

Exceptions raised inside `next()` propagate up through the middleware chain. You can catch and handle them:

```python
@app.middleware
async def error_reporter(command: str, args: dict, next):
    try:
        return await next(command, args)
    except Exception as exc:
        report_to_sentry(command, exc)
        raise   # re-raise so IPC still returns { ok: false, error: ... }
```

---

## Timing middleware

```python
import time

@app.middleware
async def timing_middleware(command: str, args: dict, next):
    start = time.monotonic()
    result = await next(command, args)
    elapsed_ms = (time.monotonic() - start) * 1000
    print(f"{command} took {elapsed_ms:.1f}ms")
    return result
```

---

## Middleware shared by reference

`App._middleware` is passed by reference to `IPC._middleware`. Middleware registered after `App.__init__` is still visible to all subsequent calls — you can add middleware at any time before `app.run()`.

---

## Guards vs middleware

| | Guards | Middleware |
|---|---|---|
| Purpose | Allow or deny | Observe or transform |
| Return value | `bool` | result (from `next` or own) |
| On rejection | `ForbiddenError` | depends on what you return |
| Order | Before middleware | After guards |

See [Guards](guards.md) for access control. See [Recipes — IPC Logging](recipes/logging-middleware.md) for a ready-to-use logging setup.
