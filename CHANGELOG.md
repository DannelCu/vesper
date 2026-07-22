# Changelog

All notable changes to Vesper and its official plugins are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Vesper adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

**Examples**

- **[examples/media-vault](examples/media-vault/)** — a media library with an in-app
  video player, built to make one point concrete: seeking needs HTTP byte ranges, so
  a `<video>` on `file://` has a dead scrub bar and one on the production localhost
  server does not. Also covers the scoped filesystem API, a real `ShellScope`
  allowlist over ffprobe/ffmpeg, downloads with taskbar progress, keep-awake and
  suspend handling, multi-window, splash, single-instance and the file clipboard. Runs
  with no optional dependency installed: without ffmpeg there are no thumbnails and a
  banner says why.
- **[examples/README.md](examples/README.md)** — an index of the examples, with what
  each one demonstrates and who should read it first.

**Recipes and known issues (documentation of what Vesper cannot do — yet)**

- **[Printing recipe](docs/recipes/printing.md)** — `window.print()` on all three
  platforms with engine differences and `@media print` guidance; print-to-PDF via
  the system dialog (Microsoft Print to PDF / Save as PDF / cups-pdf per distro);
  programmatic PDFs as an app-level Python decision. Silent printing is
  impossible today → KI4.
- **[Camera & Microphone recipe](docs/recipes/media-capture.md)** — the manual
  per-platform configuration that maximises `getUserMedia`'s odds (macOS
  Info.plist keys + entitlements + signed bundle, Windows privacy toggles and
  origin persistence, Linux GStreamer packages and distro-build caveats), plus
  the JS detection/fallback pattern. Explicitly honest: it improves odds, it
  cannot guarantee them → KI5.
- **KNOWN-ISSUES KI1–KI6** — six linkable entries for what is genuinely
  impossible today, all sharing one root cause (PyWebView owns the engine
  objects and does not surface these APIs) and one unblocker (upstream
  exposure): drag-out (KI1), native context menus (KI2), custom protocols /
  request interception (KI3, with the localhost server as the pragmatic
  substitute), programmatic printing (KI4), the media permission handler (KI5),
  and jump lists / dock menus / recent documents (KI6 — the one with no
  three-platform workaround, hence no recipe).
- The existing drag-out and context-menus recipes now state their place in the
  philosophy and link to KI1/KI2; the CI coverage table gained rows for every
  new native-touching area (file clipboard, mica, installers, rich
  notifications, screenshots, serial, frameless).

**Plugins (external dependencies, isolated behind plugin boundaries)**

- **vesper-watch** — file watching via watchdog. `vesper.watch.watch(path, {
  recursive, debounce, onChange })` streams `created|modified|deleted|moved`
  events; watched paths honour the app's `fs_scope`, observers stop at app
  close, and bursts are debounced. README covers the inotify watch limit.
- **vesper-notify** — rich notifications via desktop-notifier: click callbacks,
  action buttons, custom icon and sound (`vesper.notifyRich.send`). The core's
  minimal `vesper.notify()` is untouched as the fallback, and
  `capabilities().notifications` now reports which backend is active. README
  documents the macOS constraint: callbacks require a signed bundle.
- **vesper-crash** — error reporting via sentry-sdk. Captures IPC command
  exceptions (through the new `IPC.on_error` observation hook — the frontend
  receives the identical error response), unhandled Python exceptions (chained
  `sys.excepthook`), and frontend JS errors (`window.onerror` /
  `unhandledrejection` bridged over `vesper:crash:report`). Privacy-first: no
  DSN → silent no-op; no PII, no breadcrumbs, no automatic integrations, and
  the README states exactly what an event contains.
- **vesper-screenshot** — screen capture via mss: full screen, monitor N, or a
  region, as a PNG data URL or written to a scope-validated path. Wayland and
  the macOS Screen Recording permission degrade with explanatory errors, and
  the new `screenshot` capability reports them in `vesper doctor` (Wayland as
  N/A — nothing to install).
- **vesper-serial** — serial ports via pyserial: `listPorts`, multiple
  simultaneous connections with ids, streamed `vesper:serial:data` events,
  write, close (plus a `closed` event on unplug). CI exercises the full path
  against `loop://`; README covers Linux `dialout` per distro and Windows
  drivers.
- **vesper-sysinfo** — system information via psutil: CPU, memory, disks,
  network counters, battery, uptime; on-demand snapshot plus a tick
  subscription that stops cleanly at app close (no orphan threads).
- **`IPC.on_error(fn)`** — a core observation hook for exceptions raised in
  commands, guards and middleware (not policy denials). Zero-dependency, added
  so error-reporting plugins can observe failures without wrapping the pipeline;
  the error response the frontend receives is unchanged.

**Core (zero new dependencies)**

- **DevTools in `vesper dev`.** The WebView inspector is now available by default in
  development on all three platforms (wired as `VESPER_DEVTOOLS` →
  `webview.start(debug=True)`), with `--no-devtools` to opt out. `vesper run` and
  packaged builds never set the variable, so production cannot expose the inspector.
  Distinct from `App(debug=True)`, which only controls IPC error detail.
- **Complete filesystem API.** `vesper.fs` gains `mkdir`, `copy`, `move` (covers
  rename), `remove` (permanent; directories require an explicit `recursive` flag),
  `stat`, and `readBytes`/`writeBytes` (base64 over IPC, formalising what
  docs/file-transfers.md taught by hand). Every operation validates against
  `fs_scope` — `copy`/`move` validate both ends. The scope is now also exposed as
  `app.fs_scope` for plugins.
- **Frameless and transparent windows.** `App(...)` and `register_window(...)` accept
  `frameless`, `easy_drag`, `transparent`, `vibrancy` (macOS), and
  `min_width`/`min_height`. Drag regions for custom titlebars via the
  `data-vesper-drag` attribute or `vesper.window.makeDraggable()` — the functional
  equivalent of `-webkit-app-region`, which system WebViews do not support. New
  [Frameless Windows](docs/frameless.md) guide and
  [Custom Titlebar recipe](docs/recipes/custom-titlebar.md).
- **Windows 11 backdrop materials.** `vesper.window.setBackdrop("mica" | "acrylic" |
  "tabbed" | "none")` via `DwmSetWindowAttribute` through ctypes. Honest no-op
  (resolves `false`) everywhere else — reported as the `mica` capability, N/A
  without a fix line since there is nothing to install.
- **Production localhost server.** `App(serve_frontend=True)` serves the bundled
  frontend from `127.0.0.1` (ephemeral port, per-session token in the URL path, SPA
  fallback to index.html) instead of `file://`, fixing ES modules,
  `history.pushState` routing and relative fetch in packaged apps. The server lives
  and dies with `app.run()`; the dev server takes precedence. The static handler is
  shared with `vesper dev` (`vesper.core.static_server`). Threat model documented in
  docs/project-config.md — an `App` parameter rather than a `vesper.toml` key
  because the config file is not bundled into the binary.
- **Scoped process execution.** New `vesper.process` namespace (`run`, `spawn` with
  streamed `vesper:process:stdout|stderr|exit` events, `kill`) behind a declarative
  `ShellScope` allowlist (`App(shell_scope=...)`) — executables by name or path,
  optional fnmatch argument patterns. Secure by default: no scope, no execution.
  Never `shell=True`; argv lists end to end. Spawned processes are terminated at app
  teardown. See [docs/process.md](docs/process.md).
- **Generic downloads with progress.** `vesper.net.download(url, dest, onProgress,
  sha256?)` — the updater's download machinery generalised to a scope-validated
  destination, with optional SHA-256 verification that deletes the file on mismatch.
  The updater now consumes the same transport (`net.fetch`) with no behaviour change.
  See [docs/network.md](docs/network.md).
- **Semantic window positioning.** `vesper.window.position("top-right", { screen,
  offset })` — nine named positions, monitor by index or `"cursor"` (ctypes on
  Windows, pyobjc on macOS; degrades to primary on Linux), correct with negative
  multi-monitor coordinates. Tray-icon-relative positioning is documented as not
  obtainable (pystray does not expose it); the supported menubar pattern lives in
  the [Menubar App recipe](docs/recipes/menubar-app.md).
- **Native installers.** `vesper package --installer` builds a `.dmg` on macOS
  (`hdiutil`, drag-to-install layout, signs the `.app` first when `[sign]` is
  configured) and a `.deb` on Debian/Ubuntu (`dpkg-deb`, menu entry, clean
  uninstall), with metadata from the new `[installer]` section of `vesper.toml`.
  Windows installers stay outside the core (NSIS is non-pip tooling): the flag
  explains what is missing, `vesper doctor` reports NSIS as the `nsis` capability,
  and the [Windows Installer recipe](docs/recipes/windows-installer.md) provides a
  ready-to-adapt NSIS script plus an AppImage walkthrough.
- **File clipboard.** `vesper.clipboard.writeFiles(paths)` / `readFiles()` — the OS
  clipboard's file object, interoperating with Explorer/Finder/file managers.
  CF_HDROP via ctypes on Windows, `osascript` on macOS (reads return at most one
  file — platform limitation), `xclip -t text/uri-list` on Linux (same xclip as
  text/images, reported as the `clipboard_files` capability). Paths read from the
  clipboard are filtered through `fs_scope` before reaching the frontend.
- **CONTRIBUTING.md — "Where a feature lives".** A four-level decision tree (core →
  plugin → recipe → known issue) that governs where every proposed feature lands,
  with the admission criteria for each level and one worked example per level. It
  codifies the philosophy the codebase already followed implicitly: zero new core
  dependencies, external libraries behind plugin boundaries, three-OS coverage for
  recipes, and KNOWN-ISSUES reserved for the genuinely impossible.
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
- **Native menus were completely broken.** `app.menu()` raised
  `AttributeError: module 'webview' has no attribute 'MenuAction'` before the window
  opened — only `Menu` is re-exported at PyWebView's top level, while `MenuAction` and
  `MenuSeparator` live in `webview.menu`. Every menu and every separator was affected.
  The menu tests missed it because they replaced the whole `webview` module with a
  bare `MagicMock`, which invents any attribute asked of it; they now patch the
  resolved classes, use `spec=webview` where a module mock is still needed, and a new
  test resolves the three classes against the real PyWebView.
- **`app.quit()` left the process running when the app had a secondary window.**
  PyWebView's `start()` returns only when the last window closes, and `quit()`
  destroyed just the main one — so an app with `register_window()` kept running with
  nothing on screen and never exited. It now closes secondary windows first, each
  independently, then the main one.
- **The production server ignored `Range` requests, so media could not be seeked.**
  `App(serve_frontend=True)` answered every request with `200` and the whole file, no
  `Accept-Ranges` — a `<video>` element will not offer a seek bar without it, which
  made the localhost server no better than `file://` for the media playback it exists
  to enable. It now answers `206 Partial Content` with `Content-Range`, handles the
  open-ended, suffix and single-byte forms, and returns `416` for an unsatisfiable
  range. Unsupported forms (multi-range, non-`bytes` units) still return the whole
  file, which is always a legal answer.
- **The production server read whole files into memory.** Every response called
  `read_bytes()`, so serving a 2 GB video cost 2 GB of RSS per request. Files are now
  streamed in 64 KB blocks: a 64 KB range out of a 300 MB file moves peak RSS by 2 MB.
- **IPC internals were reachable from JavaScript.** PyWebView builds the JS-callable
  API by walking the `js_api` object with `dir()` and recursing into public
  attributes. Vesper held the IPC instance under a public name, so
  `window.pywebview.api.ipc.handle`, `.ipc.close` and `.ipc.registry.register` were
  published to the page — a route around the `invoke` envelope that guards and
  middleware hang off. The reference is now private, so only `invoke` is exposed.
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
