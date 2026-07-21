"""Tests for vesper doctor improvements — Node.js, PM, and vesper.toml schema checks."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vesper.commands.doctor import (
    _PROJECT_VALID_KEYS,
    _PROJECT_VALID_VALUES,
    _candidate_backends,
    _detect_webview_backend,
    doctor,
)


@pytest.fixture(autouse=True)
def stub_webview_backend():
    """
    Keep doctor() hermetic.

    The WebView backend check probes real system libraries (GTK/WebKit, PyObjC,
    pythonnet), so without this every doctor() test would depend on what happens to be
    installed on the machine running them. Tests that exercise the check itself call
    _detect_webview_backend directly instead.
    """
    with patch(
        "vesper.commands.doctor._detect_webview_backend",
        return_value=(True, "WebView backend available: stub", None),
    ):
        yield


def _run_doctor(tmp_path: Path, *, monkeypatch, node_version: str | None = "v20.0.0", pm: str = "npm"):
    """Helper that runs doctor() with a minimal project dir and mocked Node/npm."""
    monkeypatch.chdir(tmp_path)

    # minimal valid project
    (tmp_path / "app.py").write_text("")
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    index = frontend / "index.html"
    index.write_text('<script src="./vesper.js"></script></body>')
    (frontend / "vesper.js").write_text("")

    def fake_which(name):
        if name == "node":
            return "/usr/bin/node" if node_version else None
        if name == pm:
            return f"/usr/bin/{pm}"
        return None

    def fake_run(cmd, **kwargs):
        m = MagicMock()
        m.returncode = 0
        m.stdout = node_version or ""
        return m

    with patch("vesper.commands.doctor.shutil.which", side_effect=fake_which), \
         patch("vesper.commands.doctor.subprocess.run", side_effect=fake_run), \
         patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"):
        return doctor


# ── Node.js version ───────────────────────────────────────────────────────────


def test_node_ok_when_v18(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("")
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text('<script src="./vesper.js"></script></body>')
    (frontend / "vesper.js").write_text("")

    def fake_which(name):
        return f"/usr/bin/{name}" if name in ("node", "npm") else None

    def fake_run(cmd, **kwargs):
        m = MagicMock()
        m.returncode = 0
        m.stdout = "v18.0.0"
        return m

    with patch("vesper.commands.doctor.shutil.which", side_effect=fake_which), \
         patch("vesper.commands.doctor.subprocess.run", side_effect=fake_run), \
         patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"):
        doctor()

    out = capsys.readouterr().out
    assert "[OK] Node.js version: v18.0.0" in out


def test_node_fail_when_v16(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("")
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text('<script src="./vesper.js"></script></body>')
    (frontend / "vesper.js").write_text("")

    def fake_which(name):
        return f"/usr/bin/{name}" if name in ("node", "npm") else None

    def fake_run(cmd, **kwargs):
        m = MagicMock()
        m.returncode = 0
        m.stdout = "v16.0.0"
        return m

    with patch("vesper.commands.doctor.shutil.which", side_effect=fake_which), \
         patch("vesper.commands.doctor.subprocess.run", side_effect=fake_run), \
         patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"):
        with pytest.raises(SystemExit):
            doctor()

    out = capsys.readouterr().out
    assert "[FAIL] Node.js version: v16.0.0" in out


def test_node_fail_when_not_installed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("")
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text('<script src="./vesper.js"></script></body>')
    (frontend / "vesper.js").write_text("")

    def fake_which(name):
        if name == "npm":
            return "/usr/bin/npm"
        return None

    with patch("vesper.commands.doctor.shutil.which", side_effect=fake_which), \
         patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"):
        with pytest.raises(SystemExit):
            doctor()

    out = capsys.readouterr().out
    assert "[FAIL] Node.js version: not found" in out


# ── Package manager ───────────────────────────────────────────────────────────


def test_pm_ok_when_npm_available(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("")
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text('<script src="./vesper.js"></script></body>')
    (frontend / "vesper.js").write_text("")

    def fake_which(name):
        return f"/usr/bin/{name}" if name in ("node", "npm") else None

    def fake_run(cmd, **kwargs):
        m = MagicMock()
        m.returncode = 0
        m.stdout = "v20.0.0"
        return m

    with patch("vesper.commands.doctor.shutil.which", side_effect=fake_which), \
         patch("vesper.commands.doctor.subprocess.run", side_effect=fake_run), \
         patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"):
        doctor()

    out = capsys.readouterr().out
    assert "[OK] Package manager available: npm" in out


def test_pm_uses_toml_package_manager(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("")
    (tmp_path / "vesper.toml").write_text('[project]\npackage_manager = "pnpm"\n')
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text('<script src="./vesper.js"></script></body>')
    (frontend / "vesper.js").write_text("")

    def fake_which(name):
        return f"/usr/bin/{name}" if name in ("node", "pnpm") else None

    def fake_run(cmd, **kwargs):
        m = MagicMock()
        m.returncode = 0
        m.stdout = "v20.0.0"
        return m

    with patch("vesper.commands.doctor.shutil.which", side_effect=fake_which), \
         patch("vesper.commands.doctor.subprocess.run", side_effect=fake_run), \
         patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"):
        doctor()

    out = capsys.readouterr().out
    assert "[OK] Package manager available: pnpm" in out


def test_pm_fail_when_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("")
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text('<script src="./vesper.js"></script></body>')
    (frontend / "vesper.js").write_text("")

    def fake_which(name):
        return "/usr/bin/node" if name == "node" else None

    def fake_run(cmd, **kwargs):
        m = MagicMock()
        m.returncode = 0
        m.stdout = "v20.0.0"
        return m

    with patch("vesper.commands.doctor.shutil.which", side_effect=fake_which), \
         patch("vesper.commands.doctor.subprocess.run", side_effect=fake_run), \
         patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"):
        with pytest.raises(SystemExit):
            doctor()

    out = capsys.readouterr().out
    assert "[FAIL] Package manager not found: npm" in out


# ── vesper.toml schema ────────────────────────────────────────────────────────


def test_toml_valid_schema_passes(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("")
    (tmp_path / "vesper.toml").write_text(
        '[project]\nname = "my-app"\ntemplate = "react"\nbundler = "pyinstaller"\n'
    )
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text('<script src="./vesper.js"></script></body>')
    (frontend / "vesper.js").write_text("")

    def fake_which(name):
        return f"/usr/bin/{name}" if name in ("node", "npm") else None

    def fake_run(cmd, **kwargs):
        m = MagicMock()
        m.returncode = 0
        m.stdout = "v20.0.0"
        return m

    with patch("vesper.commands.doctor.shutil.which", side_effect=fake_which), \
         patch("vesper.commands.doctor.subprocess.run", side_effect=fake_run), \
         patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"):
        doctor()

    out = capsys.readouterr().out
    assert "[OK] vesper.toml schema is valid" in out


def test_toml_unknown_key_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("")
    (tmp_path / "vesper.toml").write_text('[project]\nunknown_key = "bad"\n')
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text('<script src="./vesper.js"></script></body>')
    (frontend / "vesper.js").write_text("")

    def fake_which(name):
        return f"/usr/bin/{name}" if name in ("node", "npm") else None

    def fake_run(cmd, **kwargs):
        m = MagicMock()
        m.returncode = 0
        m.stdout = "v20.0.0"
        return m

    with patch("vesper.commands.doctor.shutil.which", side_effect=fake_which), \
         patch("vesper.commands.doctor.subprocess.run", side_effect=fake_run), \
         patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"):
        with pytest.raises(SystemExit):
            doctor()

    out = capsys.readouterr().out
    assert "unknown key 'unknown_key'" in out


def test_toml_invalid_template_value_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("")
    (tmp_path / "vesper.toml").write_text('[project]\ntemplate = "angular"\n')
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text('<script src="./vesper.js"></script></body>')
    (frontend / "vesper.js").write_text("")

    def fake_which(name):
        return f"/usr/bin/{name}" if name in ("node", "npm") else None

    def fake_run(cmd, **kwargs):
        m = MagicMock()
        m.returncode = 0
        m.stdout = "v20.0.0"
        return m

    with patch("vesper.commands.doctor.shutil.which", side_effect=fake_which), \
         patch("vesper.commands.doctor.subprocess.run", side_effect=fake_run), \
         patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"):
        with pytest.raises(SystemExit):
            doctor()

    out = capsys.readouterr().out
    assert "invalid value for 'template': 'angular'" in out


def test_no_toml_does_not_report_schema_check(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("")
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text('<script src="./vesper.js"></script></body>')
    (frontend / "vesper.js").write_text("")

    def fake_which(name):
        return f"/usr/bin/{name}" if name in ("node", "npm") else None

    def fake_run(cmd, **kwargs):
        m = MagicMock()
        m.returncode = 0
        m.stdout = "v20.0.0"
        return m

    with patch("vesper.commands.doctor.shutil.which", side_effect=fake_which), \
         patch("vesper.commands.doctor.subprocess.run", side_effect=fake_run), \
         patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"):
        doctor()

    out = capsys.readouterr().out
    assert "vesper.toml" not in out


# ── Constants ─────────────────────────────────────────────────────────────────


def test_toml_valid_keys_set():
    assert "name" in _PROJECT_VALID_KEYS
    assert "template" in _PROJECT_VALID_KEYS
    assert "bundler" in _PROJECT_VALID_KEYS
    assert "version" in _PROJECT_VALID_KEYS


def test_toml_valid_template_values():
    assert _PROJECT_VALID_VALUES["template"] == {"vanilla", "react", "vue", "svelte"}


def test_toml_valid_bundler_values():
    assert _PROJECT_VALID_VALUES["bundler"] == {"pyinstaller", "nuitka"}


# ── [update] section ──────────────────────────────────────────────────────────


def _make_project(tmp_path, monkeypatch, toml_content):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("")
    (tmp_path / "vesper.toml").write_text(toml_content)
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text('<script src="./vesper.js"></script></body>')
    (frontend / "vesper.js").write_text("")

    def fake_which(name):
        return f"/usr/bin/{name}" if name in ("node", "npm") else None

    def fake_run(cmd, **kwargs):
        m = MagicMock()
        m.returncode = 0
        m.stdout = "v20.0.0"
        return m

    return fake_which, fake_run


def test_toml_update_section_valid(tmp_path, monkeypatch, capsys):
    fake_which, fake_run = _make_project(
        tmp_path, monkeypatch,
        '[project]\nname = "app"\nversion = "1.0.0"\n\n[update]\ncheck_url = "https://example.com/manifest.json"\n',
    )
    with patch("vesper.commands.doctor.shutil.which", side_effect=fake_which), \
         patch("vesper.commands.doctor.subprocess.run", side_effect=fake_run), \
         patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"):
        doctor()
    out = capsys.readouterr().out
    assert "[OK] vesper.toml schema is valid" in out


def test_toml_update_check_url_without_version_fails(tmp_path, monkeypatch, capsys):
    fake_which, fake_run = _make_project(
        tmp_path, monkeypatch,
        '[project]\nname = "app"\n\n[update]\ncheck_url = "https://example.com/manifest.json"\n',
    )
    with patch("vesper.commands.doctor.shutil.which", side_effect=fake_which), \
         patch("vesper.commands.doctor.subprocess.run", side_effect=fake_run), \
         patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"):
        with pytest.raises(SystemExit):
            doctor()
    out = capsys.readouterr().out
    assert "version is missing" in out


def test_toml_update_unknown_key_fails(tmp_path, monkeypatch, capsys):
    fake_which, fake_run = _make_project(
        tmp_path, monkeypatch,
        '[project]\nname = "app"\nversion = "1.0.0"\n\n[update]\nbad_key = "x"\n',
    )
    with patch("vesper.commands.doctor.shutil.which", side_effect=fake_which), \
         patch("vesper.commands.doctor.subprocess.run", side_effect=fake_run), \
         patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"):
        with pytest.raises(SystemExit):
            doctor()
    out = capsys.readouterr().out
    assert "[update] unknown key 'bad_key'" in out


# ── WebView backend detection ─────────────────────────────────────────────────


def test_backend_order_linux_prefers_gtk(monkeypatch):
    monkeypatch.setattr("vesper.commands.doctor.platform.system", lambda: "Linux")
    monkeypatch.delenv("PYWEBVIEW_GUI", raising=False)
    monkeypatch.delenv("KDE_FULL_SESSION", raising=False)
    assert _candidate_backends() == ["gtk", "qt"]


def test_backend_order_linux_kde_prefers_qt(monkeypatch):
    monkeypatch.setattr("vesper.commands.doctor.platform.system", lambda: "Linux")
    monkeypatch.delenv("PYWEBVIEW_GUI", raising=False)
    monkeypatch.setenv("KDE_FULL_SESSION", "true")
    assert _candidate_backends() == ["qt", "gtk"]


def test_backend_order_respects_pywebview_gui_env(monkeypatch):
    monkeypatch.setattr("vesper.commands.doctor.platform.system", lambda: "Linux")
    monkeypatch.setenv("PYWEBVIEW_GUI", "qt")
    assert _candidate_backends() == ["qt", "gtk"]


def test_backend_order_macos_prefers_cocoa(monkeypatch):
    monkeypatch.setattr("vesper.commands.doctor.platform.system", lambda: "Darwin")
    monkeypatch.delenv("PYWEBVIEW_GUI", raising=False)
    monkeypatch.delenv("KDE_FULL_SESSION", raising=False)
    assert _candidate_backends() == ["cocoa", "qt"]


def test_backend_order_windows_is_winforms(monkeypatch):
    monkeypatch.setattr("vesper.commands.doctor.platform.system", lambda: "Windows")
    monkeypatch.delenv("PYWEBVIEW_GUI", raising=False)
    monkeypatch.delenv("KDE_FULL_SESSION", raising=False)
    assert _candidate_backends() == ["winforms"]


def test_backend_detected_when_import_succeeds(monkeypatch):
    monkeypatch.setattr("vesper.commands.doctor.platform.system", lambda: "Linux")
    monkeypatch.delenv("PYWEBVIEW_GUI", raising=False)
    monkeypatch.delenv("KDE_FULL_SESSION", raising=False)
    monkeypatch.setattr(
        "vesper.commands.doctor.importlib.import_module", lambda name: MagicMock()
    )

    ok, message, fix = _detect_webview_backend()
    assert ok is True
    assert "GTK / WebKit2" in message
    assert fix is None


def test_backend_missing_reports_platform_fix(monkeypatch):
    """The Linux failure a fresh clone hits: pywebview installed, no GTK bindings."""
    monkeypatch.setattr("vesper.commands.doctor.platform.system", lambda: "Linux")
    monkeypatch.delenv("PYWEBVIEW_GUI", raising=False)
    monkeypatch.delenv("KDE_FULL_SESSION", raising=False)

    def boom(name):
        raise ImportError("No module named 'gi'")

    monkeypatch.setattr("vesper.commands.doctor.importlib.import_module", boom)

    ok, message, fix = _detect_webview_backend()
    assert ok is False
    assert "none available" in message
    assert "--system-site-packages" in fix
    assert "gir1.2-webkit2-4.1" in fix


def test_backend_probe_survives_non_import_errors(monkeypatch):
    """gi.require_version raises ValueError, not ImportError."""
    monkeypatch.setattr("vesper.commands.doctor.platform.system", lambda: "Linux")
    monkeypatch.delenv("PYWEBVIEW_GUI", raising=False)
    monkeypatch.delenv("KDE_FULL_SESSION", raising=False)

    def boom(name):
        raise ValueError("Namespace WebKit2 not available for version 4.0")

    monkeypatch.setattr("vesper.commands.doctor.importlib.import_module", boom)

    ok, _, fix = _detect_webview_backend()
    assert ok is False
    assert "sudo apt install" in fix


def test_backend_falls_back_to_qt_when_gtk_missing(monkeypatch):
    monkeypatch.setattr("vesper.commands.doctor.platform.system", lambda: "Linux")
    monkeypatch.delenv("PYWEBVIEW_GUI", raising=False)
    monkeypatch.delenv("KDE_FULL_SESSION", raising=False)

    def selective(name):
        if name.endswith("gtk"):
            raise ImportError("No module named 'gi'")
        return MagicMock()

    monkeypatch.setattr("vesper.commands.doctor.importlib.import_module", selective)

    ok, message, _ = _detect_webview_backend()
    assert ok is True
    assert "Qt / QtWebEngine" in message


def test_backend_macos_missing_pyobjc_mentions_framework_build(monkeypatch):
    monkeypatch.setattr("vesper.commands.doctor.platform.system", lambda: "Darwin")
    monkeypatch.delenv("PYWEBVIEW_GUI", raising=False)
    monkeypatch.delenv("KDE_FULL_SESSION", raising=False)

    def boom(name):
        raise ImportError("No module named 'Foundation'")

    monkeypatch.setattr("vesper.commands.doctor.importlib.import_module", boom)

    ok, _, fix = _detect_webview_backend()
    assert ok is False
    assert "pyobjc" in fix
    assert "framework build" in fix


def test_backend_windows_mshtml_fallback_fails(monkeypatch):
    """pythonnet imports fine but WebView2 is absent — pywebview degrades to IE11."""
    monkeypatch.setattr("vesper.commands.doctor.platform.system", lambda: "Windows")
    monkeypatch.delenv("PYWEBVIEW_GUI", raising=False)
    monkeypatch.delenv("KDE_FULL_SESSION", raising=False)

    winforms = MagicMock()
    winforms.renderer = "mshtml"
    monkeypatch.setattr(
        "vesper.commands.doctor.importlib.import_module", lambda name: winforms
    )

    ok, message, fix = _detect_webview_backend()
    assert ok is False
    assert "MSHTML" in message
    assert "WebView2" in fix


def test_backend_windows_edgechromium_passes(monkeypatch):
    monkeypatch.setattr("vesper.commands.doctor.platform.system", lambda: "Windows")
    monkeypatch.delenv("PYWEBVIEW_GUI", raising=False)
    monkeypatch.delenv("KDE_FULL_SESSION", raising=False)

    winforms = MagicMock()
    winforms.renderer = "edgechromium"
    monkeypatch.setattr(
        "vesper.commands.doctor.importlib.import_module", lambda name: winforms
    )

    ok, message, fix = _detect_webview_backend()
    assert ok is True
    assert "WinForms / WebView2" in message
    assert fix is None


def test_backend_unsupported_platform(monkeypatch):
    monkeypatch.setattr("vesper.commands.doctor.platform.system", lambda: "Haiku")
    ok, message, _ = _detect_webview_backend()
    assert ok is False
    assert "Unsupported platform" in message


def test_doctor_reports_backend_failure(tmp_path, monkeypatch, capsys):
    """A missing backend must make doctor exit non-zero, not report all-green."""
    fake_which, fake_run = _make_project(tmp_path, monkeypatch, '[project]\nname = "app"\n')

    with patch("vesper.commands.doctor.shutil.which", side_effect=fake_which), \
         patch("vesper.commands.doctor.subprocess.run", side_effect=fake_run), \
         patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"), \
         patch(
             "vesper.commands.doctor._detect_webview_backend",
             return_value=(False, "WebView backend: none available", "install GTK"),
         ):
        with pytest.raises(SystemExit):
            doctor()

    out = capsys.readouterr().out
    assert "[FAIL] WebView backend: none available" in out
    assert "Fix: install GTK" in out
