"""Tests for vesper doctor improvements — Node.js, PM, and vesper.toml schema checks."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vesper.commands.doctor import _PROJECT_VALID_KEYS, _PROJECT_VALID_VALUES, doctor


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
