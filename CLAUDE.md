# CLAUDE.md

Vesper — Python-first desktop framework (PyWebView + NestJS-style modules).
Read this, then only the docs the task points to.

## Start of every session
- `git log --oneline -10`, then `pytest -q`. The suite must start green; if it
  doesn't, that's the task.
- `CONTRIBUTING.md` → "Where each feature lives". The four-level tree
  (core / plugin / recipe / known issue) governs every decision below.

## Non-negotiables
1. **Core deps are `pywebview` + `packaging`. Nothing else, ever.** Anything
   needing a new dependency is a plugin, not core.
2. **Missing backend → no-op + honest return**, reported through
   `capabilities.py` and `vesper doctor` with a `fix` line. Never an uncaught
   exception crossing IPC. Sole exception: `app.tray()` raises when its extra is
   absent (opt-in, explicit).
3. **`capabilities.probe()` is the single source of truth** for what's available.
   Never duplicate backend detection elsewhere.
4. **Paths go through `FsScope`** (both endpoints on copy/move). **Processes go
   through `ShellScope`** (deny-by-default). No new API escapes them.
5. **Close your Apps.** The async loop is lazy, but an App that used it holds a
   thread: `with App(...)` or `app.close()`. A `conftest.py` fixture fails any
   test leaking a `vesper-async` thread.
6. Never `shell=True`; argv as a list. Never `eval()` on frontend input.

## Every feature ships five things
code · tests · `docs/<topic>.md` · SDK namespace in `vesper/sdk/vesper.js` ·
`CHANGELOG.md` entry. Missing any one = not done.

## Where to look
| Task | Read |
|---|---|
| Deciding *where* code belongs | `CONTRIBUTING.md` |
| "Can we do X?" / "why isn't X native?" | `KNOWN-ISSUES.md` first — it may be deliberate |
| Optional backends, degradation | `docs/optional-features.md`, `core/capabilities.py` |
| IPC, guards, middleware, DI | `docs/module-system.md`, `core/ipc.py`, `core/module.py` |
| Windows, frameless, effects | `docs/frameless.md`, `docs/window-controls.md`, `core/window.py`, `core/config.py` |
| Filesystem | `docs/filesystem.md`, `core/fs.py`, `core/fs_scope.py` |
| Spawning processes | `docs/process.md`, `core/process.py` |
| Serving the frontend | `core/static_server.py`, `commands/dev.py` — same confinement rules |
| CLI, packaging, signing | `docs/cli.md`, `docs/code-signing.md`, `commands/` |
| Plugins | `docs/plugins.md`; copy the shape of `plugins/vesper-theme/` |
| Platform prerequisites | `docs/platform-requirements.md` |

## Testing
- Pure Python: test for real, on all three OS.
- Native calls (COM, pyobjc, D-Bus, registry): mock, assert the call is *built*
  correctly and that degradation works — then add the area to the CI coverage
  table in `KNOWN-ISSUES.md`. Mocks never prove a visible effect.
- `pytest plugins/<name>` runs one plugin; its deps must be installed.
- **Passing in isolation ≠ passing in the suite.** Run the whole `pytest -q`
  before claiming green.

## Traps (learned the hard way)
- `xdg-open` rejects `--`, so `shell.reveal()` passes an **absolute path**
  instead. Don't "fix" this back.
- PyWebView builds its JS-callable surface by walking attributes — never hang
  internals off a public attribute of `App` or the api object.
- Mocks hid a real `autostart` bug on Windows (`OpenKey` can't create a missing
  key). When the API is stdlib, prefer a real round-trip test.
- ANSI output must degrade: no TTY, or `NO_COLOR` set → plain text.

## Don't
- Publish to PyPI, tag releases, or bump versions — the maintainer does that.
- Put merely-unfinished work in `KNOWN-ISSUES.md`; that's backlog, not a known
  issue.
- Fix things you weren't asked to fix. Report them instead.
