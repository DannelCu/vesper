# Middleware

Middleware runs before every IPC call, after guards and before the command. Use it to
observe, log, or reject requests.

---

## Registering middleware

```python
@app.middleware
def log_middleware(command: str, args: dict) -> None:
    print(f"-> {command} {args}")
```

`@app.middleware` accepts both `def` and `async def` functions.

---

## Signature

```python
def my_middleware(command: str, args: dict) -> None:
    ...
```

- `command` — the IPC command name (e.g. `"users.get_user"`)
- `args` — the validated argument dictionary
- Return value is ignored — middleware cannot replace or transform the command's
  result. To reject a call, raise (see below); to allow it, return normally.

Middleware does not wrap the command call — there is no way to run code *after* the
command finishes, see its result, or measure its duration from inside a middleware
function. If you need that, see
[Recipes — IPC Logging Middleware, "Timing and result, not just invocation"](recipes/logging-middleware.md#timing-and-result-not-just-invocation)
for the pattern that actually provides it (a wrapper around the command registry, not
`app.middleware()`).

---

## Execution order

Middleware registered first runs first, all before the command:

```python
@app.middleware
def first(command, args): ...    # runs first

@app.middleware
def second(command, args): ...   # runs second

# then the command itself
```

---

## Rejecting a call

Raise `ForbiddenError` to deny a call — reported the same way a guard rejection is
(see [Guards](guards.md)):

```python
from vesper import ForbiddenError

@app.middleware
def rate_limit(command: str, args: dict) -> None:
    if too_many_calls():
        raise ForbiddenError("Rate limit exceeded")
```

---

## When middleware fails

A middleware that raises anything other than `ForbiddenError` is a bug in the
middleware, not a rejected call, so it is reported under its own error type with the
original exception preserved as the cause, and the command does not run:

```json
{ "type": "MiddlewareError", "cause": "RuntimeError", "message": "redis down" }
```

---

## Guards vs middleware

| | Guards | Middleware |
|---|---|---|
| Purpose | Allow or deny | Observe, log, or reject |
| Return value | `bool` | ignored |
| On rejection | `ForbiddenError` | raise `ForbiddenError` yourself |
| Order | Before middleware | After guards, before the command |
| Sees the command's result | No | No — neither guards nor middleware wrap execution |

See [Guards](guards.md) for access control. See
[Recipes — IPC Logging](recipes/logging-middleware.md) for a ready-to-use logging
setup, including the workaround for timing/result logging.

---

## Middleware shared by reference

`App._middleware` is passed by reference to `IPC._middleware`. Middleware registered
after `App.__init__` is still visible to all subsequent calls — you can add
middleware at any time before `app.run()`.

See [IPC](ipc.md) for the full error type table.
