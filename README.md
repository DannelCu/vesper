# Vesper

> Build desktop apps with Python and web technologies.

Vesper is a Python-first desktop application framework. Write your backend in Python, your UI in HTML/CSS/JavaScript — Vesper connects them through a typed IPC bridge rendered in the system's native WebView.

**Inspired by Tauri. Built for Python developers.**

```python
# app.py
from vesper import App

app = App(title="My App", frontend="frontend/index.html")

@app.command
def greet(name: str) -> str:
    return f"Hello, {name}!"

if __name__ == "__main__":
    app.run()
```

```html
<!-- frontend/index.html -->
<button onclick="sayHello()">Greet</button>
<p id="output"></p>
<script src="vesper.js"></script>
<script>
async function sayHello() {
    const msg = await vesper.invoke("greet", { name: "World" })
    document.getElementById("output").textContent = msg
}
</script>
```

That is a complete, runnable desktop app. No Rust. No Node.js server. No boilerplate.

---

## Why Vesper?

If you know Python, Vesper is the fastest path to a native desktop app with a modern UI.

|  | Electron | Tauri | **Vesper** |
|---|---|---|---|
| Backend language | JavaScript / Node.js | Rust | **Python** |
| WebView | Bundled Chromium | System WebView | System WebView |
| Approximate binary size | ~150 MB | ~10 MB | ~15 MB |
| Learning curve | Medium | High (Rust required) | **Low** |
| Python ecosystem access | ❌ | ❌ | **✅** |

Use any Python library — pandas, SQLAlchemy, PyMongo, OpenCV, scikit-learn — directly in your backend. No bridges or serialization workarounds needed.

---

## Features

**IPC & Architecture**
- Bidirectional IPC — call Python from JS, push events from Python to the frontend
- Runtime argument validation — missing or unexpected args return a typed error before the command runs
- Async support — `async def` commands and middleware work natively
- NestJS-inspired module system — `@Module`, `@Controller`, `@Injectable`, dependency injection container
- Guards — per-command or per-controller access control, sync or async
- Middleware — cross-cutting logic on every IPC call (logging, auth, rate-limiting)

**Windows & UI**
- Multi-window — secondary windows sharing the same IPC registry
- Native menu bar — top-level menus, submenus, separators
- System tray — icon with context menu
- Splash screen — frameless loading overlay, auto-dismissed when the app is ready
- Window controls — minimize, maximize, restore, fullscreen, resize, move from Python or JS
- Screen info — list connected monitors with dimensions and position

**System Integration**
- Native file dialogs — open, save, folder picker, plus message/confirm/ask
- Native notifications — no extra dependencies (PowerShell, osascript, notify-send)
- Clipboard — read and write text and images
- Shell integration — open URLs in the default browser, reveal files in the file manager
- Filesystem API — read, write, exists, list directory from JS
- Deep linking — handle `myapp://` protocol URLs via `@app.on("deeplink")`, at startup or while running
- Single instance — a second launch forwards its arguments to the running app
- Window state — remember size and position, with disconnected-monitor handling
- Autostart — launch at login on all three platforms
- Power management — keep the system awake during long operations
- System trash — `fs.trash()` instead of a permanent delete
- OS info — platform, version, machine architecture

**Developer Workflow**
- Hot-reload dev server — Python restarts on backend changes, browser refreshes on frontend changes
- Framework templates — vanilla, React, Vue, Svelte (Vite-based)
- TypeScript definitions — `vesper sync-types` generates `.d.ts` from registered Python commands
- Module scaffolding — `vesper g module users` generates the full module structure
- Doctor — `vesper doctor` diagnoses environment and project issues
- Packaging — PyInstaller (default) or Nuitka native binary
- Code signing — macOS codesign + notarization, Windows signtool / osslsigncode
- Auto-updates — manifest-based self-update with download progress events

---

## Plugin Ecosystem

Plugins are separate packages installed with pip. They register IPC commands and injectable services automatically — no manual wiring required.

```python
from vesper import App
from vesper_db import DatabasePlugin, Base, DbSession
from vesper_store import StorePlugin

app = App(
    plugins=[
        DatabasePlugin(url="sqlite:///app.db"),
        StorePlugin(app_name="my-app"),
    ],
    root_module=AppModule,
)
```

Services receive plugin types via dependency injection:

```python
from vesper import Injectable
from vesper_db import DbSession

@Injectable()
class UserService:
    def __init__(self, db: DbSession):
        self.db = db  # injected automatically
```

| Plugin | What it adds | Injectable type |
|---|---|---|
| `vesper-store` | Persistent JSON key-value store | — |
| `vesper-db` | SQLAlchemy ORM integration | `DbSession` |
| `vesper-http` | HTTP client proxy (solves CORS) | `HttpClient` |
| `vesper-keychain` | OS keychain (Credential Manager / Keychain / Secret Service) | `Keychain` |
| `vesper-mongodb` | MongoDB via PyMongo | `MongoDatabase` |
| `vesper-shortcuts` | Global keyboard shortcuts (active even when unfocused) | — |
| `vesper-theme` | OS dark/light mode detection and change events | — |

---

## Requirements

| Dependency | Version | Required for |
|---|---|---|
| Python | 3.10+ | Always |
| pip | any | Always |
| System WebView | see below | Always |
| Node.js | 18+ | React / Vue / Svelte templates only |

Vesper renders in the OS WebView instead of bundling a browser, so that runtime comes from the system rather than from pip:

| Platform | WebView runtime |
|---|---|
| macOS | Built in — nothing to install |
| Windows | [Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/) (preinstalled on Windows 11) |
| Linux | GTK + WebKit2GTK — `sudo apt install python3-gi gir1.2-webkit2-4.1 libwebkit2gtk-4.1-0` |

On Linux, create virtual environments with `--system-site-packages` so the venv can see the GTK bindings, which pip cannot install. Full details in [Getting Started](docs/getting-started.md#system-webview); run `vesper doctor` to verify your setup.

---

## Installation

```bash
pip install vesper
```

With system tray support:

```bash
pip install "vesper[tray]"
```

Installing plugins:

```bash
pip install vesper-store vesper-db vesper-http vesper-keychain vesper-mongodb
pip install vesper-shortcuts vesper-theme
```

---

## Create a Project

**Interactive wizard** (recommended for first-time users):

```bash
vesper init app
cd my-app
vesper dev
```

**With flags** (for experienced users):

```bash
vesper init app --name "my-app" --template react --styles tailwind --pm pnpm
cd my-app
pnpm install
vesper dev
```

---

## Project Structures

**Vanilla** (no Node.js required):

```
my-app/
├── app.py            ← Python backend
├── vesper.toml       ← project config
└── frontend/
    ├── index.html
    └── vesper.js     ← IPC bridge (auto-generated)
```

**React / Vue / Svelte** (Vite-based):

```
my-app/
├── app.py
├── vesper.toml
├── package.json
├── vite.config.js
├── public/
│   └── vesper.js     ← IPC bridge (served as static asset)
└── src/
    └── App.jsx       ← (or .vue / .svelte)
```

**Module-based** (for larger apps):

```
my-app/
├── app.py
├── vesper.toml
└── modules/
    ├── app_module.py
    └── users/
        ├── users_module.py
        ├── users_controller.py
        └── users_service.py
```

---

## Documentation

| Guide | Description |
|---|---|
| [Getting Started](docs/getting-started.md) | Install, create, run, and build your first app |
| [CLI Reference](docs/cli.md) | All CLI commands with flags and examples |
| [Project Config](docs/project-config.md) | `vesper.toml` keys, sections, and defaults |
| [IPC](docs/ipc.md) | How the Python ↔ JavaScript bridge works |
| [Module System & DI](docs/module-system.md) | `@Module`, `@Controller`, `@Injectable`, container |
| [Guards](docs/guards.md) | Command-level access control |
| [Middleware](docs/middleware.md) | Cross-cutting IPC logic |
| [Events](docs/events.md) | Pushing events from Python to the frontend |
| [Multi-Window](docs/multiwindow.md) | Secondary windows, `WindowHandle` |
| [Native Dialogs](docs/dialogs.md) | File open, save, folder picker |
| [Notifications](docs/notifications.md) | Native desktop notifications |
| [System Tray](docs/tray.md) | Tray icon and context menu |
| [Menu Bar](docs/menu.md) | Native top-level application menu |
| [Shell Integration](docs/shell.md) | Open URLs, reveal files |
| [Clipboard](docs/clipboard.md) | Read and write the system clipboard |
| [Window Controls](docs/window-controls.md) | Minimize, maximize, resize, screen info |
| [Splash Screen](docs/splash.md) | Loading overlay before the app is ready |
| [Deep Linking](docs/deeplink.md) | Handle custom `myapp://` protocol URLs |
| [Single Instance](docs/single-instance.md) | One running copy, with argv forwarding |
| [Window State](docs/window-state.md) | Remember size and position across restarts |
| [Autostart](docs/autostart.md) | Launch the app at login |
| [Power Management](docs/power.md) | Keep the machine awake during long work |
| [Production Lockdown](docs/security-lockdown.md) | Disable browser behaviours in production |
| [Taskbar & Badges](docs/badge.md) | Progress on the taskbar, counts on the dock |
| [Filesystem API](docs/filesystem.md) | Read, write, list files from JS |
| [File Transfers](docs/file-transfers.md) | Sending binary data across the IPC boundary |
| [Auto-Updates](docs/auto-updates.md) | Self-updating apps via a manifest |
| [Code Signing](docs/code-signing.md) | macOS and Windows code signing |
| [Plugins](docs/plugins.md) | Using plugins and building your own |
| [OS & Theme](docs/os-theme.md) | Platform info and dark/light mode |

**Recipes** — complete code examples for common patterns not built into the framework:

| Recipe | Description |
|---|---|
| [Authentication with Roles](docs/recipes/auth.md) | Session auth, role-based guards, localStorage persistence |
| [Context Menus](docs/recipes/context-menus.md) | Native-looking right-click menus in HTML/CSS |
| [Saving Files (drag-out alternative)](docs/recipes/drag-out.md) | Export generated content to disk |
| [State Between Windows](docs/recipes/state-between-windows.md) | Share and sync state across multiple windows |
| [IPC Logging Middleware](docs/recipes/logging-middleware.md) | Log and time every IPC call during development |
| [User Preferences](docs/recipes/user-preferences.md) | Persistent settings panel with vesper-store |
| [Dark / Light Mode Theming](docs/recipes/theming.md) | System theme detection with CSS variables |
| [Real-Time Data Push](docs/recipes/real-time.md) | Stream live data from Python to the frontend |

---

## Examples

A complete runnable app lives in [examples/hello](examples/hello) — two files covering IPC, the scoped filesystem API, native dialogs and notifications:

```bash
cd examples/hello
vesper dev
```

---

## Contributing

Setup instructions for working on the framework itself — per-platform prerequisites, editable installs, and test conventions — are in [CONTRIBUTING.md](CONTRIBUTING.md).

Deliberate limitations and deferred work are tracked in [KNOWN-ISSUES.md](KNOWN-ISSUES.md).

---

## License

MIT © DannelCu
