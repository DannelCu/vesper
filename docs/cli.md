# CLI Reference

All Vesper commands are run via the `vesper` executable installed with `pip install vesper`.

---

## vesper init

Scaffold a new project.

```bash
vesper init app                                    # interactive wizard
vesper init app --name "my-app"                   # skip name prompt
vesper init app --template react --pm pnpm        # fully non-interactive
```

**Flags**

| Flag | Values | Default |
|---|---|---|
| `--name` | any string | prompted |
| `--template` | `vanilla`, `react`, `vue`, `svelte` | prompted |
| `--styles` | `none`, `bootstrap`, `tailwind` | prompted |
| `--bundler` | `pyinstaller`, `nuitka` | prompted |
| `--pm`, `--package-manager` | `npm`, `pnpm`, `yarn` | prompted |

When all flags are provided, no prompts appear. Missing flags are prompted interactively.

**Generated files**

Vanilla: `app.py`, `vesper.toml`, `frontend/index.html`, `frontend/vesper.js`

React/Vue/Svelte: `app.py`, `vesper.toml`, `package.json`, `vite.config.js`, `index.html`, `public/vesper.js`, `src/App.*`, `src/main.*`

---

## vesper dev

Start a development server with hot reload.

```bash
vesper dev
vesper dev --no-devtools    # keep the inspector closed for this session
```

**Flags**

| Flag | Default | Description |
|---|---|---|
| `--no-devtools` | off | Disable the WebView inspector for this session. |

**DevTools**

`vesper dev` opens the app with the native WebView inspector available on all three
platforms (right-click → Inspect, backed by `webview.start(debug=True)`). It is
wired through the `VESPER_DEVTOOLS` environment variable, which only `vesper dev`
sets — `vesper run` and packaged builds never expose the inspector.

Not to be confused with `App(debug=True)`, which is unrelated: that flag controls
how much detail IPC error responses carry, and works in any mode.

**Vanilla behavior**
- Starts an internal HTTP server on a random port serving `frontend/`
- Watches `*.py` — restarts the Python process on change
- Watches `frontend/*.html`, `*.css`, `*.js` — injects a polling script that triggers browser refresh

**Framework behavior** (react / vue / svelte)
- Resolves the package manager from `vesper.toml`
- Starts Vite, parses the port from its stdout
- Polls HTTP until Vite is ready
- Sets `VESPER_DEV_URL=http://localhost:{port}`
- Launches `app.py` — PyWebView loads from Vite

HMR (Hot Module Replacement) works normally for frameworks. Python process restarts on `.py` changes.

---

## vesper build

Build the frontend for production.

```bash
vesper build
```

**Vanilla**: copies `frontend/` to `dist/`, bundles user `.js` files (excluding `vesper.js`) into `dist/bundle.js` via esbuild, updates `dist/index.html` to reference `bundle.js`.

**Frameworks**: runs `<pm> run build` (Vite → `dist/`).

Always run `vesper build` before `vesper run` or `vesper package`.

---

## vesper run

Run the app from the production `dist/` directory.

```bash
vesper run
```

Finds `app.py`, `main.py`, or `vesper_app.py` in the current directory and executes it via `runpy`. For framework apps, checks that `dist/` exists first.

---

## vesper package

Package the app as a native executable.

```bash
vesper package
vesper package --installer    # also build a native installer where possible
```

Reads `bundler` from `vesper.toml`. Outputs to `package/<app-name>[.exe]`.

**`--installer`** builds a native installer from the packaged bundle:

| Platform | Produces | Tool used |
|---|---|---|
| macOS | `package/<name>-<version>.dmg` (drag-to-install, with `/Applications` link) | `hdiutil` (ships with macOS) |
| Debian/Ubuntu | `package/<name>_<version>_<arch>.deb` (menu entry, clean uninstall) | `dpkg-deb` (ships with dpkg) |
| Windows | Nothing — prints what is needed and where the recipe lives | NSIS is external tooling; see [the recipe](recipes/windows-installer.md) |

On macOS, if `[sign]` is configured in `vesper.toml` the `.app` bundle is signed (and notarized, if enabled) **before** the dmg is built. Metadata (version, description, maintainer, category, icon) comes from the `[installer]` section — see [Project Config](project-config.md).

**PyInstaller** (default)
- `--windowed --onefile`
- Adds PyWebView platform-specific hidden imports automatically
- Work files go to `.pyinstaller/`

**Nuitka**
- `--standalone --onefile`
- `--windows-disable-console` or `--macos-disable-console` per platform
- Requires a C compiler (`mingw-w64` on Windows, Xcode CLI tools on macOS, `gcc` on Linux)

---

## vesper sign

Sign the packaged binary after `vesper package`.

```bash
vesper sign                       # signs package/<app-name>[.exe]
vesper sign --path /custom/bin    # sign an arbitrary binary
```

Reads `[sign]` from `vesper.toml`. See [Code Signing](code-signing.md) for the full configuration reference.

---

## vesper sync-sdk

Copy the Vesper JS SDK into the project's frontend directory.

```bash
vesper sync-sdk
```

- Vanilla: copies `vesper.js` to `frontend/`
- Frameworks: copies `vesper.js` to `public/`

Also syncs JS SDK files from installed plugins. Reads the `[plugins]` section of `vesper.toml`, imports each listed package, calls `Plugin.sdk_path()`, and copies the JS file to the same directory. Prints a warning (does not fail) for plugins that are not installed.

---

## vesper sync-types

Generate TypeScript definitions from registered Python commands.

```bash
vesper sync-types
```

Imports the app entrypoint (requires the `if __name__ == "__main__":` guard around `app.run()`), finds the `App` instance, inspects the command registry, and generates a `.d.ts` file.

Output:
- Vanilla: `frontend/vesper.d.ts`
- Frameworks: `src/types/vesper.d.ts`

Built-in `vesper:*` commands are filtered from the output. Python type hints are used where present; parameters without annotations fall back to `unknown`.

Run this after adding or removing commands.

---

## vesper generate

Scaffold a module, controller, or service.

```bash
vesper generate module users       # full module: service + controller + module file
vesper generate controller users   # controller file only
vesper generate service users      # service file only

vesper g module users              # alias: vesper g
```

Generated files go to `modules/<name>/`. On the first module, `modules/app_module.py` is also created. On subsequent modules, the import line to add manually is printed to the terminal.

---

## vesper doctor

Diagnose environment and project issues.

```bash
vesper doctor
```

Checks:
- Python version (3.10+ required)
- Vesper install (importable)
- PyWebView install
- System WebView backend — resolves the backend pywebview will actually use (GTK/WebKit2, Cocoa/WKWebView, or WinForms/WebView2). PyWebView is pure Python, so installing it proves nothing about whether a usable native WebView exists; this check catches a missing GTK, PyObjC, or WebView2 runtime before it fails at `app.run()`. On Windows it also fails when pywebview silently degrades to the legacy MSHTML renderer.
- Node.js version (≥ 18, for framework templates)
- Package manager availability (from `vesper.toml` or defaults to npm)
- `vesper.toml` schema (valid keys and values)
- Entrypoint presence (`app.py`, `main.py`, or `vesper_app.py`)
- Frontend structure (`frontend/` for vanilla, `src/` for frameworks)
- SDK script tag in `index.html`

---

## vesper info

Print installed versions and project details.

```bash
vesper info
```

---

## vesper version

Print the installed Vesper version.

```bash
vesper version
```

---

## vesper clean

Remove all build artifacts.

```bash
vesper clean
```

Removes: `dist/`, `build/`, `package/`, `.pyinstaller/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `*.pyc`.

---

## vesper register-protocol

Register a custom URL scheme for deep linking.

```bash
vesper register-protocol myapp
```

- **Windows**: writes to the registry under `HKEY_CURRENT_USER\SOFTWARE\Classes\myapp`
- **macOS**: prints the `CFBundleURLTypes` plist snippet to add to `Info.plist`
- **Linux**: writes a `.desktop` file to `~/.local/share/applications/` and calls `xdg-mime default`

See [Deep Linking](deeplink.md) for the full workflow.
