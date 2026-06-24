import pytest
from vesper.commands.init import (
    create_react_app,
    create_react_app_jsx,
    create_react_main_jsx,
    create_svelte_app,
    create_svelte_main_js,
    create_vite_index_html,
    create_vue_app,
    create_vue_main_js,
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