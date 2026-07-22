# Contributing to Vesper

Thanks for your interest in Vesper. This guide covers setting up a development
environment, running the test suite, and the conventions the codebase follows.

If you only want to *use* Vesper to build an app, read
[Getting Started](docs/getting-started.md) instead — this document is for working
**on** the framework itself.

---

## System Prerequisites

Vesper renders through the operating system's native WebView. `pip install pywebview`
pulls in a pure-Python package — it does **not** install that WebView. You need the
platform runtime below, or the framework installs cleanly and then fails the moment a
window opens.

### Linux

Vesper uses GTK + WebKit2GTK. Both the C libraries and the GObject introspection
bindings are distribution packages — pip cannot install them.

```bash
# Debian / Ubuntu
sudo apt install python3-gi gir1.2-webkit2-4.1 libwebkit2gtk-4.1-0

# Fedora
sudo dnf install python3-gobject webkit2gtk4.1

# Arch
sudo pacman -S python-gobject webkit2gtk-4.1
```

On Debian/Ubuntu you may also need the venv module for your Python version, which is
packaged separately:

```bash
sudo apt install python3-venv    # or python3.13-venv, python3.14-venv, ...
```

Without it, `python3 -m venv` fails with `ensurepip is not available`.

**Qt instead of GTK:** if you prefer Qt, `pip install pyqt5 pyqtwebengine` and set
`PYWEBVIEW_GUI=qt`. Vesper picks GTK first, except under KDE (`KDE_FULL_SESSION`),
where pywebview prefers Qt automatically.

### macOS

The Cocoa/WKWebView backend ships with the system — no Homebrew packages required.
PyObjC is installed automatically as a pywebview dependency. Two edge cases:

- **Use a framework build of Python.** Cocoa requires one to create windows, take
  keyboard focus, and own a menu bar. The python.org installers, Xcode's Python, and
  Homebrew's `python@3.x` all provide one. A bare `pyenv install` does **not** unless
  built with `--enable-framework`:

  ```bash
  PYTHON_CONFIGURE_OPTS="--enable-framework" pyenv install 3.12
  ```

  Symptoms of a non-framework build: the window opens behind other apps, never takes
  focus, or the process dies with a `NSInternalInconsistencyException`.

- **Xcode Command Line Tools** are needed for code signing work (`xcode-select
  --install`). Not required for regular development.

If you package an unsigned app for testing, macOS quarantines it on first launch
("app is damaged and can't be opened"). Clear the flag with:

```bash
xattr -dr com.apple.quarantine dist/YourApp.app
```

See [Code Signing](docs/code-signing.md) for the real fix.

### Windows

Needs the **Microsoft Edge WebView2 Runtime**, preinstalled on Windows 11 and on
up-to-date Windows 10. If it is missing, download it from
[Microsoft](https://developer.microsoft.com/microsoft-edge/webview2/).

`pythonnet` is installed automatically with pywebview. When the WebView2 runtime is
absent, pywebview silently falls back to the legacy MSHTML (IE11) renderer — the app
launches but modern CSS and JavaScript break in confusing ways. `vesper doctor` reports
this fallback as a failure rather than letting you debug it blind.

---

## Development Setup

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/your-org/vesper.git
cd vesper
```

**On Linux, create the venv with `--system-site-packages`:**

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
```

This matters. The GTK bindings (`python3-gi`) are installed by your system package
manager into the system `site-packages`. A default venv is isolated from those, so
pywebview cannot import them and every window fails with
`ModuleNotFoundError: No module named 'gi'`.

On macOS and Windows the flag is unnecessary — plain `python -m venv .venv` is fine,
since PyObjC and pythonnet install from PyPI:

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # macOS
```

### 2. Install the framework and plugins

Everything is installed editable so your changes take effect without reinstalling:

```bash
pip install -e ".[tray]"

pip install -e plugins/vesper-store
pip install -e plugins/vesper-db
pip install -e plugins/vesper-http
pip install -e plugins/vesper-keychain
pip install -e plugins/vesper-mongodb
pip install -e plugins/vesper-shortcuts
pip install -e plugins/vesper-theme
```

The plugins are separate distributions that depend on `vesper`. Installing them is not
optional for development — `pytest` collects `plugins/`, and a missing plugin dependency
fails collection for the whole suite rather than just skipping those tests.

### 3. Install test dependencies

```bash
pip install pytest pytest-asyncio sqlalchemy httpx pymongo mongomock keyring pynput
```

### 4. Verify the setup

```bash
pytest -q
```

You should see the full suite pass. Then confirm the WebView backend resolved:

```bash
vesper doctor
```

Run from a project directory (see below); the project-specific checks need one. The
line to look for is `[OK] WebView backend available: ...`. If it fails, it prints the
install command for your platform.

---

## Working Against a Test App

Create a scratch app outside the repository and run it against your editable install:

```bash
cd ..
vesper init app --name vesper-test-app --template vanilla
cd vesper-test-app
vesper dev
```

Because Vesper is installed editable, changes to `vesper/` take effect immediately —
`vesper dev` restarts the Python process on backend changes and refreshes the WebView on
frontend changes.

Use the `vanilla` template for framework work: it needs no Node.js and has the shortest
edit-run loop. Switch to `--template react` (or `vue` / `svelte`) only when the change
touches Vite integration or the generated project scaffolding.

---

## Running Tests

```bash
pytest -q                          # everything (tests/ and plugins/)
pytest tests/ -q                   # core framework only
pytest plugins/vesper-db -q        # one plugin
pytest tests/test_ipc.py -q        # one file
pytest -k "guard" -q               # by name
```

Tests must be **hermetic** — they cannot depend on what happens to be installed on the
machine running them. When adding a check that probes system state, stub the probe in
the tests and cover the probe itself in isolation. `tests/test_doctor.py` shows the
pattern: an autouse fixture stubs the WebView backend detection so the project checks
stay deterministic, while dedicated tests call `_detect_webview_backend` directly with
mocked imports.

CI runs the suite on Linux, macOS, and Windows across Python 3.10–3.14.

### Window smoke test

The unit suite mocks PyWebView, so it passes on machines that cannot open a window at
all. `scripts/smoke_window.py` covers that gap end to end: it opens a real native
window, has the frontend invoke a Python command over IPC, verifies the returned value,
and shuts down.

```bash
python scripts/smoke_window.py          # macOS, Windows, or Linux with a display
xvfb-run -a python scripts/smoke_window.py   # Linux, headless
```

CI runs it on all three platforms as a separate `smoke` job. On Linux that job uses the
distribution's Python rather than `actions/setup-python`, because `python3-gi` is an apt
package that a setup-python interpreter cannot import — the same reason your local venv
needs `--system-site-packages`.

Run this after changing anything in the window lifecycle, the IPC bridge, or
`vesper/sdk/vesper.js`, since the mocked unit tests cannot catch a break there.

---

## Repository Layout

```text
vesper/
├── vesper/
│   ├── core/          Framework runtime — App, IPC, Window, modules/DI, guards
│   ├── commands/      CLI subcommands (one module per command)
│   ├── sdk/           vesper.js — the frontend IPC bridge
│   ├── exceptions/    Typed error hierarchy
│   └── cli.py         Argument parsing and dispatch
├── plugins/           Seven first-party plugins, each its own distribution
├── docs/              User-facing documentation
│   └── recipes/       Complete examples for patterns not built into the framework
└── tests/             Core framework test suite
```

Each CLI command follows the same shape: an `add_<name>_parser(subparsers)` function that
registers arguments, and a `handle_<name>(args)` function returning `True` when it
handled the command.

---

## `.gitignore` is deny-by-default — read this before adding files

This repository's `.gitignore` ignores **everything** and then re-allows specific
paths:

```gitignore
# Ignore everything by default
*

# Keep core Vesper source
!vesper/
!vesper/**

# Keep documentation
!docs/
!docs/**
...
```

**A new top-level file or directory will not be committed unless you add it to the
allowlist.** `git add` on an ignored path fails silently in the sense that nothing is
staged, and `git status` will not show it as untracked — so the file looks handled
and simply never lands. This has already bitten this project: `CONTRIBUTING.md` and
`scripts/` were written, tested and "committed" while being invisible to git, which
would have broken CI on a missing file.

When you add something that belongs in the repository:

```gitignore
# Keep whatever it is
!newthing/
!newthing/**
```

Both lines matter. `!newthing/` un-ignores the directory; without `!newthing/**` its
contents stay ignored.

Then confirm before you commit. The unambiguous check is a dry-run add:

```console
$ git add -n path/to/your/file
add 'path/to/your/file'                      # ← good, it will be committed

$ git add -n path/to/your/file
The following paths are ignored by one of your .gitignore files:
path/to/your/file                            # ← still ignored, fix the allowlist
```

`git check-ignore -v` also works but is easy to misread — **its exit code does not
tell you whether the file is ignored**, because a negation rule counts as a match too:

```console
$ git check-ignore -v newthing/file.py
.gitignore:2:*            newthing/file.py   # ← ignored (catch-all matched)

$ git check-ignore -v newthing/file.py
.gitignore:20:!newthing/**  newthing/file.py # ← NOT ignored (a "!" rule matched)
```

Both exit `0`. What matters is whether the printed rule starts with `!`. Files that
are already tracked print nothing and exit `1`, since `check-ignore` skips them.

`git status` alone is not a sufficient check either: ignored files do not show up as
untracked. Use `--untracked-files=all`:

```bash
git status --porcelain --untracked-files=all | grep newthing
```

Generated files stay ignored on purpose. `examples/**/notes.txt` is excluded because
running the example writes it.

---

## Where a feature lives

Every proposed feature lands in exactly one of four places. Walk this tree from the
top; the first level that fits is where the work goes. This is the framework's load-
bearing decision — it is why the core has two runtime dependencies and why `vesper
doctor` can be honest about what a machine can and cannot do.

1. **Core** — it can be implemented with the Python standard library, PyWebView, or
   the dependencies already declared, with **zero new dependencies** → it goes in
   `vesper/core/`. Acceptable tools: `ctypes`, `subprocess` calls to binaries the OS
   ships (`osascript`, `powershell`, `hdiutil`, `xclip`), `http.server`, `winreg`,
   `plistlib`, and JavaScript in the SDK. When the OS-level backend is missing, the
   feature degrades to a no-op with an honest return value and the gap is reported
   through `capabilities.py` and `vesper doctor`.
   *Example: the full `vesper.fs` namespace — copy, move, stat, byte I/O — is
   `shutil`/`os`/`base64` all the way down, so it belongs in the core.*

2. **Plugin** — it needs an external library, but is useful and isolates cleanly
   behind a plugin boundary → it goes in `plugins/vesper-<name>/` with its own
   `pyproject.toml`. The dependency must earn its place: actively maintained,
   cross-platform, and pip-installable without a compiler toolchain on the user's
   machine (prebuilt wheels count as acceptable; requiring a build toolchain does
   not).
   *Example: file watching. Doing it properly means inotify/FSEvents/
   ReadDirectoryChangesW, which is exactly what `watchdog` wraps — so it is
   `vesper-watch`, not core code.*

3. **Recipe** — it cannot be implemented in Vesper, but a documented workaround
   solves it: a library the user installs themselves, a manual action (permissions,
   signing, OS configuration), or a code pattern in their app → it goes in
   `docs/recipes/<name>.md` with **explicit coverage of Windows, macOS, and Linux**.
   If the workaround cannot cover all three, it is not a recipe — it is a known
   issue. (One legitimate exception: a recipe for an inherently single-platform
   artifact, like a Windows installer, which must say so explicitly.)
   *Example: printing. `window.print()` works everywhere and print-to-PDF exists on
   all three platforms as a manual step, so `docs/recipes/printing.md` covers it.*

4. **Known issue** — genuinely impossible today because of a barrier Vesper does not
   control: an API PyWebView does not expose, the absence of a cross-desktop
   standard, per-platform native code beyond the project's scope → it goes in
   `KNOWN-ISSUES.md` in the existing format: current behaviour, why it was left this
   way, and what would unblock it. Only the impossible belongs here — pending effort
   is backlog, not a known issue.
   *Example: jump lists and dock menus. Windows requires COM
   (`ICustomDestinationList`) and macOS requires the NSApplication delegate, which
   PyWebView owns and does not surface. There is no three-platform workaround, so it
   is documented as impossible for now.*

When a change is rejected from one level, it moves *down* the tree, never up: a core
proposal that turns out to need a library becomes a plugin proposal, not a core
exception.

---

## Conventions

- **Python 3.10+.** Use `from __future__ import annotations` and modern typing syntax
  (`str | None`, not `Optional[str]`).
- **No runtime dependencies beyond pywebview and packaging.** Optional features go
  behind extras (like `[tray]`) or into a plugin. Native OS integrations shell out to
  built-in tools (`osascript`, `powershell`, `notify-send`) rather than adding packages.
- **Comments explain why, not what.** Add one where a reader would otherwise wonder why
  the code is shaped that way; skip it when the code already says it.
- **Every behavior change needs a test**, and every bug fix needs a test that fails
  before the fix.
- **Update the docs in the same change.** A new CLI flag belongs in
  [docs/cli.md](docs/cli.md), a new feature in its own guide, and anything
  user-visible in [CHANGELOG.md](CHANGELOG.md) under `[Unreleased]`.

### Security-sensitive areas

Some code paths cross a trust boundary and deserve extra scrutiny — anything that builds
a shell command (`notify`, `clipboard`, `shell`), touches the filesystem on behalf of the
frontend (`fs`, `fs_scope`), or evaluates JavaScript in the WebView. Pass arguments as
lists rather than interpolating into strings, and never build a command from
frontend-supplied input without escaping it.

---

## Pull Requests

1. Branch from `main`.
2. Make the change, with tests.
3. Run `pytest -q` — the full suite must pass.
4. Update relevant docs and add a `CHANGELOG.md` entry under `[Unreleased]`.
5. Open the PR describing what changed and why, and note which platforms you tested on.

Platform coverage is genuinely useful information in a PR: most contributors can only
test one, and WebView behavior differs meaningfully across the three.

---

## Reporting Issues

Include:

- Operating system and version
- Python version (`python --version`)
- Vesper version (`vesper version`)
- Full output of `vesper doctor`
- Minimal reproduction — ideally an `app.py` short enough to paste

`vesper doctor` output resolves most environment issues immediately, since it reports
which WebView backend actually resolved on your machine.
