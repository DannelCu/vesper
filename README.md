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

## How Vesper Compares

The one-line version: Vesper is to PyWebView what Tauri is to a bare webview, or what NestJS is to Express — a framework layer on top of a primitive. PyWebView opens a native window, renders your HTML, and lets Python and JavaScript call each other. That's genuinely all it promises, and it does it well — Vesper is built directly on it (`pywebview` is one of exactly two required dependencies, see [pyproject.toml](pyproject.toml)) and adds what turns a window into an application: architecture, a security boundary, a full lifecycle, and a path to a signed binary.

**Application architecture.** The strongest, most checkable claim here: Vesper has a NestJS-shaped module system — `@Module`, `@Controller`, `@Injectable`, and a DI container that resolves constructor types automatically ([vesper/core/module.py](vesper/core/module.py)). IPC calls pass through guards and middleware before reaching a command, and each phase reports its own error type: a guard rejecting a call (`ForbiddenError`) is distinguishable from a guard raising (`GuardError`), a middleware raising (`MiddlewareError`), and the command itself failing — on top of upfront argument validation ([vesper/core/ipc.py](vesper/core/ipc.py), [docs/module-system.md](docs/module-system.md)). No other Python project in this space has this; it's what keeps a backend from becoming one 3,000-line file as an app grows.

**Native integration depth.** Tray, native menu bar, splash screen, multi-window (secondary windows sharing one IPC registry), native dialogs, frameless/transparent windows, notifications, clipboard (text, images, files), deep linking, single-instance enforcement, remembered window state, autostart, power/keep-awake, taskbar badges, semantic positioning, a production-grade localhost server, an auto-updater with SHA-256 verification, and a CLI covering `init` through `package`, `sign`, and `doctor`. Each is a real file under [vesper/core/](vesper/core) or [vesper/commands/](vesper/commands) — [docs/optional-features.md](docs/optional-features.md) is the per-backend matrix of what each needs and how it degrades without it.

**Security model.** Every filesystem call the frontend can make goes through `FsScope`, which confines paths to declared roots — checking both endpoints of a `copy()`/`move()`, so a crafted destination can't write outside the sandbox ([vesper/core/fs_scope.py](vesper/core/fs_scope.py)). Every process the frontend can spawn goes through `ShellScope`, an allowlist of executables and argument patterns, deny-by-default: no scope configured means no process starts ([vesper/core/process.py](vesper/core/process.py)). The dev and production localhost servers are confined to their root directory and gated by a per-session token in the URL ([vesper/core/static_server.py](vesper/core/static_server.py)). If you know Tauri, it's the same instinct — don't trust the webview with the filesystem or the shell by default — expressed as two small, auditable Python classes instead of a capability-file ACL.

**Degradation you can query.** `capabilities.probe()` reports what's actually available on the running machine and drives three things: `vesper doctor` gives an actionable diagnosis at install time, `vesper.capabilities()` lets the frontend adapt its own UI at runtime, and every optional-backend feature fails soft instead of raising across the IPC boundary ([vesper/core/capabilities.py](vesper/core/capabilities.py), [vesper/commands/doctor.py](vesper/commands/doctor.py)). This is more explicit than what Tauri or Electron expose out of the box — it's the one place Vesper doesn't just catch up to the non-Python frameworks, it's ahead of them.

**Minimalism as a rule.** Two required dependencies: `pywebview` and `packaging`. Everything else — tray support, trash, and all 13 official plugins — is opt-in. What keeps it that way is a four-level decision tree in [CONTRIBUTING.md](CONTRIBUTING.md#where-a-feature-lives): a feature lives in the core only if it needs zero new dependencies; otherwise it's a plugin, a documented recipe, or — genuinely last resort — a `KNOWN-ISSUES.md` entry.

| | PyWebView | Eel | NiceGUI | Flet | **Vesper** | Tauri / Electron |
|---|---|---|---|---|---|---|
| Frontend | your HTML/JS | your HTML/JS | framework-generated UI | framework-generated UI | **your HTML/JS** | your HTML/JS |
| App architecture (modules, DI, guards, middleware) | ✗ | ✗ | partial (FastAPI DI underneath) | ✗ | **✓** | plugin systems, not this DI shape |
| IPC with arg validation & typed error phases | ✗ | ✗ | n/a (no separate frontend) | n/a (no separate frontend) | **✓** | partial (typed commands, different model) |
| Filesystem / process sandboxing | ✗ | ✗ | ✗ | ✗ | **✓** | ✓ (capability/ACL-based) |
| Native lifecycle (tray, menu, deep link, single-instance…) | partial (menu + dialogs only) | ✗ | partial (native mode wraps PyWebView) | partial | **✓** | ✓ |
| Packaging + code signing, integrated | ✗ | ✗ | partial (packaging only) | partial (build tooling, no signing) | **✓** | ✓ |
| Auto-updates | ✗ | ✗ | ✗ | ✗ | **✓ (SHA-256 verified)** | ✓ |
| Capability introspection / declared degradation | ✗ | ✗ | ✗ | ✗ | **✓** | ✗ (fails at call time) |

*The Vesper and Tauri/Electron columns reflect this repository; the other four reflect public documentation, not code executed here — read "partial" as "some, unverified extent," not a precise claim.*

**A different problem, on purpose.** NiceGUI and Flet aren't really in the same lane as Vesper, Eel, or PyWebView — they solve the opposite problem. Both let you write only Python and never touch HTML, CSS, or JavaScript; the framework generates the UI. Vesper does the opposite on purpose: you bring React, Vue, Svelte, or vanilla JS and use it for real. Neither approach is more correct — if you never want to leave Python, NiceGUI or Flet is the right tool, not a lesser version of this one.

**Where this actually stands.** Vesper is `0.1.0`, pre-1.0, with one maintainer, not yet used in production anywhere but its own examples. What backs the claims above: `pytest -q` currently runs 1,600 tests (13 skipped) — check it yourself rather than trust the number, it'll be stale the moment the suite grows; CI runs that suite across 3 operating systems and 5 Python versions on every push ([.github/workflows/ci.yml](.github/workflows/ci.yml)); and [KNOWN-ISSUES.md](KNOWN-ISSUES.md) names what Vesper genuinely can't do yet and why — native file drag-out, native context menus, custom protocol handlers, programmatic printing, all blocked on PyWebView not exposing the underlying engine API. A framework that names its limits is easier to trust than one that only lists what works.

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
- Frameless & transparent windows — custom titlebars with drag regions, min size, macOS vibrancy, Windows 11 Mica
- Semantic positioning — `vesper.window.position("top-right", { screen: "cursor" })` across monitors
- Screen info — list connected monitors with dimensions and position

**System Integration**
- Native file dialogs — open, save, folder picker, plus message/confirm/ask
- Native notifications — no extra dependencies (PowerShell, osascript, notify-send)
- Clipboard — read and write text, images, and files (interoperates with the OS file manager)
- Shell integration — open URLs in the default browser, reveal files in the file manager
- Filesystem API — read, write, copy, move, stat, binary I/O from JS, sandboxed by `fs_scope`
- Process execution — run allowlisted external binaries with streamed output (`shell_scope`)
- File downloads — stream to disk with progress events and SHA-256 verification
- Deep linking — handle `myapp://` protocol URLs via `@app.on("deeplink")`, at startup or while running
- Single instance — a second launch forwards its arguments to the running app
- Window state — remember size and position, with disconnected-monitor handling
- Autostart — launch at login on all three platforms
- Power management — keep the system awake during long operations
- System trash — `fs.trash()` instead of a permanent delete
- OS info — platform, version, machine architecture

**Developer Workflow**
- Hot-reload dev server — Python restarts on backend changes, browser refreshes on frontend changes
- DevTools — the WebView inspector, on by default in `vesper dev`, never in production
- Production localhost serving — opt-in `serve_frontend=True` for ES modules and SPA routing in packaged apps
- Framework templates — vanilla, React, Vue, Svelte (Vite-based)
- TypeScript definitions — `vesper sync-types` generates `.d.ts` from registered Python commands
- Module scaffolding — `vesper g module users` generates the full module structure
- Doctor — `vesper doctor` diagnoses environment and project issues
- Packaging — PyInstaller (default) or Nuitka native binary, plus `--installer` for .dmg / .deb
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
| `vesper-watch` | File watching with change events (watchdog) | — |
| `vesper-notify` | Rich notifications — click callbacks, buttons, icon, sound | — |
| `vesper-crash` | Crash reporting to Sentry, privacy-first | — |
| `vesper-screenshot` | Screen capture — full, per monitor, or region (mss) | — |
| `vesper-serial` | Serial ports — list, stream, write (pyserial) | — |
| `vesper-sysinfo` | CPU, memory, disks, network, battery, uptime (psutil) | — |

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

On Linux, create virtual environments with `--system-site-packages` so the venv can see the GTK bindings, which pip cannot install. Full details in [Platform Requirements](docs/platform-requirements.md); run `vesper doctor` to verify your setup.

Everything beyond the WebView is optional and degrades to a no-op when absent — see [Optional Features](docs/optional-features.md) for the per-platform matrix.

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
pip install vesper-watch vesper-notify vesper-crash vesper-screenshot vesper-serial vesper-sysinfo
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
| [Platform Requirements](docs/platform-requirements.md) | The native WebView each OS needs, and how to install it |
| [Optional Features](docs/optional-features.md) | What each optional backend needs, and what happens without it |
| [CLI Reference](docs/cli.md) | All CLI commands with flags and examples |
| [Project Config](docs/project-config.md) | `vesper.toml` keys, sections, and defaults |
| [IPC](docs/ipc.md) | How the Python ↔ JavaScript bridge works |
| [Module System & DI](docs/module-system.md) | `@Module`, `@Controller`, `@Injectable`, container |
| [Guards](docs/guards.md) | Command-level access control |
| [Middleware](docs/middleware.md) | Cross-cutting IPC logic |
| [Events](docs/events.md) | Pushing events from Python to the frontend |
| [Multi-Window](docs/multiwindow.md) | Secondary windows, `WindowHandle` |
| [Frameless Windows](docs/frameless.md) | Custom titlebars, drag regions, transparency, Mica |
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
| [Filesystem API](docs/filesystem.md) | Read, write, copy, move, stat, binary I/O from JS |
| [File Transfers](docs/file-transfers.md) | Sending binary data across the IPC boundary |
| [Process Execution](docs/process.md) | Run external binaries behind a declarative allowlist |
| [Network Downloads](docs/network.md) | Stream files to disk with progress and checksums |
| [Auto-Updates](docs/auto-updates.md) | Self-updating apps via a manifest |
| [Code Signing](docs/code-signing.md) | macOS and Windows code signing |
| [Plugins](docs/plugins.md) | Using plugins and building your own |
| [OS & Theme](docs/os-theme.md) | Platform info and dark/light mode |

**Recipes** — complete code examples for common patterns not built into the framework:

| Recipe | Description |
|---|---|
| [Authentication with Roles](docs/recipes/auth.md) | Session auth, role-based guards, localStorage persistence |
| [Custom Titlebar](docs/recipes/custom-titlebar.md) | Complete frameless titlebar: drag, controls, platform quirks |
| [Menubar App](docs/recipes/menubar-app.md) | Tray-summoned window positioned on the active monitor |
| [Printing](docs/recipes/printing.md) | window.print(), print stylesheets, PDF per platform |
| [Asking the User for Text](docs/recipes/text-input.md) | An in-page `<dialog>` prompt — there is no native text dialog |
| [Camera & Microphone](docs/recipes/media-capture.md) | Making getUserMedia work, per platform, with honest limits |
| [Playing Video](docs/recipes/video-playback.md) | Why `.avi` refuses to play in a WebView, and transcoding on demand |
| [Windows Installer & AppImage](docs/recipes/windows-installer.md) | NSIS script and AppImage walkthrough for packaged apps |
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
