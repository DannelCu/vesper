# Getting Started

This guide walks you through installing Vesper, creating your first project, and understanding the basic development workflow.

---

## Requirements

- **Python 3.10+** — `python --version` to confirm
- **pip** — included with all modern Python installations
- **Node.js 18+** — only required for React, Vue, or Svelte templates
- **A system WebView runtime** — see below

### System WebView

Vesper renders your UI in the operating system's native WebView rather than bundling a
browser. That runtime comes from the OS, not from pip, so `pip install vesper` can
succeed on a machine that still cannot open a window.

**macOS** — nothing to install. The Cocoa/WKWebView backend ships with the system.

**Windows** — needs the [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/),
preinstalled on Windows 11 and on up-to-date Windows 10.

**Linux** — install GTK and WebKit2GTK, including the GObject introspection bindings:

```bash
# Debian / Ubuntu
sudo apt install python3-gi gir1.2-webkit2-4.1 libwebkit2gtk-4.1-0

# Fedora
sudo dnf install python3-gobject webkit2gtk4.1

# Arch
sudo pacman -S python-gobject webkit2gtk-4.1
```

> **Using a virtual environment on Linux?** Create it with `--system-site-packages`:
>
> ```bash
> python3 -m venv --system-site-packages .venv
> ```
>
> `python3-gi` is a distribution package installed into the system `site-packages`, and
> pip cannot provide it. A default venv is isolated from those packages, so the app
> fails at startup with `ModuleNotFoundError: No module named 'gi'`.

Run `vesper doctor` at any point to confirm which backend resolved on your machine.

---

## Install Vesper

```bash
pip install vesper
```

Verify the installation:

```bash
vesper version
```

---

## Create a Project

### Interactive wizard (recommended)

```bash
vesper init app
```

The wizard asks for your project name, template (vanilla, React, Vue, Svelte), CSS framework, bundler, and package manager. It generates the project structure and prints the next steps.

### With flags (skip the wizard)

```bash
vesper init app --name "my-app" --template vanilla
```

All flags are optional. Missing values fall back to their defaults (vanilla template, PyInstaller bundler, npm).

Available flags:

| Flag | Values | Default |
|---|---|---|
| `--name` | any string | `my-app` |
| `--template` | `vanilla`, `react`, `vue`, `svelte` | `vanilla` |
| `--styles` | `none`, `bootstrap`, `tailwind` | `none` |
| `--bundler` | `pyinstaller`, `nuitka` | `pyinstaller` |
| `--pm` | `npm`, `pnpm`, `yarn` | `npm` |

---

## Your First App (Vanilla)

After `vesper init app --template vanilla`, you have:

```
my-app/
├── app.py
├── vesper.toml
└── frontend/
    ├── index.html
    └── vesper.js
```

`app.py` looks like this:

```python
from vesper import App

app = App(title="my-app", frontend="frontend/index.html")

@app.command
def greet(name: str) -> str:
    return f"Hello, {name}!"

if __name__ == "__main__":
    app.run()
```

`frontend/index.html` calls that command from JavaScript:

```html
<!DOCTYPE html>
<html>
<head><title>my-app</title></head>
<body>
  <input id="name" placeholder="Your name" />
  <button onclick="run()">Greet</button>
  <p id="out"></p>

  <script src="vesper.js"></script>
  <script>
    async function run() {
      const name = document.getElementById("name").value
      const result = await vesper.invoke("greet", { name })
      document.getElementById("out").textContent = result
    }
  </script>
</body>
</html>
```

---

## Start the Dev Server

```bash
cd my-app
vesper dev
```

For vanilla projects, `vesper dev` starts a local HTTP server that serves `frontend/` and watches for changes:

- Python files (`*.py`) — restarts the Python process
- HTML, CSS, JS files — triggers a browser refresh

The app opens automatically in a native window.

---

## Add a Command

Commands are plain Python functions decorated with `@app.command`. They receive typed arguments, return a JSON-serializable value, and are callable from JavaScript via `vesper.invoke()`.

```python
from pathlib import Path

@app.command
def read_file(path: str) -> str:
    return Path(path).read_text()
```

Call it from JavaScript:

```js
const contents = await vesper.invoke("read_file", { path: "/etc/hosts" })
```

Vesper validates the arguments before running the function. If `path` is missing, the JS call rejects with a `ValidationError` before the Python function is ever reached.

---

## Push Events to the Frontend

Use `app.emit()` to send data from Python to JavaScript without waiting for a request:

```python
import threading

@app.command
def start_countdown():
    def run():
        for i in range(5, 0, -1):
            app.emit("tick", {"value": i})
            import time; time.sleep(1)
        app.emit("done", {})
    threading.Thread(target=run, daemon=True).start()
```

In JavaScript, subscribe with `vesper.on()`:

```js
vesper.on("tick", ({ value }) => {
    document.getElementById("counter").textContent = value
})

vesper.on("done", () => {
    document.getElementById("counter").textContent = "Done!"
})
```

---

## React / Vue / Svelte

For framework templates, the workflow adds a Vite frontend step:

```bash
vesper init app --template react --pm pnpm
cd my-app
pnpm install
vesper dev
```

`vesper dev` with a framework template:
1. Starts Vite on a random port
2. Waits until Vite is ready (polls HTTP)
3. Sets `VESPER_DEV_URL` so PyWebView loads from Vite instead of disk
4. Launches `app.py`

Hot module replacement (HMR) works normally — Vite handles frontend reloads; Vesper restarts the Python process on `.py` changes.

In your React components, call Vesper the same way:

```jsx
import { useState } from "react"

export default function App() {
    const [msg, setMsg] = useState("")

    async function greet() {
        const result = await window.vesper.invoke("greet", { name: "World" })
        setMsg(result)
    }

    return (
        <div>
            <button onClick={greet}>Greet</button>
            <p>{msg}</p>
        </div>
    )
}
```

> `vesper.js` is in `public/` for framework projects — Vite serves it as a static asset, so `window.vesper` is available globally without an import.

---

## Build for Production

```bash
vesper build
```

- **Vanilla**: copies `frontend/` to `dist/`, bundles all JS files into `dist/bundle.js`, updates `index.html` to reference it.
- **Frameworks**: runs `<pm> run build` (Vite), which outputs to `dist/`.

Test the production build:

```bash
vesper run
```

---

## Package as a Native Executable

```bash
vesper package
```

Produces a single executable in `package/<app-name>[.exe]`.

The default bundler is PyInstaller. Nuitka (selected at `vesper init` time) produces a fully native binary but requires a C compiler — see [Code Signing](code-signing.md) for distribution.

---

## Diagnose Issues

```bash
vesper doctor
```

Checks Python version, Vesper install, PyWebView, the system WebView backend, Node.js (if needed), package manager availability, `vesper.toml` validity, entrypoint presence, frontend structure, and whether the SDK script tag is present in `index.html`.

Every failed check prints a `Fix:` line with the command to run.

Common failures:

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'gi'` | Linux venv isolated from system GTK bindings | Recreate the venv with `--system-site-packages` |
| `WebView backend: none available` | System WebView runtime not installed | See [System WebView](#system-webview) above |
| `WinForms fell back to MSHTML` | WebView2 Runtime missing on Windows — the app runs on the legacy IE11 renderer and modern CSS/JS break | Install the [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/) |
| Window opens behind other apps on macOS, or never takes focus | Python is not a framework build | Use python.org, Xcode, or Homebrew Python; for pyenv, build with `PYTHON_CONFIGURE_OPTS="--enable-framework"` |

---

## Next Steps

| Topic | Guide |
|---|---|
| All CLI commands | [CLI Reference](cli.md) |
| How IPC works in detail | [IPC](ipc.md) |
| Organize code into modules | [Module System & DI](module-system.md) |
| Protect commands with guards | [Guards](guards.md) |
| Persistent storage | [Plugins](plugins.md) → vesper-store |
| Native menus, tray, splash | [Menu Bar](menu.md), [Tray](tray.md), [Splash Screen](splash.md) |
| Package and sign for distribution | [Code Signing](code-signing.md) |
