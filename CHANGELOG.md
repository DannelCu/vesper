# Changelog

All notable changes to Vesper and its official plugins are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Vesper adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **`vesper doctor` — system WebView backend check.** Resolves the backend pywebview
  will actually use (GTK/WebKit2, Cocoa/WKWebView, WinForms/WebView2) by mirroring
  `webview.guilib` import order, honoring `PYWEBVIEW_GUI` and `KDE_FULL_SESSION`.
  pywebview is pure Python, so its presence never implied a usable native WebView —
  doctor previously reported all-green on machines where `app.run()` could not open a
  window. Failures print a platform-specific install command. On Windows, a silent
  fallback to the legacy MSHTML (IE11) renderer is now reported as a failure instead of
  surfacing later as broken CSS and JavaScript.
- **`CONTRIBUTING.md`** — development setup, per-platform WebView prerequisites, editable
  install of the framework and all seven plugins, test conventions, and repository layout.
- **Window smoke test (`scripts/smoke_window.py`)** — opens a real native window, has the
  frontend invoke a Python command over IPC, and verifies the returned value. The unit
  suite mocks PyWebView, so it passed on machines that could not open a window at all;
  this closes that gap. CI runs it on Linux, macOS, and Windows as a separate `smoke`
  job, headless under xvfb on Linux.

- **Optional-dependency detection (`vesper.core.capabilities`).** One source of truth
  for which optional backends exist on this machine, consumed by three places:
  `vesper doctor` prints an "Optional features" section with the exact install command
  for anything missing (as `[WARN]`, which does not affect its exit status); the
  frontend can call `vesper.capabilities()` to hide a control whose backend is absent
  instead of offering one that does nothing; and `App.run()` warns once at startup when
  a configured feature's backend is missing. Detection is `shutil.which` and
  `find_spec` only — no imports, no subprocesses, no new dependencies.
- **[Platform Requirements](docs/platform-requirements.md)** and
  **[Optional Features](docs/optional-features.md)** — the native WebView each OS
  needs, and the contract for what happens when an optional backend is absent.
- **Taskbar badges on Windows.** `badge.set_badge()` was a no-op there. Windows has no
  numeric badge, so the count is now rendered into an overlay icon with Pillow and
  applied via `ITaskbarList3::SetOverlayIcon`; `clear_badge()` / `set_badge(0)` pass a
  null icon to remove it. Pillow stays optional (`vesper[tray]`) — without it the badge
  returns `False` as before while progress keeps working. Counts above 99 draw as a
  dot, and the accessible description carries the real number.
- **System power events** — `App(power_events=True)` emits `power:suspend`,
  `power:resume`, `power:lock` and `power:unlock` to the frontend, listened to with
  `vesper.on("power:suspend", cb)`. Backed by NSWorkspace + distributed notifications
  on macOS, `WM_POWERBROADCAST` / `WTS_SESSION_CHANGE` on a message-only window on
  Windows, and systemd-logind + the desktop screensaver over D-Bus (jeepney) on Linux.
  Opt-in and best-effort: an absent optional dependency or a desktop that publishes
  nothing degrades to no events, never to an error. See [docs/power.md](docs/power.md)
  for the per-platform table.

### Fixed
- **`autostart.enable()` failed on Windows when no startup entry had ever been
  registered.** It used `winreg.OpenKey`, which cannot create a missing key, and
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` does not exist on a profile
  where nothing has registered a startup entry — including every fresh Windows
  install. `enable()` logged the error and returned `False`. Now uses `CreateKeyEx`,
  which opens the key or creates it. Found by converting the mocked Windows tests to
  a real registry round trip; a `MagicMock` `OpenKey` never raises, so the mocks
  could not have caught it.
- **PyWebView deprecation warning on every dialog.** `open_dialog`, `save_dialog` and
  `pick_folder` used `webview.OPEN_DIALOG` / `SAVE_DIALOG` / `FOLDER_DIALOG`, which
  PyWebView 5 deprecated in favour of the `FileDialog` enum and which log
  `[pywebview] OPEN_DIALOG is deprecated ...` on each call. The constants are now
  resolved once at import, preferring `FileDialog` and falling back to the old names
  so `pywebview>=4.0` installations keep working.
- **`app.quit()` / `vesper.quit()` could hang the process at exit.** The window was
  destroyed synchronously inside the IPC command handler, so PyWebView was left
  delivering that command's return value through `evaluate_js` to a WebView that no
  longer existed. That call never returns, and because PyWebView runs it on a
  non-daemon thread the interpreter could not shut down — the window closed but the
  process stayed alive, leaving a zombie behind for a packaged app. `App.quit()` now
  defers the teardown by `_QUIT_DELAY_SECONDS` so the reply lands first, and
  `vesper:app:quit` routes through it. `Window.quit()` is unchanged and still destroys
  synchronously for callers with no pending IPC reply. Reproduced at a 62% failure
  rate (5/8 runs) under Xvfb before the fix, 0/8 after.

### Changed
- **Docs — system WebView requirements.** `README.md` and `docs/getting-started.md` now
  document the OS WebView runtime as a first-class requirement, including the Linux
  `--system-site-packages` venv requirement (`python3-gi` is a distribution package that
  pip cannot install) and macOS framework-build caveats. `docs/getting-started.md` gains
  a troubleshooting table for the common startup failures.

### Planned
- GitHub Actions CI — Windows + macOS + Linux test matrix
- PyPI publish — `vesper` and all 7 plugins
- Example apps (`examples/`) — todo, file manager, data dashboard
- Window state persistence — remember size/position across restarts
- `vesper upgrade` CLI command
- `vesper-sqlite` plugin — sqlite3 stdlib wrapper without ORM
- `vesper-pdf` plugin — PDF generation via reportlab/weasyprint
- `vesper-excel` plugin — Excel/CSV export via openpyxl

---

## [0.1.0] - 2026-07-01

First complete release of the Vesper framework. Covers the full lifecycle from
scaffolding to packaging, signing, and auto-updating a desktop app.

### Added — Core Framework

- **`App`** — single entry point: `@app.command`, `@app.middleware`, `@app.on(event)`,
  `app.emit()`, `app.notify()`, `app.tray()`, `app.menu()`, `app.splash()`,
  `app.register_window()`, `app.register_module()`, `app.add_teardown()`, `app.quit()`
- **`IPC`** — bidirectional bridge between JS and Python. Validates args against the
  Python function signature (missing/unexpected args → `ValidationError`) before
  running guards or the command. Returns `{id, ok, result}` / `{id, ok, error}`.
  Async commands dispatched via `asyncio.run_coroutine_threadsafe` on a dedicated loop.
- **`CommandRegistry`** — `dict[str, Callable]` with `CommandAlreadyRegisteredError` on
  duplicate registration and `CommandNotFoundError` on miss.
- **`Window` / `WindowHandle`** — wraps PyWebView. `VESPER_DEV_URL` env var switches to
  HTTP dev server. Secondary windows start hidden; shown via `WindowHandle.show()`.
- **`WindowConfig`** — `@dataclass(slots=True)` that validates window parameters at
  construction. File existence check deferred to `Window.create()`.
- **Guards** (`@guard`) — per-command or per-controller access control. Stacking prepends
  (outermost first). Sync and async. `ForbiddenError` on rejection.
- **Middleware** (`@app.middleware`) — wraps every IPC call. Sync and async. Shared by
  reference so registration after `IPC` construction is visible.
- **Module system** — `@Module`, `@Controller(prefix, guards=[])`, `@Injectable()`,
  `@command`, `Container`. IoC container resolves singletons by `__init__` type hints.
  `Container.register_global()` for plugin-injected providers.
- **Multi-window** — `app.register_window()` returns `WindowHandle`. All windows share
  the IPC registry. Dev mode uses `{VESPER_DEV_URL}/{basename}` for secondary windows.
- **Lifecycle hooks** — `@app.on("loaded" | "closed" | "resize" | "deeplink")`
- **System tray** — `app.tray(icon, menu, title)`, `TrayMenuItem`. Requires `vesper[tray]`.
- **Native menu bar** — `app.menu(items)`, `MenuItem(label, action, submenu)`. Converted
  to PyWebView `Menu`/`MenuAction`/`MenuSeparator`.
- **Splash screen** — `app.splash(html, width, height)`. Frameless window dismissed on
  main window `loaded` event.
- **Window controls** — `minimize()`, `maximize()`, `restore()`, `toggle_fullscreen()`,
  `resize(w, h)`, `move(x, y)`, `list_screens()`. Exposed as `vesper:window:*` and
  `vesper:screen:list` IPC built-ins.
- **Native notifications** — `app.notify(title, body)`. PowerShell on Windows, osascript
  on macOS, notify-send on Linux. Fire-and-forget daemon thread.
- **Shell integration** — `vesper:shell:open_url` (webbrowser), `vesper:shell:reveal`
  (Explorer/Finder/xdg-open). Exposed as `vesper.shell.*` in JS.
- **Clipboard** — `vesper:clipboard:read/write`. PowerShell / pbpaste / xclip.
  Exposed as `vesper.clipboard.*` in JS.
- **OS info** — `vesper:os:info` returns `{platform, version, machine, python_version}`.
  Exposed as `vesper.os.info()` in JS.
- **Deep linking** — `sys.argv` inspection at `App.__init__`. Custom `deeplink` hook fires
  on `loaded`. `vesper register-protocol` CLI command for OS registration.
- **Built-in filesystem API** — `vesper:fs:read/write/exists/list`. `write` creates parent
  dirs automatically. `list` sorts dirs-first. Exposed as `vesper.fs.*` in JS.
- **Native file dialogs** — `vesper:dialog:open/save/folder`. Filter format:
  `[{name, extensions}]` converted to PyWebView tuples. Exposed as `vesper.dialog.*` in JS.
- **Auto-updates** — `App(update_url, version)`. Manifest JSON with per-platform URLs.
  `vesper:update:check/download/install`. Install: `os.execv` on POSIX, bat swap on Windows.
- **`VesperPlugin` ABC** — `register(app)`, `sdk_path()`. Plugins run before `root_module`.
  `add_teardown(fn)` for per-call cleanup (runs in `finally`).
- **`vesper.js` SDK** — `invoke`, `on`, `dialog.*`, `notify`, `fs.*`, `shell.*`,
  `clipboard.*`, `window.*`, `screen.list()`, `os.info()`, `quit()`, `drop.onFiles()`.

### Added — CLI

- `vesper init` — interactive wizard + direct flags. Templates: vanilla, react, vue, svelte.
  Styles: none, bootstrap, tailwind. Bundlers: pyinstaller, nuitka. PMs: npm, pnpm, yarn.
- `vesper dev` — vanilla: internal HTTP server + file watcher. Frameworks: Vite subprocess
  + `VESPER_DEV_URL` handoff.
- `vesper build` — vanilla: esbuild bundle via `<pm> dlx`. Frameworks: `<pm> run build`.
- `vesper run` — `runpy.run_path` on the app entrypoint.
- `vesper package` — PyInstaller (`--windowed --onefile`) or Nuitka (`--standalone --onefile`).
- `vesper sign` — macOS: `codesign` + optional `xcrun notarytool` notarization.
  Windows: `signtool.exe` or `osslsigncode` fallback. Config via `[sign]` in `vesper.toml`.
- `vesper generate` / `vesper g` — scaffold module/controller/service. Auto-creates
  `app_module.py` on first module.
- `vesper sync-sdk` — copies `vesper.js` and plugin JS SDKs to `frontend/` or `public/`.
- `vesper sync-types` — generates `vesper.d.ts` from registered commands. Filters `vesper:*`
  built-ins. 5-second timeout to detect unguarded `app.run()`.
- `vesper doctor` — checks Python, PyWebView, Node.js, PM, vesper.toml schema, entrypoint,
  frontend structure, SDK script tag.
- `vesper register-protocol` — registers custom URL scheme. Windows: registry. macOS: plist
  snippet. Linux: .desktop file + xdg-mime.
- `vesper info`, `vesper version`, `vesper clean`

### Added — Plugins

#### vesper-store 0.1.0
Persistent JSON key-value store. IPC: `store:get/set/delete/has/keys/clear`.
JS: `vesper.store.*`. Storage in OS app data dir.

#### vesper-db 0.1.0
SQLAlchemy ORM integration. `Base`, `DbSession` (injectable `scoped_session`),
`DatabasePlugin(url)`. `create_all()` at registration. `session.remove()` as teardown hook.
Supports SQLite (including `:memory:` with `StaticPool`), PostgreSQL, MySQL.

#### vesper-http 0.1.0
HTTP proxy via httpx. Solves CORS in WebView. `HttpClient` injectable. IPC:
`http:get/post/put/patch/delete`. JS: `vesper.http.*`. Response: `{status, headers, body}`.

#### vesper-keychain 0.1.0
OS keychain via keyring. `Keychain` injectable. IPC: `keychain:get/set/delete/has`.
JS: `vesper.keychain.*`. Backends: Windows Credential Manager, macOS Keychain,
Linux Secret Service.

#### vesper-mongodb 0.1.0
MongoDB via PyMongo. `MongoDatabase` injectable. IPC: `mongo:find/find_one/insert_one/
insert_many/update_one/update_many/delete_one/delete_many/count`. JS: `vesper.mongo.*`.
`ObjectId` auto-serialized to `str` in all responses.

#### vesper-shortcuts 0.1.0
Global keyboard shortcuts via pynput. Active when app is not focused. IPC:
`vesper:shortcuts:register/unregister/unregister_all`. JS: `vesper.shortcuts.*`.
Fires `shortcut` event with `{accelerator}` payload.

#### vesper-theme 0.1.0
OS dark/light mode via darkdetect. `watch=True` starts daemon thread and emits
`theme:change` event on mode switch. IPC: `vesper:theme:get`. JS: `vesper.theme.*`.

### Added — Documentation

- `README.md` — public-facing framework entry point with quickstart, feature list,
  plugin table, project structure, and links to all docs.
- `docs/` — 23 guides: getting-started, cli, project-config, ipc, module-system,
  guards, middleware, events, multiwindow, dialogs, notifications, tray, menu, shell,
  clipboard, window-controls, splash, deeplink, filesystem, file-transfers,
  auto-updates, code-signing, plugins, os-theme.
- `docs/recipes/` — 8 recipes: auth, context-menus, drag-out, state-between-windows,
  logging-middleware, user-preferences, theming, real-time.
- `plugins/*/README.md` — individual README for each of the 7 plugins.

### Added — Versioning

- `__version__` via `importlib.metadata` in `vesper` and all 7 plugins. Single source
  of truth is `pyproject.toml`. Fallback `"0.1.0"` for non-installed dev environments.

---

[Unreleased]: https://github.com/DannelCu/vesper/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/DannelCu/vesper/releases/tag/v0.1.0
