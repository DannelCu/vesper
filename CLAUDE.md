# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Vesper

Vesper is a Python-first desktop application framework inspired by Tauri. It lets developers build desktop apps using Python for backend logic and any web technology (HTML/CSS/JS) for the UI, rendered via native system WebViews (powered by PyWebView).

## Setup

```bash
# Install in editable mode with all dependencies
pip install -e .
```

Requires Python 3.10+. PyWebView is the only runtime dependency. Optional extras:

```bash
pip install -e ".[tray]"   # system tray support (pystray + Pillow)
```

## Common Commands

```bash
# Run the framework's own tests
python -m pytest tests/

# Scaffold a new project — interactive wizard (no flags)
vesper init app

# Scaffold with flags (experienced users)
vesper init app --name "my-app" --template react --styles tailwind --bundler pyinstaller --pm pnpm

# Development workflow
vesper dev          # dev mode: vanilla serves frontend/ via HTTP + hot reload; frameworks start Vite + PyWebView
vesper build        # production build: npm run build (frameworks) or bundle/minify JS (vanilla) → dist/
vesper run          # run from dist/ after vesper build

# Packaging
vesper package      # create native executable — reads bundler from vesper.toml

# Project utilities
vesper sync-sdk     # copy vesper.js into frontend/ (vanilla) or public/ (frameworks)
vesper sync-types   # generate TypeScript definitions from registered Python commands → vesper.d.ts
vesper generate module|controller|service <name>   # scaffold a module (alias: vesper g)
vesper doctor       # diagnose environment and project issues
vesper info         # show installed versions and project info
vesper clean        # remove dist/, package/, .pyinstaller/, __pycache__, etc.
vesper version      # show Vesper version
```

## Project config — `vesper.toml`

Every project scaffolded by `vesper init` has a `vesper.toml` at its root. All CLI commands that need project context read it. Format is minimal TOML:

```toml
[project]
name = "my-app"
template = "react"         # vanilla | react | vue | svelte
styles = "tailwind"        # none | bootstrap | tailwind
bundler = "pyinstaller"    # pyinstaller | nuitka
package_manager = "pnpm"   # npm | pnpm | yarn
```

`read_vesper_toml(project_dir)` in `commands/utils.py` parses it into a flat `dict[str, str]`. If `vesper.toml` is absent, commands fall back to sensible defaults (vanilla template, pyinstaller bundler, npm). `get_project_package_manager(project_dir)` reads `package_manager` from the toml; if absent, auto-detects from lock files (`pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, else npm).

## Project structures

**Vanilla** (`--template vanilla`):
```
my-app/
├── app.py
├── vesper.toml
└── frontend/
    ├── index.html
    └── vesper.js
```

**Framework** (`--template react|vue|svelte`) — Vite-based:
```
my-app/
├── app.py
├── vesper.toml
├── package.json
├── vite.config.js
├── index.html          ← Vite entry (references /vesper.js and /src/main.*)
├── public/
│   └── vesper.js       ← SDK served as static asset by Vite
└── src/
    ├── main.jsx / main.js
    └── App.jsx / App.vue / App.svelte
```

After `vesper build`, both templates produce `dist/`. After `vesper package`, both produce `package/<app-name>[.exe]`.

**Module-based project** (optional, any template):
```
my-app/
├── app.py                         ← App(root_module=AppModule)
├── vesper.toml
├── modules/
│   ├── app_module.py              ← root @Module
│   └── users/
│       ├── __init__.py
│       ├── users_service.py
│       ├── users_controller.py
│       └── users_module.py
└── frontend/  (or src/ for frameworks)
```

## Architecture

The framework has two distinct layers: the **core runtime** (used by app developers) and the **CLI** (used in a terminal).

### Core Runtime (`vesper/core/`)

The data flow for every IPC call: `JavaScript invoke() → Window.API.invoke() → IPC.handle() → guard chain → middleware chain → CommandRegistry.get() → Python function → response`

- **`core/app.py` — `App`**: The single public entry point for app developers. Instantiates `CommandRegistry`, `Window`, and `IPC`. Provides `@app.command` (three forms: bare, string alias, `name=` kwarg), `@app.middleware`, `@app.on(event)`, `app.emit()`, `app.notify()`, `app.tray()`, `app.register_module()`, and `app.register_window()`. Accepts `root_module=` kwarg to auto-register a `@Module` tree at construction. Registers built-in commands at construction: `vesper:dialog:open/save/folder`, `vesper:notify`, `vesper:fs:read/write/exists/list`.
- **`core/registry.py` — `CommandRegistry`**: A `dict[str, Callable]` of registered commands. Raises `CommandAlreadyRegisteredError` on duplicate registration and `CommandNotFoundError` on lookup miss.
- **`core/ipc.py` — `IPC`**: Validates incoming message dicts (`{id, command, args}`), validates args against the command signature before execution (missing required args or unexpected keys → `ValidationError`), runs the guard chain, middleware chain, resolves the command, executes it (sync or async), and returns `{id, ok, result}` or `{id, ok, error}`. Runs a dedicated `asyncio` event loop on a background daemon thread; async commands and async middleware dispatch via `asyncio.run_coroutine_threadsafe`. In `debug=True` mode it appends a traceback to error responses. Shares `App._middleware` list by reference so middleware registered after construction is visible.
- **`core/window.py` — `Window` + `WindowHandle`**: Wraps PyWebView. `Window.create()` checks `VESPER_DEV_URL` env var first (dev mode, skips file validation); otherwise validates `config.frontend` exists on disk. Accepts `secondary_windows: list[WindowHandle]` — each is created hidden and attached to the shared IPC. `Window.emit()` dispatches a `CustomEvent("vesper:<name>", {detail: payload})` to the frontend via `evaluate_js`. `Window.open_dialog/save_dialog/pick_folder()` wrap `webview.create_file_dialog`. Call `Window.create()` then `Window.show()` to start the event loop. `WindowHandle` is returned by `app.register_window()` and exposes `show()`, `hide()`, `close()`, `emit()`.
- **`core/config.py` — `WindowConfig`**: A `@dataclass(slots=True)` that validates window parameters at construction. Validates `frontend` ends in `.html` but does **not** check file existence — that check is deferred to `Window.create()`.
- **`core/guard.py` — `guard`**: Decorator that attaches guard functions to a command via `__vesper_guards__`. Stacking multiple `@guard` decorators prepends (outermost runs first). Guards can be async.
- **`core/module.py` — Module system**: Provides `@Module`, `@Controller`, `@Injectable`, `@command`, and `Container`. `@Controller` now accepts `guards=[]`. See Module System and Guards sections below.
- **`core/tray.py` — `Tray` + `TrayMenuItem`**: System tray icon with a context menu. Started by `App.run()` before `webview.start()` and stopped in a `finally` block. Requires `vesper[tray]` (pystray + Pillow). `TrayMenuItem(label, action)` is the menu item dataclass; `None` in the menu list inserts a separator.
- **`core/notify.py` — `send(title, body)`**: Fire-and-forget native desktop notifications via a background daemon thread. Platform dispatch: PowerShell `ShowBalloonTip` on Windows, `osascript` on macOS, `notify-send` on Linux. No extra dependencies.
- **`core/fs.py` — filesystem helpers**: `read(path, encoding)`, `write(path, content, encoding)`, `exists(path)`, `list_dir(path)` — registered as `vesper:fs:*` built-in IPC commands. `write` creates parent directories automatically. `list_dir` returns `[{name, path, is_dir}]` sorted dirs-first.

### Module System (`core/module.py`)

Inspired by NestJS. Organizes code into self-contained feature modules following SOLID principles:

- **`@Injectable()`**: Marks a class as a DI provider (service).
- **`@Controller(prefix="", guards=[])`**: Marks a class whose `@command` methods become IPC endpoints under `"<prefix>.<name>"`. Guards passed here run before any method-level guards.
- **`@command`**: Marks a method on a controller as an IPC command. Supports bare, string alias, and `name=` forms — same as `@app.command`.
- **`@Module(controllers, providers, imports)`**: Defines a module. `imports` recursively registers other modules.
- **`Container`**: Minimal IoC container. Resolves provider singletons by inspecting `__init__` type annotations via `inspect.signature()`. Only resolves params whose annotation is a concrete `type`; skips primitives and unannotated params.

`App.register_module(module_cls)` wires the module tree:
1. Recurses into `meta["imports"]`
2. Creates a `Container` for `meta["providers"]`
3. For each controller, resolves it through the container, then registers every `@command` method as `"prefix.name"` in the IPC registry.

### JavaScript SDK (`vesper/sdk/vesper.js`)

A small IIFE shipped inside the Python package. Exposes:
- `window.vesper.invoke(command, args)` — waits for `pywebviewready`, calls `pywebview.api.invoke(JSON.stringify(request))`, resolves/rejects on `response.ok`.
- `window.vesper.on(event, handler)` — subscribes to `vesper:<event>` CustomEvents dispatched by `app.emit()`. Returns an unsubscribe function.
- `window.vesper.dialog.open(options)` — native file-picker dialog. Options: `multiple`, `filters`, `directory`.
- `window.vesper.dialog.save(options)` — native save-file dialog. Options: `filename`, `filters`, `directory`.
- `window.vesper.dialog.pickFolder(options)` — native folder-picker dialog. Options: `directory`, `multiple`.
- `window.vesper.notify(title, body)` — send a native desktop notification (delegates to `vesper:notify`).
- `window.vesper.fs.read(path, encoding?)` — read file → string.
- `window.vesper.fs.write(path, content, encoding?)` — write string to file.
- `window.vesper.fs.exists(path)` — check path existence → boolean.
- `window.vesper.fs.list(path)` — list directory → `[{name, path, is_dir}]`.

For vanilla projects the SDK lives in `frontend/`; for framework projects it lives in `public/` and Vite copies it to `dist/` on build.

### CLI (`vesper/cli.py`, `vesper/commands/`)

Each CLI subcommand lives in its own file under `vesper/commands/` and follows the pattern: `add_<name>_parser(subparsers)` + `handle_<name>(args) -> bool`. `cli.py` builds the parser and iterates handlers in order. Shared utilities (`read_vesper_toml`, `get_project_package_manager`, `pm_add`, `pm_add_dev`, `pm_run`, `pm_dlx`, `check_node_modules`, `find_entrypoint`, `APP_ENTRYPOINTS`, `FRAMEWORK_TEMPLATES`) live in `commands/utils.py`.

- **`init`**: Wizard mode when no flags given; direct mode with all flags optional (`--name`, `--template`, `--styles`, `--bundler`, `--package-manager`/`--pm`). Templates: `vanilla` (static `frontend/`), `react`/`vue`/`svelte` (Vite-based `src/` + `public/`). Styles integrated into `package.json` for frameworks, installed via the chosen PM for vanilla. Generates `vesper.toml` (includes `package_manager`). Post-init prints platform-appropriate next steps; includes C compiler instructions if Nuitka is selected. All generated `app.py` files wrap `app.run()` with `if __name__ == "__main__":`.
- **`run`**: Finds `app.py`, `main.py`, or `vesper_app.py` in `cwd`, executes via `runpy.run_path`. Checks `dist/` exists for framework apps.
- **`dev`**: Reads `vesper.toml`. Vanilla: starts an internal HTTP server on a random port that serves `frontend/` and injects a polling script for hot reload; watches `*.py` for restart and `frontend/*.html/css/js` for browser reload. Frameworks: resolves PM, starts Vite subprocess, parses port from stdout (strips ANSI codes), polls HTTP until server responds, sets `VESPER_DEV_URL=http://localhost:{port}`, then runs `app.py`. Kills Vite/HTTP server on exit via `finally` block.
- **`build`**: Resolves PM via `get_project_package_manager`. Frameworks: `check_node_modules` → `<pm> run build` (Vite → `dist/`). Vanilla: copies `frontend/` → `dist/`, bundles user `.js` files (excluding `vesper.js`) with esbuild via `<pm> dlx` into `dist/bundle.js`, updates `dist/index.html` to reference `bundle.js`.
- **`package`**: Reads `bundler` from `vesper.toml`. Determines frontend data source (`dist/` for frameworks, `frontend/` for vanilla). PyInstaller path: `--windowed --onefile`, adds PyWebView hidden imports per platform, outputs to `package/`, work files to `.pyinstaller/`. Nuitka path: `python -m nuitka --standalone --onefile`, `--windows-disable-console` / `--macos-disable-console` per platform, outputs to `package/`.
- **`sync-sdk`**: Copies the bundled `vesper.js` into `frontend/` (vanilla) or `public/` (frameworks).
- **`sync-types`**: Imports the app entrypoint (requires `if __name__ == "__main__":` guard on `app.run()`), finds the `App` instance, inspects `app.registry._commands`, generates a `.d.ts` file. Output: `frontend/vesper.d.ts` (vanilla) or `src/types/vesper.d.ts` (frameworks). The file is always regenerated — never edit it manually. Uses a 5-second timeout to detect unguarded `app.run()` calls. Python type hints are optional; missing annotations fall back to `unknown`.
- **`generate` / `g`**: Scaffolds `modules/<name>/` with `__init__.py`, `<name>_service.py`, `<name>_controller.py`, `<name>_module.py`. `vesper g module users` / `vesper g controller users` / `vesper g service users`. On first module, auto-creates `modules/app_module.py`; on subsequent modules, prints the import line to add manually.
- **`doctor`**: Checks Python version, Vesper install, PyWebView install, Node.js version (≥18), package manager availability (from `vesper.toml` or defaults to npm), `vesper.toml` schema validation (valid keys and values), entrypoint presence, frontend structure, SDK script tag in `index.html`.
- **`clean`**: Removes `dist/`, `build/`, `package/`, `.pyinstaller/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `*.pyc`.

### Guards (`vesper/core/guard.py`)

Command-level access control that runs **before** middleware and the command itself. A guard returning `False` raises `ForbiddenError` and short-circuits the call.

```python
from vesper import guard

def auth_guard(command: str, args: dict) -> bool:
    return session.is_valid()

@app.command
@guard(auth_guard)
def delete_user(user_id: int): ...
```

- `@guard(*fns)` attaches guard functions to `fn.__vesper_guards__`. Stacking decorators prepends — outermost guard runs first.
- Guards can be `async def`.
- Controller-level guards: `@Controller("users", guards=[auth_guard])` — apply to every command in the controller. They run before method-level guards.
- `IPC` reads `registry._guards[command_name]` and runs each in order before executing middleware.

### Multi-window (`vesper/core/window.py`)

Secondary windows share the main app's IPC registry. They start hidden and are shown on demand from a command.

```python
settings = app.register_window(
    title="Settings",
    width=600,
    height=400,
    frontend="dist/settings.html",
)

@app.command
def open_settings():
    settings.show()
```

- `App.register_window(**kwargs) -> WindowHandle` — accepts same params as `App.__init__` (minus `frontend` which is required). Appends to `App._secondary_windows`.
- `App.run()` passes `secondary_windows` to `Window.create()`, which creates each PyWebView window hidden and calls `handle._attach(win)`.
- `WindowHandle` exposes: `show()`, `hide()`, `close()`, `emit(event, payload)`. All are no-ops before `app.run()`.
- `WindowHandle.emit()` dispatches `vesper:<event>` to that specific window only (not the main window).
- In dev mode, secondary windows also use `VESPER_DEV_URL`: the URL is constructed as `{VESPER_DEV_URL}/{filename}` (basename of `cfg.frontend`), skipping the disk existence check.

### Native File Dialogs

Built-in commands registered automatically at `vesper:dialog:open/save/folder`. Callable from JS via `vesper.dialog.*` or from Python via `app.ipc.handle(...)`.

```js
// JS
const paths = await vesper.dialog.open({ multiple: true, filters: [{ name: "PDF", extensions: ["pdf"] }] })
const dest  = await vesper.dialog.save({ filename: "report.pdf" })
const dirs  = await vesper.dialog.pickFolder()
```

Filters format: `[{ "name": "Images", "extensions": ["png", "jpg"] }]` → PyWebView tuple `("Images (*.png;*.jpg)",)` via `_to_file_types()`. The `vesper:` prefix makes them impossible to clash with user-registered commands (Python identifiers cannot contain `:`). `vesper sync-types` filters them from the generated `.d.ts`.

### Native Notifications (`vesper/core/notify.py`)

`app.notify(title, body)` sends a fire-and-forget native notification from Python. `vesper.notify(title, body)` does the same from JS. Both delegate to the `vesper:notify` built-in command.

- Windows: PowerShell `ShowBalloonTip` via `System.Windows.Forms.NotifyIcon`
- macOS: `osascript display notification`
- Linux: `notify-send`

Special characters are escaped per-platform. Runs in a background daemon thread — never blocks.

### System Tray (`vesper/core/tray.py`)

`app.tray(icon, menu, title="")` configures a system tray icon. Must be called before `app.run()`. Requires `pip install vesper[tray]` (pystray + Pillow).

```python
from vesper import App, TrayMenuItem

app = App()
app.tray(
    icon="assets/icon.png",
    menu=[
        TrayMenuItem("Open", lambda: window.show()),
        None,  # separator
        TrayMenuItem("Quit", lambda: app.quit()),
    ],
    title="My App",
)
```

- `TrayMenuItem(label, action)` — a menu item. `action` is a zero-arg callable.
- `None` in the menu list inserts a separator.
- The tray starts in a background thread via `pystray.Icon.run_detached()` before `webview.start()`.
- The tray is stopped in a `finally` block in `App.run()` so it always cleans up on exit.

### Built-in Filesystem API (`vesper/core/fs.py`)

Registered automatically as `vesper:fs:*` built-in IPC commands. Callable from JS via `vesper.fs.*`.

```js
const text = await vesper.fs.read("/path/to/file.txt")
await vesper.fs.write("/path/to/out.txt", "hello")
const ok = await vesper.fs.exists("/path/to/file")
const entries = await vesper.fs.list("/path/to/dir")
// entries: [{name, path, is_dir}, ...]
```

```python
# Also callable from Python directly
from vesper.core import fs
content = fs.read("data.txt")
fs.write("out.txt", "hello")
fs.exists("data.txt")  # → True/False
fs.list_dir(".")        # → [{name, path, is_dir}]
```

`fs.write` creates parent directories automatically. `fs.list_dir` sorts directories before files. `vesper sync-types` filters all `vesper:` built-ins from the generated `.d.ts`.

### Public API (`vesper/__init__.py`)

`App`, `Module`, `Controller`, `Injectable`, `command`, `guard`, `TrayMenuItem`, `WindowHandle`, `VesperError`, `CommandNotFoundError`, `CommandAlreadyRegisteredError`, `ForbiddenError` are exported. Internal modules are not part of the public API.

## Key Design Constraints

- **Explicit commands only**: Frontend can only call functions registered via `@app.command` or `@command` on a controller. Nothing is auto-exposed.
- **Arg validation before execution**: `IPC.handle()` validates args against the Python function signature (missing required params, unexpected kwargs) before running guards or the command. Returns `{ok: false, error: {type: "ValidationError"}}` on failure. Commands with `**kwargs` skip the unexpected-arg check.
- **Serializable arguments only**: Args crossing the IPC boundary must be JSON-compatible. No sockets, file handles, or arbitrary Python objects. See File Transfers below.
- **PyWebView is an implementation detail**: `core/window.py` is the only file that imports `webview`. The rest of the framework must not depend on it directly.
- **Frontend validation is lazy**: `WindowConfig` validates format at construction; `Window.create()` validates file existence at run time. This allows framework `app.py` files to declare `frontend="dist/index.html"` before the build step.
- **`VESPER_DEV_URL` is internal**: The env var is set by `vesper dev` and read by `Window.create()`. It is not part of the public API.
- **`app.run()` must be guarded**: All `app.py` templates wrap `app.run()` in `if __name__ == "__main__":`. This is required for `vesper sync-types` to safely import the entrypoint without launching the GUI.
- **Async IPC**: `async def` commands are supported natively. `IPC` runs a dedicated asyncio event loop on a background daemon thread; async commands dispatch via `asyncio.run_coroutine_threadsafe`. Sync commands still run on the calling thread.
- **Middleware shares the list by reference**: `App._middleware` is passed by reference to `IPC._middleware` so middleware registered after `IPC` construction is automatically visible.
- **Dual bundler support**: PyInstaller (default, simpler) and Nuitka (native binary, requires C compiler). The choice is persisted in `vesper.toml` at `vesper init` time and read by `vesper package`.
- **Package manager abstraction**: npm, pnpm, and yarn are all supported. All PM-aware operations go through `pm_add`, `pm_add_dev`, `pm_run`, `pm_dlx` in `commands/utils.py` — never call `npm`/`pnpm`/`yarn` directly elsewhere. `yarn add -D` uses `--dev` instead of `-D`.

## File Transfers

IPC payloads are JSON-serialized — binary data must be Base64-encoded before crossing the boundary.

**Python → Frontend** (e.g. sending a generated PDF to the browser):
```python
import base64

@app.command
def get_report() -> dict:
    pdf_bytes = generate_pdf()  # returns bytes
    return {
        "name": "report.pdf",
        "data": base64.b64encode(pdf_bytes).decode(),
    }
```
```js
const { name, data } = await vesper.invoke('get_report')
const bytes = Uint8Array.from(atob(data), c => c.charCodeAt(0))
const blob = new Blob([bytes], { type: 'application/pdf' })
const url = URL.createObjectURL(blob)
```

**Frontend → Python** (e.g. uploading a file from an `<input type="file">`):
```js
const file = document.querySelector('input[type="file"]').files[0]
const reader = new FileReader()
reader.onload = async (e) => {
  const b64 = e.target.result.split(',')[1]   // strip "data:...;base64," prefix
  await vesper.invoke('save_file', { name: file.name, data: b64 })
}
reader.readAsDataURL(file)
```
```python
import base64

@app.command
def save_file(name: str, data: str) -> str:
    dest = Path.home() / "Downloads" / name
    dest.write_bytes(base64.b64decode(data))
    return str(dest)
```

**Practical limits**: Base64 adds ~33% size overhead. Files over ~10 MB may cause noticeable lag. For large files, have Python write to disk and pass the filesystem path as a string instead of the file content.

## Developer workflow per template

**Vanilla:**
```
vesper init app --template vanilla
cd my-app
vesper dev          # HTTP dev server with hot reload on frontend/
vesper build        # bundles JS → dist/
vesper run          # runs from dist/ (production check)
vesper package      # native executable → package/
```

**React / Vue / Svelte:**
```
vesper init app --template react --pm pnpm
cd my-app && pnpm install        # or npm install / yarn install
vesper dev          # Vite dev server + PyWebView at localhost
vesper build        # <pm> run build → dist/
vesper run          # runs from dist/
vesper package      # native executable → package/
```

**Module-based (any template):**
```
vesper g module users       # scaffold modules/users/
vesper g module products    # scaffold modules/products/ — add to app_module.py manually
vesper sync-types           # regenerate src/types/vesper.d.ts after adding commands
```


## Roadmap — Implementation Status

### Completed

| Feature | Files | Notes |
|---|---|---|
| Core runtime (App, Registry, IPC, Window, Config) | `core/` | Foundation — M1 |
| Module system (NestJS-style DI) | `core/module.py` | `@Module`, `@Controller`, `@Injectable`, `@command`, `Container` |
| CLI — init, run, dev, build, package, clean | `commands/` | Full workflow for vanilla + frameworks |
| CLI — generate, sync-sdk, doctor, info, version | `commands/` | Scaffolding + tooling |
| JavaScript SDK | `sdk/vesper.js` | `invoke`, `on`, `dialog.*`, `notify`, `fs.*` |
| `vesper sync-types` | `commands/sync_types.py` | Generates `.d.ts` from registered commands; filters `vesper:` built-ins |
| Guards (`@guard`, `@Controller(guards=[])`) | `core/guard.py`, `core/registry.py` | Run before middleware; sync + async; controller + method level |
| Native file dialogs | `core/window.py`, `sdk/vesper.js` | `open/save/pickFolder`; registered as `vesper:dialog:*` built-ins |
| Multi-window (`WindowHandle`) | `core/window.py`, `core/app.py` | Secondary windows hidden at start, shown on demand via handle |
| Secondary windows in dev mode | `core/window.py` | `VESPER_DEV_URL` applied per-window; disk check skipped in dev |
| Runtime arg validation | `core/ipc.py` | Missing/unexpected args → `ValidationError` before execution |
| `vesper doctor` improvements | `commands/doctor.py` | Node.js ≥18, PM availability, vesper.toml schema checks |
| System tray | `core/tray.py`, `core/app.py` | `app.tray(icon, menu)`, `TrayMenuItem`; requires `vesper[tray]` |
| Native notifications | `core/notify.py`, `core/app.py`, `sdk/vesper.js` | `app.notify()` + `vesper.notify()`; no extra deps |
| Built-in filesystem API | `core/fs.py`, `core/app.py`, `sdk/vesper.js` | `vesper:fs:read/write/exists/list` built-ins + `vesper.fs.*` in JS |

### Pending — Long-term only

- **Plugin ecosystem (M4)** — allow third-party packages to register commands, middleware, and lifecycle hooks into Vesper at install time. Needs a plugin loader and a stable plugin API surface.
- **Auto-updates** — check for new app versions and prompt the user to update. Needs a server-side manifest and a download + replace flow per platform.
- **Code signing** — sign the output of `vesper package` for macOS Gatekeeper and Windows SmartScreen.

---

# *For Claude Code Guidelines*

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
