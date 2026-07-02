# vesper-keychain

OS keychain plugin for Vesper. Stores secrets securely using the native OS credential store via [keyring](https://keyring.readthedocs.io/en/latest/).

| Platform | Storage |
|---|---|
| Windows | Windows Credential Manager |
| macOS | macOS Keychain |
| Linux | Secret Service (GNOME Keyring, KWallet) |

---

## Install

```bash
pip install vesper-keychain
```

---

## Setup

```python
from vesper import App
from vesper_keychain import KeychainPlugin

app = App(
    title="My App",
    frontend="dist/index.html",
    plugins=[KeychainPlugin(service="my-app")],
)
```

`service` is the keychain service name that groups your app's credentials. Use your app's name.

---

## JavaScript API

Add the SDK:

```toml
[plugins]
keychain = "vesper-keychain"
```

```bash
vesper sync-sdk
```

```html
<script src="vesper.js"></script>
<script src="vesper-keychain.js"></script>
```

### Methods

```js
// Store a secret
await vesper.keychain.set("api_token", "secret-value-here")

// Read a secret (returns null if not found)
const token = await vesper.keychain.get("api_token")

// Delete a secret
await vesper.keychain.delete("api_token")

// Check existence without reading the value
const exists = await vesper.keychain.has("api_token")   // true or false
```

---

## Python injection (Keychain)

```python
from vesper import Injectable
from vesper_keychain import Keychain

@Injectable()
class AuthService:
    def __init__(self, keychain: Keychain):
        self.keychain = keychain

    def save_token(self, token: str) -> None:
        self.keychain.set("access_token", token)

    def load_token(self) -> str | None:
        return self.keychain.get("access_token")

    def clear_token(self) -> None:
        self.keychain.delete("access_token")
```

---

## IPC command names

| Command | Args | Returns |
|---|---|---|
| `keychain:get` | `key: str` | `str \| null` |
| `keychain:set` | `key: str, value: str` | `true` |
| `keychain:delete` | `key: str` | `true` |
| `keychain:has` | `key: str` | `bool` |

---

## Common use cases

### API tokens

```js
// On login:
const token = await authenticate(username, password)
await vesper.keychain.set("api_token", token)

// On each request:
const token = await vesper.keychain.get("api_token")
const response = await vesper.http.get("/api/data", {
    headers: { "Authorization": `Bearer ${token}` }
})

// On logout:
await vesper.keychain.delete("api_token")
```

### Encryption keys

```python
@Injectable()
class CryptoService:
    def __init__(self, keychain: Keychain):
        self.keychain = keychain

    def get_or_create_key(self) -> bytes:
        import base64, secrets
        stored = self.keychain.get("encryption_key")
        if stored:
            return base64.b64decode(stored)
        # Generate a new key on first run
        key = secrets.token_bytes(32)
        self.keychain.set("encryption_key", base64.b64encode(key).decode())
        return key
```

---

## Linux notes

On Linux, `keyring` uses the D-Bus Secret Service. This requires either GNOME Keyring or KWallet to be running. In headless environments (CI, Docker), use the `keyrings.alt` fallback:

```bash
pip install keyrings.alt
```

Or configure a specific keyring backend via the `PYTHON_KEYRING_BACKEND` environment variable.

---

## Comparison with vesper-store

| | vesper-store | vesper-keychain |
|---|---|---|
| Storage | JSON file | OS credential store |
| Encryption | None | OS-managed |
| Use case | User preferences, app state | Passwords, tokens, secrets |
| Visible to user | Yes (editable file) | Via OS credentials UI |
