# vesper-store

Persistent key-value store for Vesper apps. Data is saved to a JSON file in the OS application data directory and survives app restarts.

---

## Install

```bash
pip install vesper-store
```

---

## Setup

```python
from vesper import App
from vesper_store import StorePlugin

app = App(
    title="My App",
    frontend="dist/index.html",
    plugins=[StorePlugin(app_name="my-app")],
)
```

`app_name` determines the directory where the JSON store file is saved:
- Windows: `%APPDATA%\my-app\store.json`
- macOS: `~/Library/Application Support/my-app/store.json`
- Linux: `~/.local/share/my-app/store.json`

---

## JavaScript API

Add the plugin SDK to your project:

```toml
# vesper.toml
[plugins]
store = "vesper-store"
```

```bash
vesper sync-sdk
```

```html
<script src="vesper.js"></script>
<script src="vesper-store.js"></script>
```

### Methods

```js
// Read a value (returns null if key does not exist)
const theme = await vesper.store.get("theme")

// Write a value (any JSON-serializable value)
await vesper.store.set("theme", "dark")
await vesper.store.set("window_size", { width: 1200, height: 800 })
await vesper.store.set("recent_files", ["a.txt", "b.txt"])

// Delete a key
await vesper.store.delete("theme")

// Check existence
const exists = await vesper.store.has("theme")   // true or false

// List all keys
const keys = await vesper.store.keys()   // ["theme", "window_size", ...]

// Clear the entire store
await vesper.store.clear()
```

---

## Python / IPC commands

The store is also accessible via IPC from Python tests or internal commands:

| Command | Args | Returns |
|---|---|---|
| `store:get` | `key: str` | value or `null` |
| `store:set` | `key: str, value: any` | `true` |
| `store:delete` | `key: str` | `true` |
| `store:has` | `key: str` | `bool` |
| `store:keys` | — | `list[str]` |
| `store:clear` | — | `true` |

---

## Storing complex values

Any JSON-serializable value can be stored: strings, numbers, booleans, lists, and dicts.

```js
await vesper.store.set("user", {
    name: "Alice",
    preferences: { theme: "dark", fontSize: 14 },
    lastLogin: new Date().toISOString(),
})

const user = await vesper.store.get("user")
// { name: "Alice", preferences: { ... }, lastLogin: "..." }
```

---

## Key namespacing

Use a prefix convention to avoid key collisions between features:

```js
await vesper.store.set("ui:sidebar_width", 240)
await vesper.store.set("ui:theme", "dark")
await vesper.store.set("user:name", "Alice")
await vesper.store.set("recent:files", [])
```

---

## Notes

- The JSON file is human-readable and can be edited manually (close the app first)
- No encryption — do not store secrets. Use `vesper-keychain` for sensitive data
- Concurrent writes are safe within a single app instance (all writes are synchronous and serialized through the IPC thread)
- For sensitive data, see [vesper-keychain](../vesper-keychain/README.md)
