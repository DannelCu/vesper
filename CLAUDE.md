# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Vesper

Vesper is a Python-first desktop application framework inspired by Tauri. It lets developers build desktop apps using Python for backend logic and any web technology (HTML/CSS/JS) for the UI, rendered via native system WebViews (powered by PyWebView).

## Setup

```bash
# Install in editable mode with all dependencies
pip install -e .
```

Requires Python 3.10+. PyWebView is the only runtime dependency.

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

The data flow for every IPC call: `JavaScript invoke() → Window.API.invoke() → IPC.handle() → middleware chain → CommandRegistry.get() → Python function → response`

- **`core/app.py` — `App`**: The single public entry point for app developers. Instantiates `CommandRegistry`, `Window`, and `IPC`. Provides `@app.command` (three forms: bare, string alias, `name=` kwarg), `@app.middleware`, `@app.on(event)`, `app.emit()`, and `app.register_module()`. Accepts `root_module=` kwarg to auto-register a `@Module` tree at construction.
- **`core/registry.py` — `CommandRegistry`**: A `dict[str, Callable]` of registered commands. Raises `CommandAlreadyRegisteredError` on duplicate registration and `CommandNotFoundError` on lookup miss.
- **`core/ipc.py` — `IPC`**: Validates incoming message dicts (`{id, command, args}`), runs the middleware chain, resolves the command, executes it (sync or async), and returns `{id, ok, result}` or `{id, ok, error}`. Runs a dedicated `asyncio` event loop on a background daemon thread; async commands and async middleware dispatch via `asyncio.run_coroutine_threadsafe`. In `debug=True` mode it appends a traceback to error responses. Shares `App._middleware` list by reference so middleware registered after construction is visible.
- **`core/window.py` — `Window`**: Wraps PyWebView. `Window.create()` checks `VESPER_DEV_URL` env var first (dev mode, skips file validation); otherwise validates `config.frontend` exists on disk. `Window.emit()` dispatches a `CustomEvent("vesper:<name>", {detail: payload})` to the frontend via `evaluate_js`. Call `Window.create()` then `Window.show()` to start the event loop.
- **`core/config.py` — `WindowConfig`**: A `@dataclass(slots=True)` that validates window parameters at construction. Validates `frontend` ends in `.html` but does **not** check file existence — that check is deferred to `Window.create()`.
- **`core/module.py` — Module system**: Provides `@Module`, `@Controller`, `@Injectable`, `@command`, and `Container`. See Module System section below.

### Module System (`core/module.py`)

Inspired by NestJS. Organizes code into self-contained feature modules following SOLID principles:

- **`@Injectable()`**: Marks a class as a DI provider (service).
- **`@Controller(prefix="")`**: Marks a class whose `@command` methods become IPC endpoints under `"<prefix>.<name>"`.
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
- **`doctor`**: Checks Python version, Vesper install, PyWebView install, entrypoint presence, frontend structure, SDK script tag in `index.html`.
- **`clean`**: Removes `dist/`, `build/`, `package/`, `.pyinstaller/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `*.pyc`.

### Public API (`vesper/__init__.py`)

`App`, `Module`, `Controller`, `Injectable`, `command`, `VesperError`, `CommandNotFoundError`, `CommandAlreadyRegisteredError` are exported. Internal modules are not part of the public API.

## Key Design Constraints

- **Explicit commands only**: Frontend can only call functions registered via `@app.command` or `@command` on a controller. Nothing is auto-exposed.
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
