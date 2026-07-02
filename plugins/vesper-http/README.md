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
// response: { status, headers, body }
// body is a string — parse JSON with JSON.parse()

const users = JSON.parse(response.body)
```

### POST

```js
const response = await vesper.http.post(
    "https://api.example.com/users",
    JSON.stringify({ name: "Alice", email: "alice@example.com" }),
    { headers: { "Content-Type": "application/json" } }
)
```

### PUT / PATCH / DELETE

```js
await vesper.http.put(url, body, options?)
await vesper.http.patch(url, body, options?)
await vesper.http.delete(url, options?)
```

### Options

All methods accept an optional `options` object:

```js
const options = {
    headers: {
        "Authorization": "Bearer token123",
        "Content-Type": "application/json",
    },
    timeout: 30,   // seconds (default: 30)
}

const response = await vesper.http.get("https://api.example.com/data", options)
```

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
        import json
        resp = self.http.get(
            f"{self.base}/users/{username}",
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        resp.raise_for_status()
        return json.loads(resp.text)
```

`HttpClient` is an httpx `Client` instance configured for sync use. For async services, use `httpx.AsyncClient` directly.

---

## IPC command names

| Command | Method |
|---|---|
| `http:get` | GET |
| `http:post` | POST |
| `http:put` | PUT |
| `http:patch` | PATCH |
| `http:delete` | DELETE |

All accept `{ url, body?, headers?, timeout? }`.

---

## Response format

All HTTP commands return:

```json
{
    "status": 200,
    "headers": { "content-type": "application/json", ... },
    "body": "<response body as string>"
}
```

Non-2xx status codes do **not** reject the Promise — the `status` field lets you handle errors:

```js
const response = await vesper.http.get("https://api.example.com/data")
if (response.status !== 200) {
    console.error("HTTP error:", response.status, response.body)
    return
}
const data = JSON.parse(response.body)
```

---

## Authentication headers

Pass auth headers in options:

```js
const headers = { "Authorization": `Bearer ${token}` }

const response = await vesper.http.get("/api/protected", { headers })
```

Or set default headers in a Python wrapper command:

```python
API_KEY = "..."

@app.command
def api_get(path: str) -> dict:
    import json
    from vesper_http import HttpClient
    # Get the global HttpClient instance
    from vesper.core.module import Container
    client = Container._global.get(HttpClient)
    resp = client.get(f"https://api.example.com{path}",
                      headers={"X-API-Key": API_KEY})
    return {"status": resp.status_code, "data": json.loads(resp.text)}
```
