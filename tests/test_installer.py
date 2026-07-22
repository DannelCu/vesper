"""Tests for `vesper package --installer` (vesper/commands/installer.py)."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vesper.commands import installer
from vesper.commands.package import add_package_parser


# ── metadata and generators (pure, real tests) ───────────────────────────────


def test_metadata_defaults(tmp_path):
    meta = installer.installer_metadata(tmp_path, "My App")
    assert meta["name"] == "My App"
    assert meta["version"] == "0.1.0"
    assert meta["category"] == "Utility"


def test_metadata_reads_installer_section(tmp_path):
    (tmp_path / "vesper.toml").write_text(
        "[project]\nname = \"my-app\"\n\n"
        "[installer]\nversion = \"2.1.0\"\nmaintainer = \"Ann <ann@example.com>\"\n"
        "category = \"Development\"\nicon = \"icon.png\"\n",
        encoding="utf-8",
    )
    meta = installer.installer_metadata(tmp_path, "my-app")
    assert meta["version"] == "2.1.0"
    assert meta["maintainer"] == "Ann <ann@example.com>"
    assert meta["category"] == "Development"
    assert meta["icon"] == "icon.png"


@pytest.mark.parametrize("raw,expected", [
    ("My App", "my-app"),
    ("my_app", "my-app"),
    ("Análisis!", "anlisis"),
    ("--weird..", "weird"),
])
def test_deb_package_name_is_debian_legal(raw, expected):
    assert installer.deb_package_name(raw) == expected


def test_deb_control_contains_required_fields():
    meta = installer.installer_metadata(Path("/nonexistent"), "My App")
    control = installer.deb_control(meta, "amd64")
    assert "Package: my-app\n" in control
    assert "Version: 0.1.0\n" in control
    assert "Architecture: amd64\n" in control
    assert control.startswith("Package:")
    assert control.endswith("\n")


def test_desktop_entry_shape():
    meta = installer.installer_metadata(Path("/nonexistent"), "My App")
    entry = installer.desktop_entry(meta)
    assert entry.startswith("[Desktop Entry]\n")
    assert "Type=Application\n" in entry
    assert "Name=My App\n" in entry
    assert "Exec=/usr/bin/my-app\n" in entry
    assert "Categories=Utility;\n" in entry
    assert "Icon=" not in entry            # no icon configured → no Icon line


def test_desktop_entry_with_icon():
    meta = {**installer.installer_metadata(Path("/x"), "My App"), "icon": "icon.png"}
    assert "Icon=my-app" in installer.desktop_entry(meta)


def test_dmg_command_shape(tmp_path):
    cmd = installer.dmg_command("My App", tmp_path / "staging", tmp_path / "out.dmg")
    assert cmd[:2] == ["hdiutil", "create"]
    assert "-volname" in cmd and "My App" in cmd
    assert "-format" in cmd and "UDZO" in cmd


def test_deb_command_shape(tmp_path):
    cmd = installer.deb_command(tmp_path / "staging", tmp_path / "out.deb")
    assert cmd[:3] == ["dpkg-deb", "--build", "--root-owner-group"]


# ── build_deb (mocked dpkg-deb, real staging tree) ───────────────────────────


@pytest.fixture
def deb_project(tmp_path):
    (tmp_path / "package").mkdir()
    (tmp_path / "package" / "my-app").write_bytes(b"\x7fELF fake binary")
    (tmp_path / "icon.png").write_bytes(b"\x89PNG fake")
    (tmp_path / "vesper.toml").write_text(
        "[installer]\nversion = \"1.2.3\"\nicon = \"icon.png\"\n", encoding="utf-8"
    )
    return tmp_path


def test_build_deb_constructs_the_call_and_tree(deb_project, monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["dpkg", "--print-architecture"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="arm64\n", stderr="")
        seen["cmd"] = list(cmd)
        # Snapshot the staging tree before build_deb cleans it up.
        staging = Path(cmd[3])
        seen["control"] = (staging / "DEBIAN" / "control").read_text()
        # as_posix(): the staged layout is what matters, not the separators of
        # the OS running the test.
        seen["files"] = sorted(
            p.relative_to(staging).as_posix() for p in staging.rglob("*") if p.is_file()
        )
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(installer.subprocess, "run", fake_run)
    monkeypatch.setattr(installer.shutil, "which", lambda name: f"/usr/bin/{name}")

    meta = installer.installer_metadata(deb_project, "my-app")
    installer.build_deb(deb_project, "my-app", meta)

    assert seen["cmd"][:3] == ["dpkg-deb", "--build", "--root-owner-group"]
    assert seen["cmd"][4].endswith("my-app_1.2.3_arm64.deb")
    assert "Version: 1.2.3" in seen["control"]
    assert "usr/bin/my-app" in seen["files"]
    assert "usr/share/applications/my-app.desktop" in seen["files"]
    assert "usr/share/icons/hicolor/256x256/apps/my-app.png" in seen["files"]
    # Staging is cleaned up either way.
    assert not (deb_project / "package" / "deb-staging").exists()


def test_build_deb_without_dpkg_explains(deb_project, monkeypatch, capsys):
    monkeypatch.setattr(installer.shutil, "which", lambda name: None)
    meta = installer.installer_metadata(deb_project, "my-app")

    with pytest.raises(SystemExit):
        installer.build_deb(deb_project, "my-app", meta)
    out = capsys.readouterr().out
    assert "dpkg-deb not found" in out


def test_build_deb_without_binary_explains(tmp_path, monkeypatch, capsys):
    (tmp_path / "package").mkdir()
    meta = installer.installer_metadata(tmp_path, "my-app")

    with pytest.raises(SystemExit):
        installer.build_deb(tmp_path, "my-app", meta)
    assert "Run 'vesper package' first" in capsys.readouterr().out


# ── build_dmg (mocked hdiutil) ───────────────────────────────────────────────


@pytest.fixture
def dmg_project(tmp_path):
    bundle = tmp_path / "package" / "MyApp.app" / "Contents" / "MacOS"
    bundle.mkdir(parents=True)
    (bundle / "MyApp").write_bytes(b"fake")
    return tmp_path


def test_build_dmg_constructs_the_call(dmg_project, monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = list(cmd)
        staging = Path(cmd[cmd.index("-srcfolder") + 1])
        seen["staged"] = sorted(p.name for p in staging.iterdir())
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(installer.subprocess, "run", fake_run)
    monkeypatch.setattr(installer.shutil, "which", lambda name: f"/usr/bin/{name}")

    meta = installer.installer_metadata(dmg_project, "MyApp")
    installer.build_dmg(dmg_project, "MyApp", meta)

    assert seen["cmd"][:2] == ["hdiutil", "create"]
    assert seen["cmd"][-1].endswith("MyApp-0.1.0.dmg")
    # Drag-to-install layout: the .app next to an Applications link.
    assert seen["staged"] == ["Applications", "MyApp.app"]
    assert not (dmg_project / "package" / "dmg-staging").exists()


def test_build_dmg_signs_first_when_configured(dmg_project, monkeypatch):
    (dmg_project / "vesper.toml").write_text(
        "[sign]\nidentity = \"Developer ID Application: X\"\n", encoding="utf-8"
    )
    order = []

    import vesper.commands.sign as sign_mod

    monkeypatch.setattr(
        sign_mod, "sign_macos", lambda bundle, cfg: order.append(("sign", bundle.name))
    )
    monkeypatch.setattr(
        installer.subprocess, "run",
        lambda cmd, **kw: (order.append(("hdiutil", None)),
                           subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b""))[1],
    )
    monkeypatch.setattr(installer.shutil, "which", lambda name: f"/usr/bin/{name}")

    meta = installer.installer_metadata(dmg_project, "MyApp")
    installer.build_dmg(dmg_project, "MyApp", meta)

    assert order[0] == ("sign", "MyApp.app")
    assert order[1][0] == "hdiutil"


def test_build_dmg_without_bundle_explains(tmp_path, monkeypatch, capsys):
    (tmp_path / "package").mkdir()
    meta = installer.installer_metadata(tmp_path, "MyApp")

    with pytest.raises(SystemExit):
        installer.build_dmg(tmp_path, "MyApp", meta)
    assert "App bundle not found" in capsys.readouterr().out


# ── Windows: explain, never fail silently ────────────────────────────────────


def test_windows_explains_nsis_missing(monkeypatch, capsys):
    monkeypatch.setattr(installer.shutil, "which", lambda name: None)
    with pytest.raises(SystemExit):
        installer.explain_windows_installer()
    out = capsys.readouterr().out
    assert "NSIS" in out
    assert "windows-installer.md" in out


def test_windows_mentions_recipe_when_nsis_present(monkeypatch, capsys):
    monkeypatch.setattr(installer.shutil, "which", lambda name: "C:/NSIS/makensis.exe")
    with pytest.raises(SystemExit):
        installer.explain_windows_installer()
    out = capsys.readouterr().out
    assert "NSIS is installed" in out
    assert "windows-installer.md" in out


# ── dispatch and CLI flag ────────────────────────────────────────────────────


def test_build_installer_dispatches_by_platform(monkeypatch, tmp_path):
    called = {}
    monkeypatch.setattr(installer, "build_dmg", lambda *a: called.setdefault("dmg", True))
    monkeypatch.setattr(installer, "build_deb", lambda *a: called.setdefault("deb", True))
    monkeypatch.setattr(
        installer, "explain_windows_installer", lambda: called.setdefault("win", True)
    )

    monkeypatch.setattr(installer.sys, "platform", "darwin")
    installer.build_installer(tmp_path, "app")
    monkeypatch.setattr(installer.sys, "platform", "linux")
    installer.build_installer(tmp_path, "app")
    monkeypatch.setattr(installer.sys, "platform", "win32")
    installer.build_installer(tmp_path, "app")

    assert called == {"dmg": True, "deb": True, "win": True}


def test_package_parser_accepts_installer_flag():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    add_package_parser(subparsers)

    assert parser.parse_args(["package"]).installer is False
    assert parser.parse_args(["package", "--installer"]).installer is True
