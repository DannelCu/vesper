# Recipe: Authentication with Roles

This recipe implements session-based authentication with role-based access control in a Vesper app. User sessions are persisted in `localStorage` so the user stays logged in across app restarts.

---

## Overview

- Credentials are checked in Python
- A session token is generated and stored server-side in a Python dict
- The token is also stored in `localStorage` so it survives restarts
- Guards read the token from the `args` dict and validate it server-side
- Commands declare their required role; the guard checks it

---

## Python backend

```python
# app.py
import secrets
import hashlib
from vesper import App, guard

app = App(title="My App", frontend="dist/index.html")

# ── In-memory session store ──────────────────────────────────────────────────

SESSIONS: dict[str, dict] = {}   # token → {"username": str, "role": str}

USERS = {
    "admin": {"password_hash": hashlib.sha256(b"admin123").hexdigest(), "role": "admin"},
    "alice": {"password_hash": hashlib.sha256(b"alice123").hexdigest(), "role": "user"},
}

# ── Auth commands ────────────────────────────────────────────────────────────

@app.command
def login(username: str, password: str) -> dict:
    user = USERS.get(username)
    if not user:
        return {"ok": False, "error": "Invalid credentials"}

    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    if pw_hash != user["password_hash"]:
        return {"ok": False, "error": "Invalid credentials"}

    token = secrets.token_hex(32)
    SESSIONS[token] = {"username": username, "role": user["role"]}
    return {"ok": True, "token": token, "role": user["role"]}


@app.command
def logout(token: str) -> bool:
    SESSIONS.pop(token, None)
    return True


@app.command
def me(token: str) -> dict | None:
    return SESSIONS.get(token)


# ── Guards ──────────────────────────────────────────────────────────────────

def require_auth(command: str, args: dict) -> bool:
    token = args.get("token")
    return token is not None and token in SESSIONS


def require_admin(command: str, args: dict) -> bool:
    token = args.get("token")
    session = SESSIONS.get(token)
    return session is not None and session["role"] == "admin"


# ── Protected commands ───────────────────────────────────────────────────────

@app.command
@guard(require_auth)
def get_dashboard_data(token: str) -> dict:
    session = SESSIONS[token]
    return {"message": f"Hello, {session['username']}!", "data": [1, 2, 3]}


@app.command
@guard(require_auth)
@guard(require_admin)
def admin_action(token: str) -> str:
    return "Admin-only action executed."


@app.command
@guard(require_admin)
def list_users(token: str) -> list:
    return [{"username": u, "role": v["role"]} for u, v in USERS.items()]


if __name__ == "__main__":
    app.run()
```

---

## Frontend

### Auth helper (`auth.js`)

```js
// frontend/auth.js

const TOKEN_KEY = "vesper_auth_token"

export function getToken() {
    return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
    localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
    localStorage.removeItem(TOKEN_KEY)
}

export async function login(username, password) {
    const result = await vesper.invoke("login", { username, password })
    if (result.ok) {
        setToken(result.token)
    }
    return result
}

export async function logout() {
    const token = getToken()
    if (token) {
        await vesper.invoke("logout", { token })
        clearToken()
    }
}

export async function me() {
    const token = getToken()
    if (!token) return null
    return vesper.invoke("me", { token })
}

export async function callProtected(command, args = {}) {
    const token = getToken()
    if (!token) throw new Error("Not authenticated")
    return vesper.invoke(command, { ...args, token })
}
```

### Login page

```html
<!-- frontend/index.html -->
<form id="login-form">
    <input id="username" placeholder="Username" />
    <input id="password" type="password" placeholder="Password" />
    <button type="submit">Login</button>
    <p id="error" style="color:red"></p>
</form>
<div id="app" style="display:none">
    <p id="greeting"></p>
    <button id="admin-btn">Admin Action</button>
    <button id="logout-btn">Logout</button>
</div>

<script src="vesper.js"></script>
<script type="module">
import { login, logout, me, callProtected, getToken } from "./auth.js"

// Restore session on startup
async function init() {
    const user = await me()
    if (user) {
        showApp(user)
    }
}

document.getElementById("login-form").onsubmit = async (e) => {
    e.preventDefault()
    const username = document.getElementById("username").value
    const password = document.getElementById("password").value

    const result = await login(username, password)
    if (result.ok) {
        const user = await me()
        showApp(user)
    } else {
        document.getElementById("error").textContent = result.error
    }
}

document.getElementById("logout-btn").onclick = async () => {
    await logout()
    document.getElementById("app").style.display = "none"
    document.getElementById("login-form").style.display = "block"
}

document.getElementById("admin-btn").onclick = async () => {
    try {
        const result = await callProtected("admin_action")
        alert(result)
    } catch (err) {
        if (err.type === "ForbiddenError") {
            alert("You do not have admin access.")
        } else {
            // GuardError means the check itself broke — a bug, not a denial.
            console.error(err.type, err.message)
        }
    }
}

function showApp(user) {
    document.getElementById("login-form").style.display = "none"
    document.getElementById("app").style.display = "block"
    document.getElementById("greeting").textContent =
        `Welcome, ${user.username}! (${user.role})`
}

init()
</script>
```

---

## How the token flows

1. User submits the login form → `vesper.invoke("login", { username, password })`
2. Python validates credentials, generates a `secrets.token_hex(32)` token, stores it in `SESSIONS`
3. JS receives the token, stores it in `localStorage`
4. Subsequent calls pass the token as `{ token, ...args }` via `callProtected()`
5. Guards on protected commands read `args["token"]` and validate against `SESSIONS`
6. On app restart, `me()` is called on startup — if the token is still in `SESSIONS` (in-memory, so it resets on restart), the user is shown the app; otherwise the login form is shown

### Making sessions survive restarts

The in-memory `SESSIONS` dict is reset every time the app restarts. To persist sessions across restarts, save them to disk. A simple approach:

```python
import json, pathlib

SESSION_FILE = pathlib.Path.home() / ".myapp" / "sessions.json"

def load_sessions():
    if SESSION_FILE.exists():
        return json.loads(SESSION_FILE.read_text())
    return {}

def save_sessions():
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(SESSIONS))

SESSIONS = load_sessions()

# Call save_sessions() after login and logout
```

Use `vesper-keychain` to store the session file location or the token itself more securely on the client.

---

## Role hierarchy

For more than two roles, implement a role hierarchy check:

```python
ROLE_LEVELS = {"user": 1, "moderator": 2, "admin": 3}

def require_role(min_role: str):
    def guard_fn(command: str, args: dict) -> bool:
        token = args.get("token")
        session = SESSIONS.get(token)
        if not session:
            return False
        return ROLE_LEVELS.get(session["role"], 0) >= ROLE_LEVELS[min_role]
    return guard_fn

@app.command
@guard(require_role("moderator"))
def moderate_content(token: str, content_id: int): ...

@app.command
@guard(require_role("admin"))
def delete_user(token: str, user_id: int): ...
```
