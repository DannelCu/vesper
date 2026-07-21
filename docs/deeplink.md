# Deep Linking

Deep linking lets your app handle custom URL schemes — for example, `myapp://action?param=value`. When a user clicks such a link in a browser or another app, your Vesper app launches and receives the URL.

---

## Registering the protocol

Before your app can receive deep links, the OS must be told that your app handles the scheme. Run:

```bash
vesper register-protocol myapp
```

**Windows**: writes the registry key `HKEY_CURRENT_USER\SOFTWARE\Classes\myapp` pointing to your app executable.

**macOS**: prints the `CFBundleURLTypes` plist snippet to add to `Info.plist` — macOS requires this to be set at build time, so it cannot be registered at runtime.

**Linux**: writes a `.desktop` file to `~/.local/share/applications/` and runs `xdg-mime default` to register the association.

---

## Handling the URL in your app

When the OS launches your app with a deep link URL, the URL appears in `sys.argv`. Vesper detects this automatically at construction time and fires the `deeplink` event when the app is ready:

```python
from vesper import App

app = App(title="My App", frontend="dist/index.html")

@app.on("deeplink")
def on_deeplink(url: str):
    print(f"Received deep link: {url}")
    # url = "myapp://action?param=value"
    app.emit("deeplink", {"url": url})

if __name__ == "__main__":
    app.run()
```

The `deeplink` callback receives the full URL string as its first argument.

In JavaScript, listen for the `deeplink` event:

```js
vesper.on("deeplink", ({ url }) => {
    const parsed = new URL(url)
    const action = parsed.pathname.slice(2)   // "myapp://action" → "action"
    const param  = parsed.searchParams.get("param")
    handleDeepLink(action, param)
})
```

---

## URL parsing

Python's standard library handles URL parsing:

```python
from urllib.parse import urlparse, parse_qs

@app.on("deeplink")
def on_deeplink(url: str):
    parsed = urlparse(url)
    # parsed.scheme  → "myapp"
    # parsed.netloc  → "action"
    # parsed.query   → "param=value"
    params = parse_qs(parsed.query)
    app.emit("deeplink", {
        "action": parsed.netloc,
        "params": {k: v[0] for k, v in params.items()},
    })
```

---

## How it works

Vesper inspects `sys.argv[1:]` at `App.__init__` time. Any argument that does not start with a web scheme (`http://`, `https://`, `ftp://`, `ftps://`) and contains `://` is treated as a deep link URL. The URL is stored internally and fired as a `deeplink` event via a `loaded` hook when the window is ready.

### Links arriving while the app is already running

The above covers a *cold start*. If the app is already open when the user clicks a
link, the OS launches a second copy of it — and by default that second copy just
starts its own window.

Enable [single-instance mode](single-instance.md) to route it to the running app
instead:

```python
app = App(title="My App", single_instance=True)
```

The second process hands its `sys.argv` to the first and exits. The first fires the
same `deeplink` hooks, so your handler does not need to distinguish the two cases:

```python
@app.on("deeplink")
def handle(url: str):
    # Fires whether the app was launched with this URL or already running.
    open_document(url)
```

A handler that raises is logged and the remaining handlers still run — this path
executes on the single-instance listener thread, where an escaping exception would
otherwise stop the app accepting any further links.

---

## Testing without protocol registration

You can test deep linking by passing the URL directly as a command-line argument:

```bash
python app.py myapp://action?param=test
```

---

## macOS specifics

On macOS, app launching via URL scheme is handled by the OS — the URL is passed via an Apple Event, not `sys.argv`. PyInstaller-packaged apps need additional configuration in `Info.plist`. The `vesper register-protocol` command prints the exact plist snippet to add.

For development testing on macOS, the `sys.argv` approach still works when launching from the terminal.
