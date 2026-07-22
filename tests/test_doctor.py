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


ALL_CAPABILITIES_OK = {
    name: {"available": True, "detail": "stub", "fix": None}
    for name in (
        "clipboard_text", "clipboard_image", "clipboard_files", "notifications",
        "trash", "keep_awake", "tray", "badge", "mica", "nsis", "screenshot",
        "power_events", "global_shortcuts",
    )
}


@pytest.fixture(autouse=True)
def stub_capabilities():
    """
    Same reason as stub_webview_backend: probe() reads the real PATH and the real
    installed packages, so without this every doctor() test would report differently
    depending on whether the machine happens to have xclip.
    """
    with patch("vesper.core.capabilities.probe", return_value=ALL_CAPABILITIES_OK):
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


# ── Optional features section ─────────────────────────────────────────────────


def _minimal_project(tmp_path):
    (tmp_path / "app.py").write_text("")
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text('<script src="./vesper.js"></script></body>')
    (frontend / "vesper.js").write_text("")


def _doctor_output(tmp_path, monkeypatch, capsys, capability_report):
    """Run doctor() over a healthy project with a given capability report."""
    monkeypatch.chdir(tmp_path)
    _minimal_project(tmp_path)

    def fake_run(cmd, **kwargs):
        m = MagicMock()
        m.returncode = 0
        m.stdout = "v20.0.0"
        return m

    with patch("vesper.commands.doctor.shutil.which",
               side_effect=lambda n: f"/usr/bin/{n}" if n in ("node", "npm") else None), \
         patch("vesper.commands.doctor.subprocess.run", side_effect=fake_run), \
         patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"), \
         patch("vesper.core.capabilities.probe", return_value=capability_report):
        try:
            doctor()
            exited = 0
        except SystemExit as e:
            exited = e.code

    return capsys.readouterr().out, exited


def test_optional_features_section_is_printed(tmp_path, monkeypatch, capsys):
    out, _ = _doctor_output(tmp_path, monkeypatch, capsys, ALL_CAPABILITIES_OK)
    assert "Optional features" in out


def test_every_capability_gets_a_line(tmp_path, monkeypatch, capsys):
    """Every capability is accounted for, whether on its own row or a grouped one."""
    from vesper.commands.doctor import _CAPABILITY_LABELS

    # Distinct details keep the clipboard rows from being merged, so each label shows.
    report = {
        name: {"available": True, "detail": f"stub-{name}", "fix": None}
        for name in ALL_CAPABILITIES_OK
    }

    out, _ = _doctor_output(tmp_path, monkeypatch, capsys, report)
    for label in _CAPABILITY_LABELS.values():
        assert label in out, label


def test_a_missing_capability_is_listed_with_its_fix(tmp_path, monkeypatch, capsys):
    report = dict(ALL_CAPABILITIES_OK)
    report["clipboard_image"] = {
        "available": False,
        "detail": "xclip not found",
        "fix": "sudo apt install xclip",
    }

    out, _ = _doctor_output(tmp_path, monkeypatch, capsys, report)

    assert "xclip not found" in out
    assert "Fix: sudo apt install xclip" in out


def test_a_missing_capability_is_a_warning_not_a_failure(tmp_path, monkeypatch, capsys):
    """Optional means optional: [WARN], not the [FAIL] used for the WebView."""
    report = dict(ALL_CAPABILITIES_OK)
    report["tray"] = {"available": False, "detail": "missing: pystray", "fix": "x"}

    out, _ = _doctor_output(tmp_path, monkeypatch, capsys, report)

    assert "[WARN] System tray" in out
    assert "[FAIL] System tray" not in out


def test_a_missing_capability_does_not_fail_doctor(tmp_path, monkeypatch, capsys):
    """The whole point: an unavailable optional backend must not exit non-zero."""
    report = {
        name: {"available": False, "detail": "gone", "fix": "install it"}
        for name in ALL_CAPABILITIES_OK
    }

    out, exited = _doctor_output(tmp_path, monkeypatch, capsys, report)

    assert exited == 0
    assert "All required checks passed." in out


def test_missing_capabilities_are_counted(tmp_path, monkeypatch, capsys):
    report = dict(ALL_CAPABILITIES_OK)
    report["tray"] = {"available": False, "detail": "gone", "fix": "x"}
    report["trash"] = {"available": False, "detail": "gone", "fix": "y"}

    out, _ = _doctor_output(tmp_path, monkeypatch, capsys, report)

    assert "2 optional feature(s) unavailable" in out


def test_no_summary_line_when_everything_is_available(tmp_path, monkeypatch, capsys):
    out, _ = _doctor_output(tmp_path, monkeypatch, capsys, ALL_CAPABILITIES_OK)
    assert "unavailable" not in out


def test_optional_section_comes_after_the_critical_checks(tmp_path, monkeypatch, capsys):
    """Ordering matters: the critical checks must not be buried below optional ones."""
    out, _ = _doctor_output(tmp_path, monkeypatch, capsys, ALL_CAPABILITIES_OK)
    assert out.index("WebView backend") < out.index("Optional features")


def test_a_critical_failure_still_fails_with_capabilities_present(
    tmp_path, monkeypatch, capsys
):
    """Adding the section must not mask a real problem."""
    monkeypatch.chdir(tmp_path)   # no project files at all

    with patch("vesper.commands.doctor.shutil.which", return_value=None), \
         patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"), \
         patch("vesper.core.capabilities.probe", return_value=ALL_CAPABILITIES_OK):
        with pytest.raises(SystemExit) as exc:
            doctor()

    assert exc.value.code == 1
    assert "Optional features" in capsys.readouterr().out


# ── Optional features: three states and grouping ──────────────────────────────


def test_unavailable_with_a_fix_is_a_warning(tmp_path, monkeypatch, capsys):
    report = dict(ALL_CAPABILITIES_OK)
    report["tray"] = {"available": False, "detail": "missing: pystray", "fix": "install"}

    out, _ = _doctor_output(tmp_path, monkeypatch, capsys, report)

    assert "[WARN] System tray" in out
    assert "Fix: install" in out


def test_unavailable_without_a_fix_is_not_applicable(tmp_path, monkeypatch, capsys):
    """A Linux taskbar badge is not something the user forgot to install."""
    report = dict(ALL_CAPABILITIES_OK)
    report["badge"] = {
        "available": False,
        "detail": "no cross-desktop badge protocol on Linux",
        "fix": None,
    }

    out, _ = _doctor_output(tmp_path, monkeypatch, capsys, report)

    assert "[N/A] Taskbar / dock badge" in out
    assert "[WARN] Taskbar / dock badge" not in out


def test_not_applicable_never_prints_a_fix_line(tmp_path, monkeypatch, capsys):
    report = dict(ALL_CAPABILITIES_OK)
    report["badge"] = {"available": False, "detail": "unsupported", "fix": None}

    out, _ = _doctor_output(tmp_path, monkeypatch, capsys, report)

    badge_line = [ln for ln in out.splitlines() if "Taskbar" in ln][0]
    following = out.splitlines()[out.splitlines().index(badge_line) + 1]
    assert "Fix:" not in following


def test_fail_is_reserved_for_critical_checks(tmp_path, monkeypatch, capsys):
    """No optional feature may print [FAIL], whatever its state."""
    report = {
        name: {"available": False, "detail": "gone", "fix": "install it"}
        for name in ALL_CAPABILITIES_OK
    }
    report["badge"] = {"available": False, "detail": "unsupported", "fix": None}

    out, _ = _doctor_output(tmp_path, monkeypatch, capsys, report)

    optional_section = out.split("Optional features")[1]
    assert "[FAIL]" not in optional_section


def test_identical_clipboard_entries_are_grouped(tmp_path, monkeypatch, capsys):
    """One xclip, one fix line — two rows would look like two problems."""
    xclip = {"available": False, "detail": "xclip not found", "fix": "apt install xclip"}
    report = dict(ALL_CAPABILITIES_OK)
    report["clipboard_text"] = xclip
    report["clipboard_image"] = dict(xclip)

    out, _ = _doctor_output(tmp_path, monkeypatch, capsys, report)

    assert "Clipboard (text + images)" in out
    assert "Clipboard (text):" not in out
    assert "Clipboard (images):" not in out
    assert out.count("apt install xclip") == 1


def test_differing_clipboard_entries_stay_separate(tmp_path, monkeypatch, capsys):
    """If text works while images do not, merging them would hide it."""
    report = dict(ALL_CAPABILITIES_OK)
    report["clipboard_text"] = {"available": True, "detail": "xclip", "fix": None}
    report["clipboard_image"] = {
        "available": False, "detail": "xclip not found", "fix": "apt install xclip",
    }

    out, _ = _doctor_output(tmp_path, monkeypatch, capsys, report)

    assert "Clipboard (text):" in out
    assert "Clipboard (images):" in out
    assert "Clipboard (text + images)" not in out


def test_grouped_row_counts_once_towards_the_total(tmp_path, monkeypatch, capsys):
    xclip = {"available": False, "detail": "xclip not found", "fix": "apt install xclip"}
    report = dict(ALL_CAPABILITIES_OK)
    report["clipboard_text"] = xclip
    report["clipboard_image"] = dict(xclip)

    out, _ = _doctor_output(tmp_path, monkeypatch, capsys, report)

    assert "1 optional feature(s) unavailable" in out


# ── Final verdict ─────────────────────────────────────────────────────────────


def test_verdict_is_unqualified_when_nothing_is_missing(tmp_path, monkeypatch, capsys):
    out, exited = _doctor_output(tmp_path, monkeypatch, capsys, ALL_CAPABILITIES_OK)

    assert exited == 0
    assert "All required checks passed." in out
    assert "optional feature(s) unavailable" not in out


def test_verdict_separates_required_from_optional(tmp_path, monkeypatch, capsys):
    """"All checks passed" above a list of [WARN] lines reads as a contradiction."""
    report = dict(ALL_CAPABILITIES_OK)
    report["tray"] = {"available": False, "detail": "gone", "fix": "install"}

    out, exited = _doctor_output(tmp_path, monkeypatch, capsys, report)

    assert exited == 0
    assert "All required checks passed." in out
    assert "1 optional feature(s) unavailable (see above)" in out
    assert "degrade to no-ops" in out


def test_verdict_is_absent_when_a_required_check_failed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    with patch("vesper.commands.doctor.shutil.which", return_value=None), \
         patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"), \
         patch("vesper.core.capabilities.probe", return_value=ALL_CAPABILITIES_OK):
        with pytest.raises(SystemExit):
            doctor()

    out = capsys.readouterr().out
    assert "All required checks passed." not in out
    assert "Doctor found issues" in out
