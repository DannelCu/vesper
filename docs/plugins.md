# Plugins

Plugins extend Vesper with additional capabilities. Each plugin is a separate pip package that registers IPC commands, injectable services, and optionally a JavaScript SDK.

---

## Using a plugin

Install the plugin:

```bash
pip install vesper-db
```

Pass it to `App(plugins=[...])`:

```python
from vesper import App
from vesper_db import DatabasePlugin

app = App(
    plugins=[DatabasePlugin(url="sqlite:///app.db")],
    root_module=AppModule,
)
```

Plugins always register before the module tree — global DI providers from plugins are available when the container resolves your modules.

---

## Official plugins

### vesper-store

Persistent JSON key-value store. No injectable type — all access goes through IPC commands.

```bash
pip install vesper-store
```

```python
from vesper_store import StorePlugin

app = App(plugins=[StorePlugin(app_name="my-app")])
```

JS API: `vesper.store.get(key)`, `set(key, value)`, `delete(key)`, `has(key)`, `clear()`, `keys()`.

See [vesper-store README](../plugins/vesper-store/README.md).

### vesper-db

SQLAlchemy ORM integration. Provides `DbSession` as an injectable type.

```bash
pip install vesper-db
```

```python
from vesper_db import DatabasePlugin, Base, DbSession

app = App(plugins=[DatabasePlugin(url="sqlite:///app.db")])
```

See [vesper-db README](../plugins/vesper-db/README.md).

### vesper-http

HTTP client proxy that solves CORS issues. Provides `HttpClient` as an injectable type.

```bash
pip install vesper-http
```

```python
from vesper_http import HttpPlugin

app = App(plugins=[HttpPlugin()])
```

JS API: `vesper.http.get(url, options?)`, `post(url, body, options?)`, `put(...)`, `patch(...)`, `delete(...)`.

See [vesper-http README](../plugins/vesper-http/README.md).

### vesper-keychain

OS keychain access (Windows Credential Manager, macOS Keychain, Linux Secret Service). Provides `Keychain` as an injectable type.

```bash
pip install vesper-keychain
```

```python
from vesper_keychain import KeychainPlugin

app = App(plugins=[KeychainPlugin(service="my-app")])
```

JS API: `vesper.keychain.get(key)`, `set(key, value)`, `delete(key)`, `has(key)`.

See [vesper-keychain README](../plugins/vesper-keychain/README.md).

### vesper-mongodb

MongoDB via PyMongo. Provides `MongoDatabase` as an injectable type.

```bash
pip install vesper-mongodb
```

```python
from vesper_mongodb import MongoPlugin

app = App(plugins=[MongoPlugin(uri="mongodb://localhost:27017", database="mydb")])
```

JS API: `vesper.mongo.find(collection, filter?)`, `findOne(...)`, `insertOne(...)`, `insertMany(...)`, `updateOne(...)`, `updateMany(...)`, `deleteOne(...)`, `deleteMany(...)`, `count(...)`.

See [vesper-mongodb README](../plugins/vesper-mongodb/README.md).

### vesper-shortcuts

Global keyboard shortcuts via pynput. Active even when the app window is not focused.

```bash
pip install vesper-shortcuts
```

```python
from vesper_shortcuts import ShortcutsPlugin

app = App(plugins=[ShortcutsPlugin()])
```

JS API: `vesper.shortcuts.register(accelerator, callback)`, `unregister(accelerator)`, `unregisterAll()`.

See [vesper-shortcuts README](../plugins/vesper-shortcuts/README.md).

### vesper-theme

OS dark/light mode detection and change events via darkdetect.

```bash
pip install vesper-theme
```

```python
from vesper_theme import ThemePlugin

app = App(plugins=[ThemePlugin(watch=True)])
```

JS API: `vesper.theme.get()`, `vesper.theme.onChange(callback)`.

See [vesper-theme README](../plugins/vesper-theme/README.md).

### vesper-watch

File watching via watchdog (inotify / FSEvents / ReadDirectoryChangesW). Watched paths honour the app's `fs_scope`; change events stream to the frontend with debouncing.

```bash
pip install vesper-watch
```

```python
from vesper_watch import WatchPlugin

app = App(plugins=[WatchPlugin()])
```

JS API: `vesper.watch.watch(path, { recursive, debounce, onChange })`, `unwatch(id)`, `onChange(callback)`.

See [vesper-watch README](../plugins/vesper-watch/README.md).

### vesper-notify

Rich notifications via desktop-notifier: click callbacks, action buttons, custom icon and sound. The core's minimal `vesper.notify()` stays as the dependency-free fallback; `vesper.capabilities().notifications` reflects which backend is active. On macOS, callbacks require a signed bundle — see the README.

```bash
pip install vesper-notify
```

```python
from vesper_notify import NotifyPlugin

app = App(plugins=[NotifyPlugin(app_name="My App")])
```

JS API: `vesper.notifyRich.send(title, { body, buttons, icon, sound, onClick, onAction })`.

See [vesper-notify README](../plugins/vesper-notify/README.md).

### vesper-crash

Crash reporting via sentry-sdk: exceptions in IPC commands, unhandled Python exceptions, and frontend JS errors. Privacy-first (no PII, no breadcrumbs, no automatic integrations) and a silent no-op without a DSN. Reporting never alters the error the frontend receives.

```bash
pip install vesper-crash
```

```python
from vesper_crash import CrashPlugin

app = App(plugins=[CrashPlugin(dsn=os.environ.get("SENTRY_DSN"))])
```

JS API: the SDK installs `window.onerror`/`unhandledrejection` bridges; `vesper.crash.report(error)` for manual reports.

See [vesper-crash README](../plugins/vesper-crash/README.md).

### vesper-screenshot

Screen capture via mss: full screen, per monitor, or a region — as a PNG data URL or written to a scope-validated path. Wayland is not supported (session fact, reported by `vesper doctor`); macOS needs the Screen Recording permission, granted manually.

```bash
pip install vesper-screenshot
```

```python
from vesper_screenshot import ScreenshotPlugin

app = App(plugins=[ScreenshotPlugin()])
```

JS API: `vesper.screenshot.capture({ monitor, region })`, `captureToFile(dest, options)`, `monitors()`.

See [vesper-screenshot README](../plugins/vesper-screenshot/README.md).

### vesper-serial

Serial port access via pyserial: list devices, open several ports with ids, stream incoming data as events, write, close. Linux users need the `dialout` group — see the README.

```bash
pip install vesper-serial
```

```python
from vesper_serial import SerialPlugin

app = App(plugins=[SerialPlugin()])
```

JS API: `vesper.serial.listPorts()`, `open(port, { baudrate, onData, onClose })`, `write(id, data)`, `close(id)`.

See [vesper-serial README](../plugins/vesper-serial/README.md).

### vesper-sysinfo

System information via psutil: CPU, memory, disks, network counters, battery, uptime — snapshots on demand or a tick stream for dashboards, stopped cleanly at app close.

```bash
pip install vesper-sysinfo
```

```python
from vesper_sysinfo import SysinfoPlugin

app = App(plugins=[SysinfoPlugin()])
```

JS API: `vesper.sysinfo.snapshot()`, `subscribe({ interval, onTick })`, `unsubscribe()`.

See [vesper-sysinfo README](../plugins/vesper-sysinfo/README.md).

---

## Syncing JS SDKs

After installing plugins, copy their JavaScript SDK files into your project:

```bash
vesper sync-sdk
```

Add the plugins to `vesper.toml` so `sync-sdk` knows what to copy:

```toml
[plugins]
store = "vesper-store"
db    = "vesper-db"
http  = "vesper-http"
```

The JS files end up in `frontend/` (vanilla) or `public/` (frameworks), alongside `vesper.js`.

---

## Building your own plugin

A plugin is a class that extends `VesperPlugin`:

```python
from vesper import VesperPlugin
from pathlib import Path

class MyPlugin(VesperPlugin):
    def register(self, app) -> None:
        @app.command("myplugin:hello")
        def hello(name: str) -> str:
            return f"Hello from MyPlugin, {name}!"

    def sdk_path(self) -> Path | None:
        return Path(__file__).parent / "sdk" / "my-plugin.js"

Plugin = MyPlugin   # convention: export Plugin alias
```

### register(app)

Called during `App.__init__` (before `root_module`). Use it to:
- Register IPC commands with `@app.command` or `app.registry.register(name, fn)`
- Register middleware with `@app.middleware`
- Add teardown hooks with `app.add_teardown(fn)`
- Register global DI providers with `Container.register_global(type_, instance)`

### sdk_path()

Return the path to your JS SDK file, or `None` if the plugin has no JS interface. `vesper sync-sdk` copies this file into the project's frontend directory.

### Global DI providers

To make a type injectable across all modules:

```python
from vesper.core.module import Container

class MyPlugin(VesperPlugin):
    def register(self, app) -> None:
        instance = MyService()
        Container.register_global(MyService, instance)
```

Any `@Injectable` or `@Controller` with `def __init__(self, svc: MyService)` will receive this instance.

### Teardown hooks

Teardown runs in a `finally` block after every IPC call — useful for releasing per-call resources:

```python
class MyPlugin(VesperPlugin):
    def register(self, app) -> None:
        def cleanup():
            self.session.remove()
        app.add_teardown(cleanup)
```

Exceptions in teardown are silently swallowed to avoid masking the original response.
