import json

import pytest
from vesper.cli import build_parser
from vesper.commands.init import (
    create_app,
    create_react_app,
    create_react_app_jsx,
    create_react_main_jsx,
    create_svelte_app,
    create_svelte_main_js,
    create_vite_index_html,
    create_vue_app,
    create_vue_main_js,
    handle_init,
    normalize_app_directory_name,
)


# ─── normalize_app_directory_name ────────────────────────────────────────────


def test_normalize_lowercases():
    assert normalize_app_directory_name("MyApp") == "myapp"


def test_normalize_replaces_spaces():
    assert normalize_app_directory_name("my app") == "my-app"


def test_normalize_strips_whitespace():
    assert normalize_app_directory_name("  my-app  ") == "my-app"


def test_normalize_empty_raises():
    with pytest.raises(ValueError):
        normalize_app_directory_name("")


def test_normalize_whitespace_only_raises():
    with pytest.raises(ValueError):
        normalize_app_directory_name("   ")


# ─── create_vite_index_html ───────────────────────────────────────────────────


def test_vite_index_html_has_mount_div():
    html = create_vite_index_html("My App", entry="/src/main.jsx", mount_id="root")
    assert '<div id="root"></div>' in html


def test_vite_index_html_has_entry_script():
    html = create_vite_index_html("My App", entry="/src/main.jsx", mount_id="root")
    assert 'src="/src/main.jsx"' in html


def test_vite_index_html_has_vesper_sdk():
    html = create_vite_index_html("My App", entry="/src/main.jsx", mount_id="root")
    assert 'src="/vesper.js"' in html


def test_vite_index_html_has_title():
    html = create_vite_index_html("My App", entry="/src/main.jsx", mount_id="root")
    assert "<title>My App</title>" in html


# ─── React main.jsx ───────────────────────────────────────────────────────────


def test_react_main_none_imports_index_css():
    main = create_react_main_jsx("none")
    assert "import './index.css'" in main


def test_react_main_tailwind_imports_index_css():
    main = create_react_main_jsx("tailwind")
    assert "import './index.css'" in main


def test_react_main_bootstrap_imports_bootstrap():
    main = create_react_main_jsx("bootstrap")
    assert "import 'bootstrap/dist/css/bootstrap.min.css'" in main


def test_react_main_bootstrap_no_index_css():
    main = create_react_main_jsx("bootstrap")
    assert "import './index.css'" not in main


# ─── React App.jsx ────────────────────────────────────────────────────────────


def test_react_app_jsx_none_has_dark_background():
    jsx = create_react_app_jsx("my-app", "none")
    assert "#0d0d14" in jsx


def test_react_app_jsx_none_has_invoke_call():
    jsx = create_react_app_jsx("my-app", "none")
    assert "vesper.invoke" in jsx


# ─── Vue main.js ─────────────────────────────────────────────────────────────


def test_vue_main_none_imports_index_css():
    main = create_vue_main_js("none")
    assert "import './index.css'" in main


def test_vue_main_tailwind_imports_index_css():
    main = create_vue_main_js("tailwind")
    assert "import './index.css'" in main


def test_vue_main_bootstrap_imports_bootstrap():
    main = create_vue_main_js("bootstrap")
    assert "import 'bootstrap/dist/css/bootstrap.min.css'" in main


# ─── Svelte main.js ──────────────────────────────────────────────────────────


def test_svelte_main_none_imports_index_css():
    main = create_svelte_main_js("none")
    assert "import './index.css'" in main


def test_svelte_main_tailwind_imports_index_css():
    main = create_svelte_main_js("tailwind")
    assert "import './index.css'" in main


def test_svelte_main_bootstrap_imports_bootstrap():
    main = create_svelte_main_js("bootstrap")
    assert "import 'bootstrap/dist/css/bootstrap.min.css'" in main


# ─── React scaffold (filesystem) ─────────────────────────────────────────────


def test_react_none_creates_index_css(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_react_app("my-app", styles="none", bundler="pyinstaller", package_manager="npm")
    css = (tmp_path / "my-app" / "src" / "index.css").read_text(encoding="utf-8")
    assert "margin: 0" in css
    assert "padding: 0" in css


def test_react_tailwind_creates_tailwind_css(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_react_app("my-app", styles="tailwind", bundler="pyinstaller", package_manager="npm")
    css = (tmp_path / "my-app" / "src" / "index.css").read_text(encoding="utf-8")
    assert "tailwindcss" in css


def test_react_bootstrap_no_index_css(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_react_app("my-app", styles="bootstrap", bundler="pyinstaller", package_manager="npm")
    assert not (tmp_path / "my-app" / "src" / "index.css").exists()


def test_react_creates_vesper_toml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_react_app("my-app", styles="none", bundler="pyinstaller", package_manager="npm")
    toml = (tmp_path / "my-app" / "vesper.toml").read_text(encoding="utf-8")
    assert 'template = "react"' in toml
    assert 'styles = "none"' in toml
    assert 'package_manager = "npm"' in toml
    assert 'bundler = "pyinstaller"' in toml


def test_react_creates_app_py(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_react_app("my-app", styles="none", bundler="pyinstaller", package_manager="npm")
    app_py = (tmp_path / "my-app" / "app.py").read_text(encoding="utf-8")
    assert "from vesper import App" in app_py
    assert 'frontend="dist/index.html"' in app_py


def test_react_copies_vesper_sdk(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_react_app("my-app", styles="none", bundler="pyinstaller", package_manager="npm")
    assert (tmp_path / "my-app" / "public" / "vesper.js").exists()


# ─── Vue scaffold (filesystem) ───────────────────────────────────────────────


def test_vue_none_creates_index_css(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_vue_app("my-app", styles="none", bundler="pyinstaller", package_manager="npm")
    css = (tmp_path / "my-app" / "src" / "index.css").read_text(encoding="utf-8")
    assert "margin: 0" in css


def test_vue_creates_vesper_toml_with_correct_template(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_vue_app("my-app", styles="none", bundler="pyinstaller", package_manager="npm")
    toml = (tmp_path / "my-app" / "vesper.toml").read_text(encoding="utf-8")
    assert 'template = "vue"' in toml


# ─── Svelte scaffold (filesystem) ────────────────────────────────────────────


def test_svelte_none_creates_index_css(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_svelte_app("my-app", styles="none", bundler="pyinstaller", package_manager="npm")
    css = (tmp_path / "my-app" / "src" / "index.css").read_text(encoding="utf-8")
    assert "margin: 0" in css


def test_svelte_creates_vesper_toml_with_correct_template(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_svelte_app("my-app", styles="none", bundler="pyinstaller", package_manager="npm")
    toml = (tmp_path / "my-app" / "vesper.toml").read_text(encoding="utf-8")
    assert 'template = "svelte"' in toml


# ─── TypeScript scaffold: JS is still the default ────────────────────────────


@pytest.mark.parametrize(
    ("creator", "ext"),
    [
        (create_react_app, "jsx"),
        (create_vue_app, "js"),
        (create_svelte_app, "js"),
    ],
)
def test_default_language_is_js(tmp_path, monkeypatch, creator, ext):
    monkeypatch.chdir(tmp_path)
    creator("my-app", styles="none", bundler="pyinstaller", package_manager="npm")
    app_dir = tmp_path / "my-app"

    assert (app_dir / "src" / f"main.{ext}").exists()
    assert (app_dir / "vite.config.js").exists()
    assert not (app_dir / "tsconfig.json").exists()
    assert not (app_dir / "vite.config.ts").exists()

    package = json.loads((app_dir / "package.json").read_text(encoding="utf-8"))
    assert "typescript" not in package.get("devDependencies", {})


@pytest.mark.parametrize("creator", [create_react_app, create_vue_app, create_svelte_app])
def test_default_language_omits_vesper_toml_key(tmp_path, monkeypatch, creator):
    monkeypatch.chdir(tmp_path)
    creator("my-app", styles="none", bundler="pyinstaller", package_manager="npm")
    toml = (tmp_path / "my-app" / "vesper.toml").read_text(encoding="utf-8")
    assert "language" not in toml


# ─── TypeScript scaffold: React ───────────────────────────────────────────────


def test_react_typescript_creates_tsx_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_react_app("my-app", styles="none", bundler="pyinstaller", package_manager="npm", language="ts")
    app_dir = tmp_path / "my-app"

    assert (app_dir / "src" / "main.tsx").exists()
    assert (app_dir / "src" / "App.tsx").exists()
    assert (app_dir / "src" / "vite-env.d.ts").exists()
    assert (app_dir / "vite.config.ts").exists()
    assert (app_dir / "tsconfig.json").exists()
    assert (app_dir / "tsconfig.node.json").exists()
    assert not (app_dir / "src" / "main.jsx").exists()
    assert not (app_dir / "vite.config.js").exists()


def test_react_typescript_package_json_has_typescript(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_react_app("my-app", styles="none", bundler="pyinstaller", package_manager="npm", language="ts")
    package = json.loads((tmp_path / "my-app" / "package.json").read_text(encoding="utf-8"))
    assert "typescript" in package["devDependencies"]
    assert package["scripts"]["build"] == "tsc && vite build"


def test_react_typescript_tsconfig_includes_src(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_react_app("my-app", styles="none", bundler="pyinstaller", package_manager="npm", language="ts")
    tsconfig = json.loads((tmp_path / "my-app" / "tsconfig.json").read_text(encoding="utf-8"))
    # sync-types writes src/types/vesper.d.ts — this must be reachable with no
    # further tsconfig changes.
    assert "src" in tsconfig["include"]


def test_react_typescript_vesper_toml_records_language(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_react_app("my-app", styles="none", bundler="pyinstaller", package_manager="npm", language="ts")
    toml = (tmp_path / "my-app" / "vesper.toml").read_text(encoding="utf-8")
    assert 'language = "ts"' in toml


# ─── TypeScript scaffold: Vue ─────────────────────────────────────────────────


def test_vue_typescript_creates_ts_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_vue_app("my-app", styles="none", bundler="pyinstaller", package_manager="npm", language="ts")
    app_dir = tmp_path / "my-app"

    assert (app_dir / "src" / "main.ts").exists()
    assert (app_dir / "src" / "App.vue").exists()
    assert (app_dir / "src" / "vite-env.d.ts").exists()
    assert (app_dir / "vite.config.ts").exists()
    assert (app_dir / "tsconfig.json").exists()
    assert not (app_dir / "src" / "main.js").exists()

    script_setup = (app_dir / "src" / "App.vue").read_text(encoding="utf-8")
    assert '<script setup lang="ts">' in script_setup


def test_vue_typescript_package_json_has_vue_tsc(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_vue_app("my-app", styles="none", bundler="pyinstaller", package_manager="npm", language="ts")
    package = json.loads((tmp_path / "my-app" / "package.json").read_text(encoding="utf-8"))
    assert "vue-tsc" in package["devDependencies"]
    assert package["scripts"]["build"] == "vue-tsc --noEmit && vite build"


# ─── TypeScript scaffold: Svelte ──────────────────────────────────────────────


def test_svelte_typescript_creates_ts_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_svelte_app("my-app", styles="none", bundler="pyinstaller", package_manager="npm", language="ts")
    app_dir = tmp_path / "my-app"

    assert (app_dir / "src" / "main.ts").exists()
    assert (app_dir / "src" / "App.svelte").exists()
    assert (app_dir / "src" / "vite-env.d.ts").exists()
    assert (app_dir / "vite.config.ts").exists()
    assert (app_dir / "tsconfig.json").exists()
    assert (app_dir / "svelte.config.js").exists()
    assert not (app_dir / "src" / "main.js").exists()

    script = (app_dir / "src" / "App.svelte").read_text(encoding="utf-8")
    assert '<script lang="ts">' in script


def test_svelte_typescript_package_json_has_svelte_check(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_svelte_app("my-app", styles="none", bundler="pyinstaller", package_manager="npm", language="ts")
    package = json.loads((tmp_path / "my-app" / "package.json").read_text(encoding="utf-8"))
    assert "svelte-check" in package["devDependencies"]
    assert package["scripts"]["check"] == "svelte-check --tsconfig ./tsconfig.json"


# ─── create_app: vanilla + TypeScript ────────────────────────────────────────


def test_create_app_vanilla_typescript_falls_back_to_js(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    create_app("my-app", template="vanilla", styles="none", bundler="pyinstaller", package_manager="npm", language="ts")

    app_dir = tmp_path / "my-app"
    assert (app_dir / "frontend" / "index.html").exists()
    assert not (app_dir / "tsconfig.json").exists()

    out = capsys.readouterr().out
    assert "no TypeScript variant" in out or "no build step" in out


def test_create_app_react_typescript(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_app("my-app", template="react", styles="none", bundler="pyinstaller", package_manager="npm", language="ts")
    assert (tmp_path / "my-app" / "src" / "App.tsx").exists()


# ─── CLI: --typescript / --ts flag ────────────────────────────────────────────


def test_cli_typescript_flag_persists_in_vesper_toml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    parser = build_parser()
    args = parser.parse_args(
        ["init", "app", "--name", "my-app", "--template", "react", "--typescript"]
    )
    handle_init(args)

    toml = (tmp_path / "my-app" / "vesper.toml").read_text(encoding="utf-8")
    assert 'language = "ts"' in toml


def test_cli_ts_alias_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    parser = build_parser()
    args = parser.parse_args(["init", "app", "--name", "my-app", "--template", "vue", "--ts"])
    handle_init(args)

    assert (tmp_path / "my-app" / "src" / "main.ts").exists()


def test_cli_no_typescript_flag_defaults_to_js(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    parser = build_parser()
    args = parser.parse_args(["init", "app", "--name", "my-app", "--template", "react"])
    handle_init(args)

    assert (tmp_path / "my-app" / "src" / "main.jsx").exists()
    assert not (tmp_path / "my-app" / "tsconfig.json").exists()