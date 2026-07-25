# vesper-http

HTTP client plugin for Vesper. Proxies HTTP requests through Python to solve CORS restrictions in the WebView. Uses [httpx](https://www.python-httpx.org/) under the hood.

---

## Install

```bash
pip install vesper-http
```

---

## Why a proxy?

Web browsers (including the WebView that Vesper uses) enforce CORS (Cross-Origin Resource Sharing). Many APIs do not send the headers needed to allow WebView requests. By routing requests through Python, the restriction disappears — Python is not a browser and has no CORS restrictions.

---

## Setup

```python
from vesper import App
from vesper_http import HttpPlugin

app = App(
    title="My App",
    frontend="dist/index.html",
    plugins=[HttpPlugin()],
)
```

---

## JavaScript API

Add the SDK:

```toml
[plugins]
http = "vesper-http"
```

```bash
vesper sync-sdk
```

```html
<script src="vesper.js"></script>
<script src="vesper-http.js"></script>
```

### GET

```js
const response = await vesper.http.get("https://api.example.com/users")
// response: { status, ok, headers, body, json }
// body is the raw response text; json is the parsed body (or null if it wasn't JSON)

const users = response.json
```

### POST

There is no separate body argument — the body goes inside the second (`options`)
argument, as `json` (auto-serialized) or `data` (form-encoded):

```js
const response = await vesper.http.post(
    "https://api.example.com/users",
    { json: { name: "Alice", email: "alice@example.com" } }
)
```

### PUT / PATCH / DELETE

```js
await vesper.http.put(url, options?)     // options: { json?, data?, headers?, timeout? }
await vesper.http.patch(url, options?)   // options: { json?, data?, headers?, timeout? }
await vesper.http.delete(url, options?)  // options: { params?, headers?, timeout? }
```

### Options

Every method takes the URL and a single optional `options` object — never a separate
body argument:

```js
const response = await vesper.http.get("https://api.example.com/data", {
    headers: {
        "Authorization": "Bearer token123",
    },
    timeout: 30,   // seconds (default: 30)
})
```

`get`/`delete` accept `params` (query string) in `options`; `post`/`put`/`patch`
accept `json`/`data` (request body) instead.

---

## Python injection (HttpClient)

Use `HttpClient` as a DI type in services:

```python
from vesper import Injectable
from vesper_http import HttpClient

@Injectable()
class GitHubService:
    def __init__(self, http: HttpClient):
        self.http = http
        self.base = "https://api.github.com"

    def get_user(self, username: str) -> dict:
        resp = self.http.get(
            f"{self.base}/users/{username}",
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        return resp["json"]
```

`HttpClient` is a small wrapper around `httpx.Client`, not an `httpx.Client`/`Response`
itself — every method (`get`, `post`, `put`, `patch`, `delete`) returns a plain `dict`:

```python
{
    "status": 200,
    "ok": True,          # True when status < 400
    "headers": {...},
    "body": "...",        # raw response text
    "json": {...} | None, # parsed JSON, or None if the body wasn't JSON
}
```

There is no `.raise_for_status()` or `.text` on the result — check `resp["ok"]` /
`resp["status"]` and read `resp["json"]` or `resp["body"]` directly. For async
services, use `httpx.AsyncClient` directly instead of `HttpClient`.

---

## IPC command names

| Command | Method | Extra args |
|---|---|---|
| `http:get` | GET | `params?, headers?, timeout?` |
| `http:post` | POST | `json?, data?, headers?, timeout?` |
| `http:put` | PUT | `json?, data?, headers?, timeout?` |
| `http:patch` | PATCH | `json?, data?, headers?, timeout?` |
| `http:delete` | DELETE | `params?, headers?, timeout?` |

There is no generic `body` field — POST/PUT/PATCH take `json` (auto-serialized) or
`data` (form-encoded) instead.

---

## Response format

All HTTP commands return:

```json
{
    "status": 200,
    "ok": true,
    "headers": { "content-type": "application/json", ... },
    "body": "<response body as string>",
    "json": { "...": "..." }
}
```

`json` is the parsed body, or `null` if it was not JSON. Non-2xx status codes do
**not** reject the Promise — use `ok` (or `status`) to handle errors:

```js
const response = await vesper.http.get("https://api.example.com/data")
if (!response.ok) {
    console.error("HTTP error:", response.status, response.body)
    return
}
const data = response.json
```

---

## Authentication headers

Pass auth headers in options:

```js
const headers = { "Authorization": `Bearer ${token}` }

const response = await vesper.http.get("/api/protected", { headers })
```

Or set default headers once, via an injected service rather than a plain command —
`HttpClient` is only reachable through DI (`app.register_global_provider`), so a
bare `@app.command` function has no built-in way to reach the same instance:

```python
from vesper import Injectable, Controller, command
from vesper_http import HttpClient

API_KEY = "..."

@Injectable()
class ApiService:
    def __init__(self, http: HttpClient):
        self.http = http

    def get(self, path: str) -> dict:
        resp = self.http.get(f"https://api.example.com{path}",
                              headers={"X-API-Key": API_KEY})
        return resp["json"]

@Controller("api")
class ApiController:
    def __init__(self, svc: ApiService):
        self.svc = svc

    @command
    def get(self, path: str) -> dict:
        return self.svc.get(path)
```
