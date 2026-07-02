# Guards

Guards control access to individual commands. A guard is a function that runs before middleware and the command itself. If it returns `False`, the call is rejected with a `ForbiddenError` and the command never executes.

---

## Basic usage

```python
from vesper import App, guard

app = App(...)

def auth_guard(command: str, args: dict) -> bool:
    return session.is_authenticated()

@app.command
@guard(auth_guard)
def delete_user(user_id: int):
    ...
```

A guard receives two arguments: the command name (`str`) and the validated arguments (`dict`). It must return a truthy or falsy value.

---

## Async guards

Guards can be `async def`:

```python
async def token_guard(command: str, args: dict) -> bool:
    return await verify_token(args.get("token"))

@app.command
@guard(token_guard)
async def protected_action(): ...
```

---

## Stacking guards

Multiple `@guard` decorators can be stacked. The outermost decorator runs first:

```python
@app.command
@guard(auth_guard)       # runs first
@guard(rate_limit_guard) # runs second (only if auth_guard passed)
def sensitive_action(): ...
```

All stacked guards pass the same `(command, args)` arguments.

---

## Controller-level guards

Apply guards to every command in a controller using the `guards=[]` parameter on `@Controller`:

```python
from vesper import Controller, command, guard

@Controller("admin", guards=[auth_guard])
class AdminController:
    @command
    def list_users(self): ...   # auth_guard runs here

    @command
    @guard(superuser_guard)
    def delete_all(self): ...   # auth_guard runs first, then superuser_guard
```

Controller-level guards run before any method-level `@guard` decorators.

---

## What the frontend sees on rejection

When a guard returns `False`, the JS Promise rejects with:

```json
{ "type": "ForbiddenError", "message": "Forbidden" }
```

```js
try {
    await vesper.invoke("delete_user", { user_id: 1 })
} catch (err) {
    if (err.type === "ForbiddenError") {
        showLoginPrompt()
    }
}
```

---

## Passing context to guards

Guards only receive `command` and `args`. For session state, use a module-level or closure-based approach:

```python
# Simple module-level session
_session = {"user": None}

def auth_guard(command: str, args: dict) -> bool:
    return _session["user"] is not None

@app.command
def login(username: str, password: str) -> bool:
    if check_credentials(username, password):
        _session["user"] = username
        return True
    return False
```

For a full authentication system with roles and localStorage persistence, see the [Authentication with Roles recipe](recipes/auth.md).

---

## Guards vs middleware

| | Guards | Middleware |
|---|---|---|
| Purpose | Allow or deny the call | Observe or transform the call |
| Return value | `bool` | calls `next()`, can modify result |
| On rejection | `ForbiddenError`, command skipped | N/A |
| Order | Before middleware | After guards, before command |

Use guards for access control. Use middleware for logging, timing, or cross-cutting logic. See [Middleware](middleware.md).
