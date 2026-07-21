# IPC

Vesper's IPC (Inter-Process Communication) bridge connects the JavaScript frontend to Python backend commands. Every call goes through a typed, validated pipeline.

---

## How a call flows

```
JS: vesper.invoke("greet", { name: "Alice" })
    ↓
vesper.js → pywebview.api.invoke(JSON payload)
    ↓
IPC.handle() — deserializes the message
    ↓
Arg validation — checks against the Python function signature
    ↓
Guard chain — each guard returns True/False
    ↓
Middleware chain — wraps around execution
    ↓
CommandRegistry.get("greet") → calls the function
    ↓
Returns { id, ok: true, result } or { id, ok: false, error }
    ↓
vesper.js resolves or rejects the Promise
```

---

## Registering commands

### Bare decorator

```python
@app.command
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

The command name defaults to the function name: `"greet"`.

### String alias

```python
@app.command("say-hello")
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

### Keyword alias

```python
@app.command(name="say-hello")
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

---

## Calling from JavaScript

```js
const result = await vesper.invoke("greet", { name: "Alice" })
```

`vesper.invoke` returns a Promise. It resolves to the return value of the Python function or rejects with an error object.

Arguments must be JSON-serializable: strings, numbers, booleans, lists, plain objects. No class instances, file handles, or binary data (see [File Transfers](file-transfers.md) for binary).

---

## Argument validation

Vesper validates arguments against the Python function's signature **before** running guards or the command. This happens at the IPC layer — your function is never called with invalid input.

**Missing required argument**
```js
await vesper.invoke("greet", {})
// rejects with: { type: "ValidationError", message: "missing argument: name" }
```

**Unexpected argument**
```js
await vesper.invoke("greet", { name: "Alice", extra: 1 })
// rejects with: { type: "ValidationError", message: "unexpected argument: extra" }
```

**Commands with `**kwargs` skip the unexpected-argument check** — they explicitly accept arbitrary keys.

---

## Return values

Return any JSON-serializable value: a string, number, boolean, list, or dict.

```python
@app.command
def get_user(user_id: int) -> dict:
    return {"id": user_id, "name": "Alice"}
```

Returning `None` is valid — the JS Promise resolves to `null`.

---

## Async commands

`async def` commands are fully supported. Vesper runs a dedicated asyncio event loop on a background thread; async commands dispatch via `asyncio.run_coroutine_threadsafe`.

```python
import httpx

@app.command
async def fetch(url: str) -> str:
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
        return r.text
```

Sync and async commands can coexist freely — the dispatch is handled automatically.

---

## Error handling

When a command raises an exception, the IPC returns `{ ok: false, error: { type, message } }` and the JavaScript Promise rejects.

```js
try {
    const result = await vesper.invoke("get_user", { user_id: 99 })
} catch (err) {
    console.error(err.type, err.message)
}
```

Built-in error types:

| Type | Cause |
|---|---|
| `ValidationError` | Missing or unexpected arguments |
| `CommandNotFoundError` | No command registered under that name |
| `ForbiddenError` | A guard or middleware rejected the call |
| `GuardError` | A guard itself raised an exception |
| `MiddlewareError` | A middleware itself raised an exception |
| *(the exception's own class)* | The command raised — e.g. `KeyError`, `ValueError` |

The pipeline reports **which phase failed**, so the frontend can tell policy from
breakage. `ForbiddenError` means "you may not do this" and is worth acting on;
`GuardError` means the check itself is broken and is a bug in the app.

```js
try {
    await vesper.invoke("delete_user", { user_id: 1 })
} catch (err) {
    if (err.type === "ForbiddenError") showLoginPrompt()
    else if (err.type === "GuardError") reportBug(err)
}
```

When a guard or middleware raises something other than `ForbiddenError`, the original
exception class is preserved in an `error.cause` field so the real cause is not lost:

```json
{ "type": "GuardError", "cause": "PermissionError", "message": "not allowed" }
```

In debug mode (`App(debug=True)`), error responses carry a Python traceback in a
separate `error.traceback` field.

---

## Message format

The raw IPC message format (handled internally by `vesper.js` and `IPC` — you normally never see this):

**Request**
```json
{ "id": "abc123", "command": "greet", "args": { "name": "Alice" } }
```

**Success response**
```json
{ "id": "abc123", "ok": true, "result": "Hello, Alice!" }
```

**Error response**
```json
{ "id": "abc123", "ok": false, "error": { "type": "CommandNotFoundError", "message": "..." } }
```

The `id` field lets `vesper.js` match responses to the correct Promise when multiple calls are in-flight simultaneously.

---

## Calling IPC from Python

For testing or internal use, you can call the IPC layer directly from Python:

```python
response = app.ipc.handle({
    "id": "test",
    "command": "greet",
    "args": {"name": "Alice"},
})
assert response["ok"] is True
assert response["result"] == "Hello, Alice!"
```

---

## Related

- [Guards](guards.md) — reject calls before execution
- [Middleware](middleware.md) — wrap every call with cross-cutting logic
- [Events](events.md) — push data from Python to JS without a request
- [Module System](module-system.md) — organize commands into controllers
