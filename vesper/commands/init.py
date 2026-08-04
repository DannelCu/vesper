from __future__ import annotations

import argparse
import json
import shutil
from importlib.resources import files as _pkg_files
from pathlib import Path

from vesper.commands.utils import (
    copy_sdk_to_frontend,
    pm_add,
    pm_add_dev,
    pm_run,
    validate_package_manager,
)


def _copy_asset(target_dir: Path, asset_name: str) -> None:
    src = _pkg_files("vesper").joinpath("assets", asset_name)
    dst = target_dir / asset_name
    with src.open("rb") as f:
        dst.write_bytes(f.read())


# ─── Constants ───────────────────────────────────────────────────────────────

SUPPORTED_TEMPLATES = {
    "vanilla",
    "react",
    "vue",
    "svelte",
}

SUPPORTED_STYLES = {
    "none",
    "bootstrap",
    "tailwind",
}

SUPPORTED_BUNDLERS = {
    "pyinstaller",
    "nuitka",
}

SUPPORTED_PACKAGE_MANAGERS = {
    "npm",
    "pnpm",
    "yarn",
}

# Framework templates only — vanilla has no build step, so TypeScript doesn't apply.
SUPPORTED_LANGUAGES = {
    "js",
    "ts",
}


# ─── Validation ──────────────────────────────────────────────────────────────


def normalize_app_directory_name(name: str) -> str:
    normalized = name.strip().lower().replace(" ", "-")

    if not normalized:
        raise ValueError("App name cannot be empty.")

    return normalized


def validate_template(template: str) -> str:
    normalized = template.strip().lower()

    if normalized not in SUPPORTED_TEMPLATES:
        print(f"Unsupported template: {template}")
        print("")
        print("Available templates:")

        for t in sorted(SUPPORTED_TEMPLATES):
            print(f"  - {t}")

        raise SystemExit(1)

    return normalized


def validate_styles(styles: str) -> str:
    normalized = styles.strip().lower()

    if normalized not in SUPPORTED_STYLES:
        print(f"Unsupported styles option: {styles}")
        print("")
        print("Available styles:")

        for s in sorted(SUPPORTED_STYLES):
            print(f"  - {s}")

        raise SystemExit(1)

    return normalized


def validate_bundler(bundler: str) -> str:
    normalized = bundler.strip().lower()

    if normalized not in SUPPORTED_BUNDLERS:
        print(f"Unsupported bundler: {bundler}")
        print("")
        print("Available bundlers:")

        for b in sorted(SUPPORTED_BUNDLERS):
            print(f"  - {b}")

        raise SystemExit(1)

    return normalized


def validate_language(language: str) -> str:
    normalized = language.strip().lower()

    if normalized not in SUPPORTED_LANGUAGES:
        print(f"Unsupported language: {language}")
        print("")
        print("Available languages:")

        for lang in sorted(SUPPORTED_LANGUAGES):
            print(f"  - {lang}")

        raise SystemExit(1)

    return normalized


# ─── vesper.toml ─────────────────────────────────────────────────────────────


def create_vesper_toml(
    app_dir: Path,
    *,
    name: str,
    template: str,
    styles: str,
    bundler: str,
    package_manager: str = "npm",
    language: str = "js",
) -> None:
    content = (
        f"[project]\n"
        f'name = "{name}"\n'
        f'template = "{template}"\n'
        f'styles = "{styles}"\n'
        f'bundler = "{bundler}"\n'
        f'package_manager = "{package_manager}"\n'
    )

    # Absence means JS — only written for the non-default so a plain JS
    # scaffold's vesper.toml stays byte-for-byte what it was before TS existed.
    if language != "js":
        content += f'language = "{language}"\n'

    (app_dir / "vesper.toml").write_text(content, encoding="utf-8")


# ─── Wizard ──────────────────────────────────────────────────────────────────


def _prompt(question: str, default: str, choices: dict[str, tuple[str, str]]) -> str:
    print(question)

    for number, (value, label) in choices.items():
        marker = " (default)" if value == default else ""
        print(f"  [{number}] {label}{marker}")

    answer = input("Choice: ").strip()

    if not answer:
        return default

    if answer in choices:
        return choices[answer][0]

    for _, (value, _) in choices.items():
        if answer.lower() == value.lower():
            return value

    print(f"Invalid choice. Using default: {default}")
    return default


def run_wizard() -> dict:
    print("Creating a new Vesper app.")
    print("")

    try:
        name = input("App name (my-vesper-app): ").strip() or "my-vesper-app"

        print("")

        template = _prompt(
            "JS Template:",
            "vanilla",
            {
                "1": ("vanilla", "Vanilla HTML/CSS/JS"),
                "2": ("react", "React"),
                "3": ("vue", "Vue"),
                "4": ("svelte", "Svelte"),
            },
        )

        print("")

        language = "js"

        if template != "vanilla":
            language = _prompt(
                "Language:",
                "js",
                {
                    "1": ("js", "JavaScript"),
                    "2": ("ts", "TypeScript"),
                },
            )

            print("")

        styles = _prompt(
            "Styles:",
            "none",
            {
                "1": ("none", "None"),
                "2": ("bootstrap", "Bootstrap"),
                "3": ("tailwind", "Tailwind CSS"),
            },
        )

        print("")

        package_manager = _prompt(
            "Package manager:",
            "npm",
            {
                "1": ("npm", "npm"),
                "2": ("pnpm", "pnpm"),
                "3": ("yarn", "Yarn"),
            },
        )

        print("")

        bundler = _prompt(
            "Bundler:",
            "pyinstaller",
            {
                "1": ("pyinstaller", "PyInstaller"),
                "2": ("nuitka", "Nuitka (smaller binary, requires C compiler)"),
            },
        )

        print("")

    except (KeyboardInterrupt, EOFError):
        print("")
        print("Cancelled.")
        raise SystemExit(0)

    return {
        "name": name,
        "template": template,
        "language": language,
        "styles": styles,
        "package_manager": package_manager,
        "bundler": bundler,
    }


# ─── Shared ──────────────────────────────────────────────────────────────────


def create_app_py(name: str, *, frontend: str) -> str:
    return f'''from vesper import App


app = App(
    title="{name}",
    width=900,
    height=600,
    resizable=True,
    debug=True,
    frontend="{frontend}",
)


@app.command("hello")
def hello(name: str = "World") -> str:
    return f"Hello, {{name}}!"


if __name__ == "__main__":
    app.run()
'''


# ─── Vanilla template ────────────────────────────────────────────────────────


def write_vanilla_package_json(app_dir: Path, styles: str) -> None:
    scripts = {}

    if styles == "tailwind":
        scripts = {
            "dev:css": "tailwindcss -i ./frontend/styles/input.css -o ./frontend/styles/styles.css --watch",
            "build:css": "tailwindcss -i ./frontend/styles/input.css -o ./frontend/styles/styles.css --minify",
        }

    package_json = {
        "name": app_dir.name,
        "version": "0.1.0",
        "private": True,
        "scripts": scripts,
    }

    (app_dir / "package.json").write_text(
        json.dumps(package_json, indent=2) + "\n",
        encoding="utf-8",
    )


def install_bootstrap(app_dir: Path, frontend_dir: Path, *, pm: str = "npm") -> None:
    write_vanilla_package_json(app_dir, "bootstrap")
    pm_add(pm, app_dir, "bootstrap")

    bootstrap_dist = app_dir / "node_modules" / "bootstrap" / "dist"
    vendor_dir = frontend_dir / "vendor" / "bootstrap"
    css_dir = vendor_dir / "css"
    js_dir = vendor_dir / "js"

    css_dir.mkdir(parents=True, exist_ok=True)
    js_dir.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(
        bootstrap_dist / "css" / "bootstrap.min.css",
        css_dir / "bootstrap.min.css",
    )
    shutil.copyfile(
        bootstrap_dist / "js" / "bootstrap.bundle.min.js",
        js_dir / "bootstrap.bundle.min.js",
    )


def install_tailwind(app_dir: Path, frontend_dir: Path, *, pm: str = "npm") -> None:
    write_vanilla_package_json(app_dir, "tailwind")

    styles_dir = frontend_dir / "styles"
    styles_dir.mkdir(parents=True, exist_ok=True)
    (styles_dir / "input.css").write_text('@import "tailwindcss";\n', encoding="utf-8")

    pm_add_dev(pm, app_dir, "tailwindcss", "@tailwindcss/cli")
    pm_run(pm, app_dir, "build:css")


def create_vanilla_index_html(name: str, styles: str) -> str:
    if styles == "none":
        return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{name}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0d0d14;
      color: #e2e4ef;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .container {{ text-align: center; max-width: 520px; padding: 2rem; }}
    .logo {{ width: 80px; height: 80px; margin: 0 auto 1.5rem; display: block; }}
    h1 {{ font-size: 2rem; font-weight: 700; letter-spacing: -.02em; color: #f0f1fa; margin-bottom: .4rem; }}
    .powered-by {{ font-size: .7rem; letter-spacing: .12em; text-transform: uppercase; color: #3e4462; margin-bottom: 2rem; }}
    p {{ font-size: .9rem; color: #6e748f; line-height: 1.7; margin-bottom: 1.75rem; }}
    code {{ font-family: ui-monospace, 'Cascadia Code', monospace; font-size: .85em; color: #a493ff; }}
    button {{
      background: #6a4fd6; color: #fff; border: none; border-radius: 8px;
      padding: .6rem 1.5rem; font-size: .875rem; font-weight: 500;
      cursor: pointer; transition: background .15s;
    }}
    button:hover {{ background: #7c62e8; }}
    #response {{ margin-top: 1rem; min-height: 1.4em; font-size: .875rem; color: #a493ff; }}
  </style>
</head>
<body>
  <div class="container">
    <img class="logo" src="./vesper-icon-dark.svg" alt="Vesper" />
    <h1>{name}</h1>
    <p class="powered-by">Powered by Vesper</p>
    <p>
      Edit <code>frontend/index.html</code> and save to reload.<br>
      Call Python with <code>vesper.invoke()</code>.
    </p>
    <button id="hello-btn">Call Python</button>
    <p id="response"></p>
  </div>
  <!-- VESPER SDK: DO NOT REMOVE. Required for Python <-> JavaScript communication. -->
  <script src="./vesper.js"></script>
  <script>
    document.getElementById('hello-btn').addEventListener('click', async () => {{
      try {{
        const res = await vesper.invoke('hello', {{ name: 'Vesper' }});
        document.getElementById('response').textContent = res;
      }} catch (e) {{
        document.getElementById('response').textContent = e.message;
      }}
    }});
  </script>
</body>
</html>
"""

    if styles == "bootstrap":
        return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{name}</title>
  <link rel="stylesheet" href="./vendor/bootstrap/css/bootstrap.min.css" />
</head>
<body class="bg-light">
  <div class="min-vh-100 d-flex align-items-center justify-content-center">
    <div class="text-center" style="max-width:520px;padding:2rem">
      <img src="./vesper-icon-light.svg" width="80" height="80" alt="Vesper" class="mb-4" />
      <h1 class="fw-bold mb-1">{name}</h1>
      <p class="text-uppercase text-secondary mb-4" style="font-size:.7rem;letter-spacing:.12em">Powered by Vesper</p>
      <p class="text-muted mb-4">
        Edit <code>frontend/index.html</code> and save to reload.<br>
        Call Python with <code>vesper.invoke()</code>.
      </p>
      <button class="btn btn-primary" id="hello-btn">Call Python</button>
      <p class="mt-3 text-primary" id="response"></p>
    </div>
  </div>
  <script src="./vendor/bootstrap/js/bootstrap.bundle.min.js"></script>
  <!-- VESPER SDK: DO NOT REMOVE. Required for Python <-> JavaScript communication. -->
  <script src="./vesper.js"></script>
  <script>
    document.getElementById('hello-btn').addEventListener('click', async () => {{
      try {{
        const res = await vesper.invoke('hello', {{ name: 'Vesper' }});
        document.getElementById('response').textContent = res;
      }} catch (e) {{
        document.getElementById('response').textContent = e.message;
      }}
    }});
  </script>
</body>
</html>
"""

    # tailwind
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{name}</title>
  <link rel="stylesheet" href="./styles/styles.css" />
</head>
<body class="min-h-screen bg-slate-950 text-white flex items-center justify-center">
  <div class="text-center max-w-lg px-8 py-10">
    <img src="./vesper-icon-dark.svg" alt="Vesper" class="w-20 h-20 mx-auto mb-6" />
    <h1 class="text-4xl font-bold tracking-tight mb-1">{name}</h1>
    <p class="text-xs uppercase tracking-widest text-slate-600 mb-8">Powered by Vesper</p>
    <p class="text-slate-400 text-sm leading-relaxed mb-8">
      Edit <code class="text-violet-400 font-mono">frontend/index.html</code> and save to reload.<br>
      Call Python with <code class="text-violet-400 font-mono">vesper.invoke()</code>.
    </p>
    <button id="hello-btn"
      class="bg-violet-600 hover:bg-violet-500 text-white px-6 py-2.5 rounded-lg text-sm font-medium transition-colors cursor-pointer">
      Call Python
    </button>
    <p id="response" class="mt-4 text-violet-400 text-sm min-h-5"></p>
  </div>
  <!-- VESPER SDK: DO NOT REMOVE. Required for Python <-> JavaScript communication. -->
  <script src="./vesper.js"></script>
  <script>
    document.getElementById('hello-btn').addEventListener('click', async () => {{
      try {{
        const res = await vesper.invoke('hello', {{ name: 'Vesper' }});
        document.getElementById('response').textContent = res;
      }} catch (e) {{
        document.getElementById('response').textContent = e.message;
      }}
    }});
  </script>
</body>
</html>
"""


def create_vanilla_app(name: str, *, styles: str, bundler: str, package_manager: str = "npm") -> None:
    app_dir_name = normalize_app_directory_name(name)
    app_dir = Path.cwd() / app_dir_name
    frontend_dir = app_dir / "frontend"

    if app_dir.exists():
        raise FileExistsError(f"Directory already exists: {app_dir}")

    frontend_dir.mkdir(parents=True)

    copy_sdk_to_frontend(frontend_dir)
    icon_variant = "light" if styles == "bootstrap" else "dark"
    _copy_asset(frontend_dir, f"vesper-icon-{icon_variant}.svg")

    (frontend_dir / "index.html").write_text(
        create_vanilla_index_html(name, styles), encoding="utf-8"
    )
    (app_dir / "app.py").write_text(
        create_app_py(name, frontend="frontend/index.html"), encoding="utf-8"
    )

    create_vesper_toml(app_dir, name=name, template="vanilla", styles=styles, bundler=bundler, package_manager=package_manager)

    if styles == "bootstrap":
        install_bootstrap(app_dir, frontend_dir, pm=package_manager)
    elif styles == "tailwind":
        install_tailwind(app_dir, frontend_dir, pm=package_manager)

    print(f"Created Vesper app: {app_dir}")
    print("Template: vanilla")
    print(f"Styles: {styles}")

    print_next_steps(app_dir_name, template="vanilla", styles=styles, bundler=bundler, package_manager=package_manager)


# ─── Vite shared helpers ─────────────────────────────────────────────────────


def create_tsconfig_node_json() -> str:
    """tsconfig covering vite.config.ts — editor-only, not part of the build script."""
    config = {
        "compilerOptions": {
            "composite": True,
            "skipLibCheck": True,
            "module": "ESNext",
            "moduleResolution": "bundler",
            "allowSyntheticDefaultImports": True,
            "strict": True,
        },
        "include": ["vite.config.ts"],
    }
    return json.dumps(config, indent=2) + "\n"


def create_vite_env_dts(*, extra_reference: str | None = None) -> str:
    """
    Ambient types every TS template needs immediately, before `vesper sync-types`
    has ever run: `import.meta.env` (Vite) and `window.vesper` (the SDK script tag
    has no package to ship its own .d.ts from). Declared on the `Window` interface
    rather than as a bare global const so it can never collide with the bare
    `declare const vesper` that `sync-types` writes to src/types/vesper.d.ts —
    that file is for the app's own commands; this one is for the SDK's base surface.
    """
    references = ['/// <reference types="vite/client" />']
    if extra_reference:
        references.insert(0, f'/// <reference types="{extra_reference}" />')

    return "\n".join(references) + """

export {}

declare global {
  interface Window {
    vesper: {
      invoke(command: string, args?: Record<string, unknown>): Promise<unknown>
      on(event: string, handler: (detail: unknown) => void): () => void
      security: { lockdown(): void }
    }
  }
}
"""


def create_vite_index_html(name: str, *, entry: str, mount_id: str) -> str:
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{name}</title>
</head>
<body>
  <div id="{mount_id}"></div>

  <!-- VESPER SDK: DO NOT REMOVE. Required for Python <-> JavaScript communication. -->
  <script src="/vesper.js"></script>
  <script type="module" src="{entry}"></script>
</body>
</html>
"""


# ─── React template ──────────────────────────────────────────────────────────


def create_react_package_json(name: str, styles: str, typescript: bool = False) -> str:
    dependencies: dict = {
        "react": "^18.2.0",
        "react-dom": "^18.2.0",
    }

    dev_dependencies: dict = {
        "@vitejs/plugin-react": "^4.2.0",
        "vite": "^5.0.0",
    }

    if styles == "bootstrap":
        dependencies["bootstrap"] = "^5.3.0"
    elif styles == "tailwind":
        dev_dependencies["tailwindcss"] = "^4.0.0"
        dev_dependencies["@tailwindcss/vite"] = "^4.0.0"

    scripts = {
        "dev": "vite",
        "build": "vite build",
        "preview": "vite preview",
    }

    if typescript:
        dev_dependencies["typescript"] = "^5.4.0"
        dev_dependencies["@types/react"] = "^18.2.66"
        dev_dependencies["@types/react-dom"] = "^18.2.22"
        scripts["build"] = "tsc && vite build"
        scripts["type-check"] = "tsc --noEmit"

    package = {
        "name": name,
        "version": "0.1.0",
        "private": True,
        "type": "module",
        "scripts": scripts,
        "dependencies": dependencies,
        "devDependencies": dev_dependencies,
    }

    return json.dumps(package, indent=2) + "\n"


def create_react_tsconfig_json() -> str:
    config = {
        "compilerOptions": {
            "target": "ES2020",
            "useDefineForClassFields": True,
            "lib": ["ES2020", "DOM", "DOM.Iterable"],
            "module": "ESNext",
            "skipLibCheck": True,
            "moduleResolution": "bundler",
            "allowImportingTsExtensions": True,
            "resolveJsonModule": True,
            "isolatedModules": True,
            "noEmit": True,
            "jsx": "react-jsx",
            "strict": True,
        },
        "include": ["src"],
        "references": [{"path": "./tsconfig.node.json"}],
    }
    return json.dumps(config, indent=2) + "\n"


def create_react_vite_config(styles: str) -> str:
    if styles == "tailwind":
        return """\
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
})
"""
    return """\
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})
"""


def create_react_main_jsx(styles: str, typescript: bool = False) -> str:
    ext = "tsx" if typescript else "jsx"

    lines = [
        "import { StrictMode } from 'react'",
        "import { createRoot } from 'react-dom/client'",
    ]

    if styles == "bootstrap":
        lines.append("import 'bootstrap/dist/css/bootstrap.min.css'")
    else:
        lines.append("import './index.css'")

    lines.append(f"import App from './App.{ext}'")

    # TypeScript's strictNullChecks makes getElementById's return type
    # `HTMLElement | null` — the `!` tells it the mount point is guaranteed
    # to exist, matching how every other Vite + React + TS template does this.
    mount = "document.getElementById('root')!" if typescript else "document.getElementById('root')"

    return "\n".join(lines) + f"""

// Turns off browser affordances (reload, find, right-click menu, zoom) so the
// app feels native rather than like a page in a browser. import.meta.env.DEV
// is Vite's own dev/production flag — true under `vesper dev`, false in a
// production build, regardless of how the frontend is served (this also
// covers App(serve_frontend=True), which security.lockdown()'s own runtime
// heuristic cannot distinguish from `vesper dev` by hostname alone).
// See docs/security-lockdown.md.
if (!import.meta.env.DEV) {{
  window.vesper.security.lockdown()
}}

createRoot({mount}).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
"""


def create_react_app_jsx(name: str, styles: str, typescript: bool = False) -> str:
    if styles == "none":
        content = f"""\
import {{ useState }} from 'react'

function App() {{
  const [message, setMessage] = useState('')

  async function callPython() {{
    try {{
      const result = await window.vesper.invoke('hello', {{ name: 'Vesper' }})
      setMessage(result)
    }} catch (e) {{
      setMessage(e.message)
    }}
  }}

  return (
    <div style={{{{ fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", background: '#0d0d14', color: '#e2e4ef', minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}}}>
      <div style={{{{ textAlign: 'center', maxWidth: '560px', padding: '2rem' }}}}>
        <div style={{{{ display: 'flex', gap: '1.25rem', justifyContent: 'center', alignItems: 'center', marginBottom: '1.75rem' }}}}>
          <img src="/vesper-icon-dark.svg" width="72" height="72" alt="Vesper" />
          <span style={{{{ color: '#2e3352', fontSize: '1.5rem' }}}}>+</span>
          <img src="/react-logo.svg" width="72" height="72" alt="React" />
          <span style={{{{ color: '#2e3352', fontSize: '1.5rem' }}}}>+</span>
          <img src="/vite-logo.svg" width="72" height="72" alt="Vite" />
        </div>
        <h1 style={{{{ fontSize: '2rem', fontWeight: 700, letterSpacing: '-.02em', color: '#f0f1fa', marginBottom: '.4rem' }}}}>
          {name}
        </h1>
        <p style={{{{ fontSize: '.7rem', letterSpacing: '.12em', textTransform: 'uppercase', color: '#3e4462', marginBottom: '2rem' }}}}>
          Vesper + React + Vite
        </p>
        <p style={{{{ fontSize: '.9rem', color: '#6e748f', lineHeight: 1.7, marginBottom: '1.75rem' }}}}>
          Edit <code style={{{{ fontFamily: 'ui-monospace, monospace', color: '#a493ff', fontSize: '.85em' }}}}>src/App.jsx</code> and save to reload.<br />
          Call Python with <code style={{{{ fontFamily: 'ui-monospace, monospace', color: '#a493ff', fontSize: '.85em' }}}}>vesper.invoke()</code>.
        </p>
        <button
          onClick={{callPython}}
          style={{{{ background: '#6a4fd6', color: '#fff', border: 'none', borderRadius: '8px', padding: '.6rem 1.5rem', fontSize: '.875rem', fontWeight: 500, cursor: 'pointer' }}}}
        >
          Call Python
        </button>
        {{message && (
          <p style={{{{ marginTop: '1rem', fontSize: '.875rem', color: '#a493ff' }}}}>{{message}}</p>
        )}}
      </div>
    </div>
  )
}}

export default App
"""

    elif styles == "bootstrap":
        content = f"""\
import {{ useState }} from 'react'

function App() {{
  const [message, setMessage] = useState('')

  async function callPython() {{
    try {{
      const result = await window.vesper.invoke('hello', {{ name: 'Vesper' }})
      setMessage(result)
    }} catch (e) {{
      setMessage(e.message)
    }}
  }}

  return (
    <div className="bg-light min-vh-100 d-flex align-items-center justify-content-center">
      <div className="text-center" style={{{{ maxWidth: '520px', padding: '2rem' }}}}>
        <div className="d-flex gap-3 justify-content-center align-items-center mb-4">
          <img src="/vesper-icon-light.svg" width="64" height="64" alt="Vesper" />
          <span className="text-secondary fs-4">+</span>
          <img src="/react-logo.svg" width="64" height="64" alt="React" />
          <span className="text-secondary fs-4">+</span>
          <img src="/vite-logo.svg" width="64" height="64" alt="Vite" />
        </div>
        <h1 className="fw-bold mb-1">{name}</h1>
        <p className="text-uppercase text-secondary mb-4" style={{{{ fontSize: '.7rem', letterSpacing: '.12em' }}}}>Vesper + React + Vite</p>
        <p className="text-muted mb-4">
          Edit <code>src/App.jsx</code> and save to reload.<br />
          Call Python with <code>vesper.invoke()</code>.
        </p>
        <button className="btn btn-primary" onClick={{callPython}}>Call Python</button>
        {{message && <p className="mt-3 text-primary">{{message}}</p>}}
      </div>
    </div>
  )
}}

export default App
"""

    else:
        # tailwind
        content = f"""\
import {{ useState }} from 'react'

function App() {{
  const [message, setMessage] = useState('')

  async function callPython() {{
    try {{
      const result = await window.vesper.invoke('hello', {{ name: 'Vesper' }})
      setMessage(result)
    }} catch (e) {{
      setMessage(e.message)
    }}
  }}

  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center">
      <div className="text-center max-w-lg px-8 py-10">
        <div className="flex gap-5 justify-center items-center mb-7">
          <img src="/vesper-icon-dark.svg" width="72" height="72" alt="Vesper" />
          <span className="text-slate-700 text-2xl">+</span>
          <img src="/react-logo.svg" width="72" height="72" alt="React" />
          <span className="text-slate-700 text-2xl">+</span>
          <img src="/vite-logo.svg" width="72" height="72" alt="Vite" />
        </div>
        <h1 className="text-4xl font-bold tracking-tight mb-1">{name}</h1>
        <p className="text-xs uppercase tracking-widest text-slate-600 mb-8">Vesper + React + Vite</p>
        <p className="text-slate-400 text-sm leading-relaxed mb-8">
          Edit <code className="text-violet-400 font-mono">src/App.jsx</code> and save to reload.<br />
          Call Python with <code className="text-violet-400 font-mono">vesper.invoke()</code>.
        </p>
        <button
          onClick={{callPython}}
          className="bg-violet-600 hover:bg-violet-500 text-white px-6 py-2.5 rounded-lg text-sm font-medium transition-colors cursor-pointer"
        >
          Call Python
        </button>
        {{message && <p className="mt-4 text-violet-400 text-sm">{{message}}</p>}}
      </div>
    </div>
  )
}}

export default App
"""

    if typescript:
        content = content.replace("src/App.jsx", "src/App.tsx")
        content = content.replace("setMessage(result)", "setMessage(result as string)")
        content = content.replace("setMessage(e.message)", "setMessage((e as Error).message)")

    return content


def create_react_app(name: str, *, styles: str, bundler: str, package_manager: str = "npm", language: str = "js") -> None:
    typescript = language == "ts"
    ext = "tsx" if typescript else "jsx"

    app_dir_name = normalize_app_directory_name(name)
    app_dir = Path.cwd() / app_dir_name
    src_dir = app_dir / "src"
    public_dir = app_dir / "public"

    if app_dir.exists():
        raise FileExistsError(f"Directory already exists: {app_dir}")

    src_dir.mkdir(parents=True)
    public_dir.mkdir(parents=True)

    copy_sdk_to_frontend(public_dir)
    icon_variant = "light" if styles == "bootstrap" else "dark"
    _copy_asset(public_dir, f"vesper-icon-{icon_variant}.svg")
    _copy_asset(public_dir, "react-logo.svg")
    _copy_asset(public_dir, "vite-logo.svg")

    (app_dir / "package.json").write_text(create_react_package_json(app_dir_name, styles, typescript), encoding="utf-8")
    vite_config_name = "vite.config.ts" if typescript else "vite.config.js"
    (app_dir / vite_config_name).write_text(create_react_vite_config(styles), encoding="utf-8")
    (app_dir / "index.html").write_text(
        create_vite_index_html(name, entry=f"/src/main.{ext}", mount_id="root"),
        encoding="utf-8",
    )
    (src_dir / f"main.{ext}").write_text(create_react_main_jsx(styles, typescript), encoding="utf-8")
    (src_dir / f"App.{ext}").write_text(create_react_app_jsx(name, styles, typescript), encoding="utf-8")

    if styles == "tailwind":
        (src_dir / "index.css").write_text('@import "tailwindcss";\n', encoding="utf-8")
    elif styles == "none":
        (src_dir / "index.css").write_text("body { margin: 0; padding: 0; }\n", encoding="utf-8")

    if typescript:
        (app_dir / "tsconfig.json").write_text(create_react_tsconfig_json(), encoding="utf-8")
        (app_dir / "tsconfig.node.json").write_text(create_tsconfig_node_json(), encoding="utf-8")
        (src_dir / "vite-env.d.ts").write_text(create_vite_env_dts(), encoding="utf-8")

    (app_dir / "app.py").write_text(create_app_py(name, frontend="dist/index.html"), encoding="utf-8")

    create_vesper_toml(app_dir, name=name, template="react", styles=styles, bundler=bundler, package_manager=package_manager, language=language)

    print(f"Created Vesper app: {app_dir}")
    print("Template: react")
    print(f"Styles: {styles}")

    print_next_steps(app_dir_name, template="react", styles=styles, bundler=bundler, package_manager=package_manager)


# ─── Vue template ────────────────────────────────────────────────────────────


def create_vue_package_json(name: str, styles: str, typescript: bool = False) -> str:
    dependencies: dict = {
        "vue": "^3.4.0",
    }

    dev_dependencies: dict = {
        "@vitejs/plugin-vue": "^5.0.0",
        "vite": "^5.0.0",
    }

    if styles == "bootstrap":
        dependencies["bootstrap"] = "^5.3.0"
    elif styles == "tailwind":
        dev_dependencies["tailwindcss"] = "^4.0.0"
        dev_dependencies["@tailwindcss/vite"] = "^4.0.0"

    scripts = {
        "dev": "vite",
        "build": "vite build",
        "preview": "vite preview",
    }

    if typescript:
        dev_dependencies["typescript"] = "^5.4.0"
        dev_dependencies["vue-tsc"] = "^2.0.0"
        scripts["build"] = "vue-tsc --noEmit && vite build"
        scripts["type-check"] = "vue-tsc --noEmit"

    package = {
        "name": name,
        "version": "0.1.0",
        "private": True,
        "type": "module",
        "scripts": scripts,
        "dependencies": dependencies,
        "devDependencies": dev_dependencies,
    }

    return json.dumps(package, indent=2) + "\n"


def create_vue_tsconfig_json() -> str:
    config = {
        "compilerOptions": {
            "target": "ES2020",
            "useDefineForClassFields": True,
            "module": "ESNext",
            "lib": ["ES2020", "DOM", "DOM.Iterable"],
            "skipLibCheck": True,
            "moduleResolution": "bundler",
            "allowImportingTsExtensions": True,
            "resolveJsonModule": True,
            "isolatedModules": True,
            "noEmit": True,
            "strict": True,
        },
        "include": ["src/**/*.ts", "src/**/*.d.ts", "src/**/*.vue"],
        "references": [{"path": "./tsconfig.node.json"}],
    }
    return json.dumps(config, indent=2) + "\n"


def create_vue_vite_config(styles: str) -> str:
    if styles == "tailwind":
        return """\
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
  ],
})
"""
    return """\
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
})
"""


def create_vue_main_js(styles: str) -> str:
    lines = ["import { createApp } from 'vue'"]

    if styles == "bootstrap":
        lines.append("import 'bootstrap/dist/css/bootstrap.min.css'")
    else:
        lines.append("import './index.css'")

    lines += [
        "import App from './App.vue'",
        "",
        "// import.meta.env.DEV is Vite's own dev/production flag — see the",
        "// comment in the React template's main.jsx for why this is checked",
        "// instead of security.lockdown()'s own runtime heuristic.",
        "if (!import.meta.env.DEV) {",
        "  window.vesper.security.lockdown()",
        "}",
        "",
        "createApp(App).mount('#app')",
        "",
    ]

    return "\n".join(lines)


def create_vue_app_vue(name: str, styles: str, typescript: bool = False) -> str:
    if styles == "none":
        markup = f"""\
<template>
  <div :style="outer">
    <div :style="inner">
      <div :style="logoRow">
        <img src="/vesper-icon-dark.svg" width="72" height="72" alt="Vesper" />
        <span :style="plus">+</span>
        <img src="/vue-logo.svg" width="72" height="72" alt="Vue" />
        <span :style="plus">+</span>
        <img src="/vite-logo.svg" width="72" height="72" alt="Vite" />
      </div>
      <h1 :style="title">{name}</h1>
      <p :style="subtitle">Vesper + Vue + Vite</p>
      <p :style="desc">
        Edit <code :style="code">src/App.vue</code> and save to reload.<br>
        Call Python with <code :style="code">vesper.invoke()</code>.
      </p>
      <button :style="btn" @click="callPython">Call Python</button>
      <p v-if="message" :style="result">{{{{ message }}}}</p>
    </div>
  </div>
</template>"""

    elif styles == "bootstrap":
        markup = f"""\
<template>
  <div class="bg-light min-vh-100 d-flex align-items-center justify-content-center">
    <div class="text-center" style="max-width:520px;padding:2rem">
      <div class="d-flex gap-3 justify-content-center align-items-center mb-4">
        <img src="/vesper-icon-light.svg" width="64" height="64" alt="Vesper" />
        <span class="text-secondary fs-4">+</span>
        <img src="/vue-logo.svg" width="64" height="64" alt="Vue" />
        <span class="text-secondary fs-4">+</span>
        <img src="/vite-logo.svg" width="64" height="64" alt="Vite" />
      </div>
      <h1 class="fw-bold mb-1">{name}</h1>
      <p class="text-uppercase text-secondary mb-4" style="font-size:.7rem;letter-spacing:.12em">Vesper + Vue + Vite</p>
      <p class="text-muted mb-4">
        Edit <code>src/App.vue</code> and save to reload.<br>
        Call Python with <code>vesper.invoke()</code>.
      </p>
      <button class="btn btn-primary" @click="callPython">Call Python</button>
      <p v-if="message" class="mt-3 text-primary">{{{{ message }}}}</p>
    </div>
  </div>
</template>"""

    else:
        markup = f"""\
<template>
  <div class="min-h-screen bg-slate-950 text-white flex items-center justify-center">
    <div class="text-center max-w-lg px-8 py-10">
      <div class="flex gap-5 justify-center items-center mb-7">
        <img src="/vesper-icon-dark.svg" width="72" height="72" alt="Vesper" />
        <span class="text-slate-700 text-2xl">+</span>
        <img src="/vue-logo.svg" width="72" height="72" alt="Vue" />
        <span class="text-slate-700 text-2xl">+</span>
        <img src="/vite-logo.svg" width="72" height="72" alt="Vite" />
      </div>
      <h1 class="text-4xl font-bold tracking-tight mb-1">{name}</h1>
      <p class="text-xs uppercase tracking-widest text-slate-600 mb-8">Vesper + Vue + Vite</p>
      <p class="text-slate-400 text-sm leading-relaxed mb-8">
        Edit <code class="text-violet-400 font-mono">src/App.vue</code> and save to reload.<br>
        Call Python with <code class="text-violet-400 font-mono">vesper.invoke()</code>.
      </p>
      <button
        class="bg-violet-600 hover:bg-violet-500 text-white px-6 py-2.5 rounded-lg text-sm font-medium transition-colors cursor-pointer"
        @click="callPython"
      >Call Python</button>
      <p v-if="message" class="mt-4 text-violet-400 text-sm">{{{{ message }}}}</p>
    </div>
  </div>
</template>"""

    styles_obj = ""
    if styles == "none":
        # Type-annotated under TS so string literals like 'center' narrow to the
        # CSSProperties union (e.g. TextAlign) instead of widening to `string`,
        # which is all :style="..." bindings accept.
        ann = ": CSSProperties" if typescript else ""
        styles_obj = f"""
const outer{ann} = {{ fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", background: '#0d0d14', color: '#e2e4ef', minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
const inner{ann} = {{ textAlign: 'center', maxWidth: '560px', padding: '2rem' }}
const logoRow{ann} = {{ display: 'flex', gap: '1.25rem', justifyContent: 'center', alignItems: 'center', marginBottom: '1.75rem' }}
const plus{ann} = {{ color: '#2e3352', fontSize: '1.5rem' }}
const title{ann} = {{ fontSize: '2rem', fontWeight: 700, letterSpacing: '-.02em', color: '#f0f1fa', marginBottom: '.4rem' }}
const subtitle{ann} = {{ fontSize: '.7rem', letterSpacing: '.12em', textTransform: 'uppercase', color: '#3e4462', marginBottom: '2rem' }}
const desc{ann} = {{ fontSize: '.9rem', color: '#6e748f', lineHeight: 1.7, marginBottom: '1.75rem' }}
const code{ann} = {{ fontFamily: 'ui-monospace, monospace', color: '#a493ff', fontSize: '.85em' }}
const btn{ann} = {{ background: '#6a4fd6', color: '#fff', border: 'none', borderRadius: '8px', padding: '.6rem 1.5rem', fontSize: '.875rem', fontWeight: 500, cursor: 'pointer' }}
const result{ann} = {{ marginTop: '1rem', fontSize: '.875rem', color: '#a493ff' }}"""

        if typescript:
            styles_obj = "import type { CSSProperties } from 'vue'\n" + styles_obj

    script_tag = "<script setup lang=\"ts\">" if typescript else "<script setup>"
    result_assign = "message.value = result as string" if typescript else "message.value = result"
    catch_assign = "message.value = (e as Error).message" if typescript else "message.value = e.message"

    return f"""\
{script_tag}
import {{ ref }} from 'vue'
{styles_obj}
const message = ref('')

async function callPython() {{
  try {{
    const result = await window.vesper.invoke('hello', {{ name: 'Vesper' }})
    {result_assign}
  }} catch (e) {{
    {catch_assign}
  }}
}}
</script>

{markup}
"""


def create_vue_app(name: str, *, styles: str, bundler: str, package_manager: str = "npm", language: str = "js") -> None:
    typescript = language == "ts"
    ext = "ts" if typescript else "js"

    app_dir_name = normalize_app_directory_name(name)
    app_dir = Path.cwd() / app_dir_name
    src_dir = app_dir / "src"
    public_dir = app_dir / "public"

    if app_dir.exists():
        raise FileExistsError(f"Directory already exists: {app_dir}")

    src_dir.mkdir(parents=True)
    public_dir.mkdir(parents=True)

    copy_sdk_to_frontend(public_dir)
    icon_variant = "light" if styles == "bootstrap" else "dark"
    _copy_asset(public_dir, f"vesper-icon-{icon_variant}.svg")
    _copy_asset(public_dir, "vue-logo.svg")
    _copy_asset(public_dir, "vite-logo.svg")

    (app_dir / "package.json").write_text(create_vue_package_json(app_dir_name, styles, typescript), encoding="utf-8")
    vite_config_name = "vite.config.ts" if typescript else "vite.config.js"
    (app_dir / vite_config_name).write_text(create_vue_vite_config(styles), encoding="utf-8")
    (app_dir / "index.html").write_text(
        create_vite_index_html(name, entry=f"/src/main.{ext}", mount_id="app"),
        encoding="utf-8",
    )
    (src_dir / f"main.{ext}").write_text(create_vue_main_js(styles), encoding="utf-8")
    (src_dir / "App.vue").write_text(create_vue_app_vue(name, styles, typescript), encoding="utf-8")

    if styles == "tailwind":
        (src_dir / "index.css").write_text('@import "tailwindcss";\n', encoding="utf-8")
    elif styles == "none":
        (src_dir / "index.css").write_text("body { margin: 0; padding: 0; }\n", encoding="utf-8")

    if typescript:
        (app_dir / "tsconfig.json").write_text(create_vue_tsconfig_json(), encoding="utf-8")
        (app_dir / "tsconfig.node.json").write_text(create_tsconfig_node_json(), encoding="utf-8")
        (src_dir / "vite-env.d.ts").write_text(create_vite_env_dts(), encoding="utf-8")

    (app_dir / "app.py").write_text(create_app_py(name, frontend="dist/index.html"), encoding="utf-8")

    create_vesper_toml(app_dir, name=name, template="vue", styles=styles, bundler=bundler, package_manager=package_manager, language=language)

    print(f"Created Vesper app: {app_dir}")
    print("Template: vue")
    print(f"Styles: {styles}")

    print_next_steps(app_dir_name, template="vue", styles=styles, bundler=bundler, package_manager=package_manager)


# ─── Svelte template ─────────────────────────────────────────────────────────


def create_svelte_package_json(name: str, styles: str, typescript: bool = False) -> str:
    dependencies: dict = {}

    dev_dependencies: dict = {
        "@sveltejs/vite-plugin-svelte": "^3.0.0",
        "svelte": "^4.2.0",
        "vite": "^5.0.0",
    }

    if styles == "bootstrap":
        dependencies["bootstrap"] = "^5.3.0"
    elif styles == "tailwind":
        dev_dependencies["tailwindcss"] = "^4.0.0"
        dev_dependencies["@tailwindcss/vite"] = "^4.0.0"

    scripts = {
        "dev": "vite",
        "build": "vite build",
        "preview": "vite preview",
    }

    if typescript:
        dev_dependencies["typescript"] = "^5.4.0"
        dev_dependencies["svelte-check"] = "^3.6.0"
        dev_dependencies["@tsconfig/svelte"] = "^5.0.2"
        # Kept separate from "build", matching upstream create-vite: svelte-check
        # is slow enough that gating the build on it is not the ecosystem default.
        scripts["check"] = "svelte-check --tsconfig ./tsconfig.json"

    package: dict = {
        "name": name,
        "version": "0.1.0",
        "private": True,
        "type": "module",
        "scripts": scripts,
        "devDependencies": dev_dependencies,
    }

    if dependencies:
        package["dependencies"] = dependencies

    return json.dumps(package, indent=2) + "\n"


def create_svelte_tsconfig_json() -> str:
    config = {
        "extends": "@tsconfig/svelte/tsconfig.json",
        "compilerOptions": {
            "target": "ESNext",
            "useDefineForClassFields": True,
            "module": "ESNext",
            "resolveJsonModule": True,
        },
        "include": ["src/**/*.d.ts", "src/**/*.ts", "src/**/*.svelte"],
        "references": [{"path": "./tsconfig.node.json"}],
    }
    return json.dumps(config, indent=2) + "\n"


def create_svelte_config_js() -> str:
    return """\
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte'

export default {
  preprocess: vitePreprocess(),
}
"""


def create_svelte_vite_config(styles: str) -> str:
    if styles == "tailwind":
        return """\
import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    svelte(),
    tailwindcss(),
  ],
})
"""
    return """\
import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig({
  plugins: [svelte()],
})
"""


def create_svelte_main_js(styles: str, typescript: bool = False) -> str:
    lines = []

    if styles == "bootstrap":
        lines.append("import 'bootstrap/dist/css/bootstrap.min.css'")
    else:
        lines.append("import './index.css'")

    # TypeScript's strictNullChecks makes getElementById's return type
    # `HTMLElement | null` — the `!` tells it the mount point is guaranteed
    # to exist, matching how the other two templates' main file does this.
    target = "document.getElementById('app')!" if typescript else "document.getElementById('app')"

    lines += [
        "import App from './App.svelte'",
        "",
        "// import.meta.env.DEV is Vite's own dev/production flag — see the",
        "// comment in the React template's main.jsx for why this is checked",
        "// instead of security.lockdown()'s own runtime heuristic.",
        "if (!import.meta.env.DEV) {",
        "  window.vesper.security.lockdown()",
        "}",
        "",
        "new App({",
        f"  target: {target},",
        "})",
        "",
    ]

    return "\n".join(lines)


def create_svelte_app_svelte(name: str, styles: str, typescript: bool = False) -> str:
    if styles == "none":
        markup = f"""\
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d0d14; color: #e2e4ef; min-height: 100vh; display: flex; align-items: center; justify-content: center;">
  <div style="text-align: center; max-width: 560px; padding: 2rem;">
    <div style="display: flex; gap: 1.25rem; justify-content: center; align-items: center; margin-bottom: 1.75rem;">
      <img src="/vesper-icon-dark.svg" width="72" height="72" alt="Vesper" />
      <span style="color: #2e3352; font-size: 1.5rem;">+</span>
      <img src="/svelte-logo.svg" width="72" height="72" alt="Svelte" />
      <span style="color: #2e3352; font-size: 1.5rem;">+</span>
      <img src="/vite-logo.svg" width="72" height="72" alt="Vite" />
    </div>
    <h1 style="font-size: 2rem; font-weight: 700; letter-spacing: -.02em; color: #f0f1fa; margin-bottom: .4rem;">{name}</h1>
    <p style="font-size: .7rem; letter-spacing: .12em; text-transform: uppercase; color: #3e4462; margin-bottom: 2rem;">Vesper + Svelte + Vite</p>
    <p style="font-size: .9rem; color: #6e748f; line-height: 1.7; margin-bottom: 1.75rem;">
      Edit <code style="font-family: ui-monospace, monospace; color: #a493ff; font-size: .85em;">src/App.svelte</code> and save to reload.<br>
      Call Python with <code style="font-family: ui-monospace, monospace; color: #a493ff; font-size: .85em;">vesper.invoke()</code>.
    </p>
    <button on:click={{callPython}}
      style="background: #6a4fd6; color: #fff; border: none; border-radius: 8px; padding: .6rem 1.5rem; font-size: .875rem; font-weight: 500; cursor: pointer;">
      Call Python
    </button>
    {{#if message}}<p style="margin-top: 1rem; font-size: .875rem; color: #a493ff;">{{message}}</p>{{/if}}
  </div>
</div>"""

    elif styles == "bootstrap":
        markup = f"""\
<div class="bg-light min-vh-100 d-flex align-items-center justify-content-center">
  <div class="text-center" style="max-width:520px;padding:2rem">
    <div class="d-flex gap-3 justify-content-center align-items-center mb-4">
      <img src="/vesper-icon-light.svg" width="64" height="64" alt="Vesper" />
      <span class="text-secondary fs-4">+</span>
      <img src="/svelte-logo.svg" width="64" height="64" alt="Svelte" />
      <span class="text-secondary fs-4">+</span>
      <img src="/vite-logo.svg" width="64" height="64" alt="Vite" />
    </div>
    <h1 class="fw-bold mb-1">{name}</h1>
    <p class="text-uppercase text-secondary mb-4" style="font-size:.7rem;letter-spacing:.12em">Vesper + Svelte + Vite</p>
    <p class="text-muted mb-4">
      Edit <code>src/App.svelte</code> and save to reload.<br>
      Call Python with <code>vesper.invoke()</code>.
    </p>
    <button class="btn btn-primary" on:click={{callPython}}>Call Python</button>
    {{#if message}}<p class="mt-3 text-primary">{{message}}</p>{{/if}}
  </div>
</div>"""

    else:
        markup = f"""\
<div class="min-h-screen bg-slate-950 text-white flex items-center justify-center">
  <div class="text-center max-w-lg px-8 py-10">
    <div class="flex gap-5 justify-center items-center mb-7">
      <img src="/vesper-icon-dark.svg" width="72" height="72" alt="Vesper" />
      <span class="text-slate-700 text-2xl">+</span>
      <img src="/svelte-logo.svg" width="72" height="72" alt="Svelte" />
      <span class="text-slate-700 text-2xl">+</span>
      <img src="/vite-logo.svg" width="72" height="72" alt="Vite" />
    </div>
    <h1 class="text-4xl font-bold tracking-tight mb-1">{name}</h1>
    <p class="text-xs uppercase tracking-widest text-slate-600 mb-8">Vesper + Svelte + Vite</p>
    <p class="text-slate-400 text-sm leading-relaxed mb-8">
      Edit <code class="text-violet-400 font-mono">src/App.svelte</code> and save to reload.<br>
      Call Python with <code class="text-violet-400 font-mono">vesper.invoke()</code>.
    </p>
    <button
      class="bg-violet-600 hover:bg-violet-500 text-white px-6 py-2.5 rounded-lg text-sm font-medium transition-colors cursor-pointer"
      on:click={{callPython}}
    >Call Python</button>
    {{#if message}}<p class="mt-4 text-violet-400 text-sm">{{message}}</p>{{/if}}
  </div>
</div>"""

    script_tag = '<script lang="ts">' if typescript else "<script>"
    result_assign = "message = result as string" if typescript else "message = result"
    catch_assign = "message = (e as Error).message" if typescript else "message = e.message"

    return f"""\
{script_tag}
  let message = ''

  async function callPython() {{
    try {{
      const result = await window.vesper.invoke('hello', {{ name: 'Vesper' }})
      {result_assign}
    }} catch (e) {{
      {catch_assign}
    }}
  }}
</script>

{markup}
"""


def create_svelte_app(name: str, *, styles: str, bundler: str, package_manager: str = "npm", language: str = "js") -> None:
    app_dir_name = normalize_app_directory_name(name)
    typescript = language == "ts"
    ext = "ts" if typescript else "js"

    app_dir = Path.cwd() / app_dir_name
    src_dir = app_dir / "src"
    public_dir = app_dir / "public"

    if app_dir.exists():
        raise FileExistsError(f"Directory already exists: {app_dir}")

    src_dir.mkdir(parents=True)
    public_dir.mkdir(parents=True)

    copy_sdk_to_frontend(public_dir)
    icon_variant = "light" if styles == "bootstrap" else "dark"
    _copy_asset(public_dir, f"vesper-icon-{icon_variant}.svg")
    _copy_asset(public_dir, "svelte-logo.svg")
    _copy_asset(public_dir, "vite-logo.svg")

    (app_dir / "package.json").write_text(create_svelte_package_json(app_dir_name, styles, typescript), encoding="utf-8")
    vite_config_name = "vite.config.ts" if typescript else "vite.config.js"
    (app_dir / vite_config_name).write_text(create_svelte_vite_config(styles), encoding="utf-8")
    (app_dir / "index.html").write_text(
        create_vite_index_html(name, entry=f"/src/main.{ext}", mount_id="app"),
        encoding="utf-8",
    )
    (src_dir / f"main.{ext}").write_text(create_svelte_main_js(styles, typescript), encoding="utf-8")
    (src_dir / "App.svelte").write_text(create_svelte_app_svelte(name, styles, typescript), encoding="utf-8")

    if styles == "tailwind":
        (src_dir / "index.css").write_text('@import "tailwindcss";\n', encoding="utf-8")
    elif styles == "none":
        (src_dir / "index.css").write_text("body { margin: 0; padding: 0; }\n", encoding="utf-8")

    if typescript:
        (app_dir / "tsconfig.json").write_text(create_svelte_tsconfig_json(), encoding="utf-8")
        (app_dir / "tsconfig.node.json").write_text(create_tsconfig_node_json(), encoding="utf-8")
        (app_dir / "svelte.config.js").write_text(create_svelte_config_js(), encoding="utf-8")
        (src_dir / "vite-env.d.ts").write_text(create_vite_env_dts(extra_reference="svelte"), encoding="utf-8")

    (app_dir / "app.py").write_text(create_app_py(name, frontend="dist/index.html"), encoding="utf-8")

    create_vesper_toml(app_dir, name=name, template="svelte", styles=styles, bundler=bundler, package_manager=package_manager, language=language)

    print(f"Created Vesper app: {app_dir}")
    print("Template: svelte")
    print(f"Styles: {styles}")

    print_next_steps(app_dir_name, template="svelte", styles=styles, bundler=bundler, package_manager=package_manager)


# ─── Post-init output ────────────────────────────────────────────────────────


def print_nuitka_instructions() -> None:
    print("")
    print("Nuitka requires a C compiler to build your app:")
    print("  Windows: Install Visual Studio Build Tools")
    print("           https://visualstudio.microsoft.com/visual-cpp-build-tools/")
    print("  macOS:   xcode-select --install")
    print("  Linux:   sudo apt install gcc   (Debian/Ubuntu)")
    print("           sudo dnf install gcc   (Fedora)")


def print_next_steps(
    app_dir_name: str,
    *,
    template: str,
    styles: str,
    bundler: str,
    package_manager: str = "npm",
) -> None:
    print("")
    print("Next steps:")
    print(f"  cd {app_dir_name}")

    if template == "vanilla":
        if styles == "tailwind":
            print(f"  {package_manager} run dev:css   # run in a separate terminal to watch for CSS changes")
        print("  vesper run")
    else:
        print(f"  {package_manager} install")
        print("  vesper dev")

    if bundler == "nuitka":
        print_nuitka_instructions()


# ─── Main dispatcher ─────────────────────────────────────────────────────────


def create_app(
    name: str,
    *,
    template: str = "vanilla",
    styles: str = "none",
    bundler: str = "pyinstaller",
    package_manager: str = "npm",
    language: str = "js",
) -> None:
    normalized_template = validate_template(template)
    normalized_styles = validate_styles(styles)
    normalized_bundler = validate_bundler(bundler)
    normalized_pm = validate_package_manager(package_manager)
    normalized_language = validate_language(language)

    if normalized_template == "vanilla" and normalized_language == "ts":
        print("The vanilla template has no build step, so there's no TypeScript variant.")
        print("Continuing with JavaScript.")
        normalized_language = "js"

    if normalized_template == "vanilla":
        create_vanilla_app(name, styles=normalized_styles, bundler=normalized_bundler, package_manager=normalized_pm)
    elif normalized_template == "react":
        create_react_app(name, styles=normalized_styles, bundler=normalized_bundler, package_manager=normalized_pm, language=normalized_language)
    elif normalized_template == "vue":
        create_vue_app(name, styles=normalized_styles, bundler=normalized_bundler, package_manager=normalized_pm, language=normalized_language)
    elif normalized_template == "svelte":
        create_svelte_app(name, styles=normalized_styles, bundler=normalized_bundler, package_manager=normalized_pm, language=normalized_language)
    else:
        raise RuntimeError(f"Unhandled template: {normalized_template}")


# ─── CLI ─────────────────────────────────────────────────────────────────────


def add_init_parser(subparsers: argparse._SubParsersAction) -> None:
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a new Vesper project."
    )

    init_subparsers = init_parser.add_subparsers(dest="init_target")

    init_app_parser = init_subparsers.add_parser(
        "app",
        help="Create a new Vesper app. Run without flags for interactive setup."
    )

    init_app_parser.add_argument(
        "--name",
        default=None,
        help="Name of the app to create.",
    )

    init_app_parser.add_argument(
        "--template",
        default=None,
        help="JS template to use. Available: vanilla (default), react, vue, svelte.",
    )

    init_app_parser.add_argument(
        "--typescript",
        "--ts",
        dest="typescript",
        action="store_true",
        default=None,
        help="Generate the framework template in TypeScript instead of JavaScript "
        "(default). Has no effect with --template vanilla.",
    )

    init_app_parser.add_argument(
        "--styles",
        default=None,
        help="Frontend styles. Available: none (default), bootstrap, tailwind.",
    )

    init_app_parser.add_argument(
        "--bundler",
        default=None,
        help="Packaging bundler. Available: pyinstaller (default), nuitka.",
    )

    init_app_parser.add_argument(
        "--package-manager",
        "--pm",
        dest="package_manager",
        default=None,
        help="Package manager. Available: npm (default), pnpm, yarn.",
    )


def handle_init(args: argparse.Namespace) -> bool:
    if args.command != "init" or args.init_target != "app":
        return False

    no_flags = (
        args.name is None
        and args.template is None
        and args.styles is None
        and getattr(args, "bundler", None) is None
        and getattr(args, "package_manager", None) is None
        and getattr(args, "typescript", None) is None
    )

    if no_flags:
        config = run_wizard()
    else:
        config = {
            "name": args.name or "my-vesper-app",
            "template": args.template or "vanilla",
            "language": "ts" if getattr(args, "typescript", None) else "js",
            "styles": args.styles or "none",
            "bundler": getattr(args, "bundler", None) or "pyinstaller",
            "package_manager": getattr(args, "package_manager", None) or "npm",
        }

    try:
        create_app(
            config["name"],
            template=config["template"],
            styles=config["styles"],
            bundler=config["bundler"],
            package_manager=config["package_manager"],
            language=config.get("language", "js"),
        )
    except FileExistsError as e:
        print(str(e))
        raise SystemExit(1)

    return True
