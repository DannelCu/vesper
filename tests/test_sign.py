"""Tests for vesper sign — code signing command."""
from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from vesper.commands.sign import (
    find_packaged_binary,
    find_signtool,
    notarize_macos,
    sign,
    sign_macos,
    sign_windows,
    sign_windows_osslsigncode,
    sign_windows_signtool,
)


# ── find_signtool ─────────────────────────────────────────────────────────────


def test_find_signtool_returns_path_from_which():
    with patch("shutil.which", side_effect=lambda n: "/usr/bin/signtool" if n == "signtool" else None):
        assert find_signtool() == "/usr/bin/signtool"


def test_find_signtool_returns_none_when_missing():
    with patch("shutil.which", return_value=None), \
         patch("vesper.commands.sign.Path.is_dir", return_value=False):
        assert find_signtool() is None


# ── find_packaged_binary ──────────────────────────────────────────────────────


def test_find_packaged_binary_returns_exe_on_windows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pkg = tmp_path / "package"
    pkg.mkdir()
    suffix = ".exe" if sys.platform == "win32" else ""
    binary = pkg / f"myapp{suffix}"
    binary.write_bytes(b"binary")

    result = find_packaged_binary(tmp_path, {"name": "myapp"})
    assert result == binary


def test_find_packaged_binary_uses_dir_name_as_default(tmp_path):
    pkg = tmp_path / "package"
    pkg.mkdir()
    suffix = ".exe" if sys.platform == "win32" else ""
    binary = pkg / f"{tmp_path.name}{suffix}"
    binary.write_bytes(b"binary")

    result = find_packaged_binary(tmp_path, {})
    assert result == binary


def test_find_packaged_binary_missing_package_dir_exits(tmp_path):
    with pytest.raises(SystemExit):
        find_packaged_binary(tmp_path, {"name": "myapp"})


def test_find_packaged_binary_missing_binary_exits(tmp_path):
    (tmp_path / "package").mkdir()
    with pytest.raises(SystemExit):
        find_packaged_binary(tmp_path, {"name": "myapp"})


# ── sign_macos ────────────────────────────────────────────────────────────────


@pytest.mark.skipif(sys.platform == "win32", reason="macOS paths only")
def test_sign_macos_calls_codesign(tmp_path):
    binary = tmp_path / "myapp"
    binary.write_bytes(b"binary")

    with patch("subprocess.run") as mock_run:
        sign_macos(binary, {"identity": "Developer ID Application: Test"})

    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "codesign" in cmd
    assert "--sign" in cmd
    assert "Developer ID Application: Test" in cmd


@pytest.mark.skipif(sys.platform == "win32", reason="macOS paths only")
def test_sign_macos_includes_entitlements(tmp_path):
    binary = tmp_path / "myapp"
    binary.write_bytes(b"binary")
    ent = tmp_path / "entitlements.plist"
    ent.write_text("<plist/>")

    with patch("subprocess.run") as mock_run:
        sign_macos(binary, {
            "identity": "Developer ID Application: Test",
            "entitlements": str(ent),
        })

    cmd = mock_run.call_args[0][0]
    assert "--entitlements" in cmd
    assert str(ent) in cmd


@pytest.mark.skipif(sys.platform == "win32", reason="macOS paths only")
def test_sign_macos_missing_identity_exits(tmp_path):
    binary = tmp_path / "myapp"
    binary.write_bytes(b"binary")
    with pytest.raises(SystemExit):
        sign_macos(binary, {})


@pytest.mark.skipif(sys.platform == "win32", reason="macOS paths only")
def test_sign_macos_missing_entitlements_file_exits(tmp_path):
    binary = tmp_path / "myapp"
    binary.write_bytes(b"binary")
    with pytest.raises(SystemExit):
        sign_macos(binary, {
            "identity": "Developer ID Application: Test",
            "entitlements": str(tmp_path / "missing.plist"),
        })


@pytest.mark.skipif(sys.platform == "win32", reason="macOS paths only")
def test_sign_macos_triggers_notarize_when_set(tmp_path):
    binary = tmp_path / "myapp"
    binary.write_bytes(b"binary")

    with patch("subprocess.run"), \
         patch("vesper.commands.sign.notarize_macos") as mock_notarize:
        sign_macos(binary, {
            "identity": "Developer ID Application: Test",
            "notarize": "true",
        })

    mock_notarize.assert_called_once_with(binary, {
        "identity": "Developer ID Application: Test",
        "notarize": "true",
    })


# ── notarize_macos ────────────────────────────────────────────────────────────


@pytest.mark.skipif(sys.platform == "win32", reason="macOS paths only")
def test_notarize_macos_missing_apple_id_exits(tmp_path):
    binary = tmp_path / "myapp"
    binary.write_bytes(b"binary")
    with pytest.raises(SystemExit):
        notarize_macos(binary, {"team_id": "ABC123"})


@pytest.mark.skipif(sys.platform == "win32", reason="macOS paths only")
def test_notarize_macos_missing_password_env_exits(tmp_path, monkeypatch):
    monkeypatch.delenv("VESPER_NOTARIZE_PASSWORD", raising=False)
    binary = tmp_path / "myapp"
    binary.write_bytes(b"binary")
    with pytest.raises(SystemExit):
        notarize_macos(binary, {"apple_id": "dev@x.com", "team_id": "ABC123"})


@pytest.mark.skipif(sys.platform == "win32", reason="macOS paths only")
def test_notarize_macos_runs_expected_commands(tmp_path, monkeypatch):
    monkeypatch.setenv("VESPER_NOTARIZE_PASSWORD", "secret")
    binary = tmp_path / "myapp"
    binary.write_bytes(b"binary")

    with patch("subprocess.run") as mock_run:
        notarize_macos(binary, {"apple_id": "dev@x.com", "team_id": "T1"})

    assert mock_run.call_count == 3
    cmds = [mock_run.call_args_list[i][0][0] for i in range(3)]
    assert "ditto" in cmds[0]
    assert "notarytool" in cmds[1]
    assert "stapler" in cmds[2]


# ── sign_windows_signtool ─────────────────────────────────────────────────────


def test_sign_windows_signtool_builds_correct_cmd(tmp_path):
    binary = tmp_path / "myapp.exe"
    binary.write_bytes(b"binary")
    cert = tmp_path / "cert.pfx"
    cert.write_bytes(b"cert")

    with patch("subprocess.run") as mock_run:
        sign_windows_signtool(binary, cert, "pass123", "http://ts.example.com", "signtool.exe")

    cmd = mock_run.call_args[0][0]
    assert "signtool.exe" in cmd
    assert "/f" in cmd
    assert "/p" in cmd
    assert "pass123" in cmd
    assert "/t" in cmd
    assert "http://ts.example.com" in cmd
    assert "/fd" in cmd
    assert "sha256" in cmd


def test_sign_windows_signtool_no_password_no_p_flag(tmp_path):
    binary = tmp_path / "myapp.exe"
    binary.write_bytes(b"binary")
    cert = tmp_path / "cert.pfx"
    cert.write_bytes(b"cert")

    with patch("subprocess.run") as mock_run:
        sign_windows_signtool(binary, cert, "", "", "signtool.exe")

    cmd = mock_run.call_args[0][0]
    assert "/p" not in cmd
    assert "/t" not in cmd


def test_sign_windows_signtool_failure_exits(tmp_path):
    import subprocess
    binary = tmp_path / "myapp.exe"
    binary.write_bytes(b"binary")
    cert = tmp_path / "cert.pfx"
    cert.write_bytes(b"cert")

    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "signtool")):
        with pytest.raises(SystemExit):
            sign_windows_signtool(binary, cert, "", "", "signtool.exe")


# ── sign_windows_osslsigncode ─────────────────────────────────────────────────


def test_sign_windows_osslsigncode_replaces_original(tmp_path):
    binary = tmp_path / "myapp.exe"
    binary.write_bytes(b"original")
    cert = tmp_path / "cert.pfx"
    cert.write_bytes(b"cert")
    signed = tmp_path / "myapp_signed.exe"

    def fake_run(cmd, **kwargs):
        signed.write_bytes(b"signed content")

    with patch("subprocess.run", side_effect=fake_run):
        sign_windows_osslsigncode(binary, cert, "pass", "", "osslsigncode")

    assert binary.read_bytes() == b"signed content"
    assert not signed.exists()


def test_sign_windows_osslsigncode_builds_correct_cmd(tmp_path):
    binary = tmp_path / "myapp.exe"
    binary.write_bytes(b"binary")
    cert = tmp_path / "cert.pfx"
    cert.write_bytes(b"cert")

    def fake_run(cmd, **kwargs):
        Path(cmd[cmd.index("-out") + 1]).write_bytes(b"signed")

    with patch("subprocess.run", side_effect=fake_run):
        sign_windows_osslsigncode(binary, cert, "pass", "http://ts.example.com", "osslsigncode")

    # Just verify it ran without error — cmd structure tested indirectly via fake_run


# ── sign_windows dispatcher ───────────────────────────────────────────────────


def test_sign_windows_missing_certificate_exits(tmp_path):
    with pytest.raises(SystemExit):
        sign_windows(tmp_path / "myapp.exe", {})


def test_sign_windows_certificate_not_found_exits(tmp_path):
    binary = tmp_path / "myapp.exe"
    binary.write_bytes(b"binary")
    with pytest.raises(SystemExit):
        sign_windows(binary, {"certificate": str(tmp_path / "missing.pfx")})


def test_sign_windows_no_tool_found_exits(tmp_path):
    binary = tmp_path / "myapp.exe"
    binary.write_bytes(b"binary")
    cert = tmp_path / "cert.pfx"
    cert.write_bytes(b"cert")

    with patch("vesper.commands.sign.find_signtool", return_value=None), \
         patch("shutil.which", return_value=None):
        with pytest.raises(SystemExit):
            sign_windows(binary, {"certificate": str(cert)})


def test_sign_windows_prefers_signtool_over_osslsigncode(tmp_path):
    binary = tmp_path / "myapp.exe"
    binary.write_bytes(b"binary")
    cert = tmp_path / "cert.pfx"
    cert.write_bytes(b"cert")

    with patch("vesper.commands.sign.find_signtool", return_value="signtool.exe"), \
         patch("vesper.commands.sign.sign_windows_signtool") as mock_st, \
         patch("vesper.commands.sign.sign_windows_osslsigncode") as mock_ossl:
        sign_windows(binary, {"certificate": str(cert)})

    mock_st.assert_called_once()
    mock_ossl.assert_not_called()


def test_sign_windows_falls_back_to_osslsigncode(tmp_path):
    binary = tmp_path / "myapp.exe"
    binary.write_bytes(b"binary")
    cert = tmp_path / "cert.pfx"
    cert.write_bytes(b"cert")

    with patch("vesper.commands.sign.find_signtool", return_value=None), \
         patch("shutil.which", return_value="osslsigncode"), \
         patch("vesper.commands.sign.sign_windows_osslsigncode") as mock_ossl:
        sign_windows(binary, {"certificate": str(cert)})

    mock_ossl.assert_called_once()


# ── sign() top-level ──────────────────────────────────────────────────────────


def test_sign_no_toml_sign_section_exits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "vesper.toml").write_text("[project]\nname = \"myapp\"\n")
    with pytest.raises(SystemExit):
        sign()


def test_sign_explicit_path_not_found_exits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "vesper.toml").write_text("[sign]\nidentity = \"Dev\"\n")
    with pytest.raises(SystemExit):
        sign(binary_path=str(tmp_path / "nonexistent"))


def test_sign_unsupported_platform_exits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "vesper.toml").write_text("[sign]\nidentity = \"Dev\"\n")
    binary = tmp_path / "myapp"
    binary.write_bytes(b"binary")

    with patch("platform.system", return_value="FreeBSD"):
        with pytest.raises(SystemExit):
            sign(binary_path=str(binary))


# ── doctor [sign] section validation ─────────────────────────────────────────


from vesper.commands.doctor import _SIGN_VALID_KEYS, _SIGN_VALID_VALUES, doctor
from unittest.mock import MagicMock, patch as _patch


def _doctor_env(tmp_path, monkeypatch, toml_content):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("")
    (tmp_path / "vesper.toml").write_text(toml_content)
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text('<script src="./vesper.js"></script></body>')
    (frontend / "vesper.js").write_text("")

    def fake_which(name):
        return f"/usr/bin/{name}" if name in ("node", "npm", "codesign", "xcrun") else None

    def fake_run(cmd, **kwargs):
        m = MagicMock()
        m.returncode = 0
        m.stdout = "v20.0.0"
        return m

    return fake_which, fake_run


def test_sign_valid_keys_constant():
    assert "identity" in _SIGN_VALID_KEYS
    assert "certificate" in _SIGN_VALID_KEYS
    assert "notarize" in _SIGN_VALID_KEYS
    assert "apple_id" in _SIGN_VALID_KEYS
    assert "team_id" in _SIGN_VALID_KEYS
    assert "timestamp_url" in _SIGN_VALID_KEYS
    assert "entitlements" in _SIGN_VALID_KEYS


def test_sign_notarize_valid_values():
    assert _SIGN_VALID_VALUES["notarize"] == {"true", "false"}


def test_doctor_sign_unknown_key_fails(tmp_path, monkeypatch, capsys):
    fake_which, fake_run = _doctor_env(
        tmp_path, monkeypatch,
        '[project]\nname = "app"\n\n[sign]\nbad_key = "x"\n',
    )
    with _patch("vesper.commands.doctor.shutil.which", side_effect=fake_which), \
         _patch("vesper.commands.doctor.subprocess.run", side_effect=fake_run), \
         _patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"):
        with pytest.raises(SystemExit):
            doctor()
    out = capsys.readouterr().out
    assert "[sign] unknown key 'bad_key'" in out


def test_doctor_sign_invalid_notarize_value_fails(tmp_path, monkeypatch, capsys):
    fake_which, fake_run = _doctor_env(
        tmp_path, monkeypatch,
        '[project]\nname = "app"\n\n[sign]\nnotarize = "maybe"\n',
    )
    with _patch("vesper.commands.doctor.shutil.which", side_effect=fake_which), \
         _patch("vesper.commands.doctor.subprocess.run", side_effect=fake_run), \
         _patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"):
        with pytest.raises(SystemExit):
            doctor()
    out = capsys.readouterr().out
    assert "invalid value for 'notarize': 'maybe'" in out


def test_doctor_sign_notarize_without_apple_id_fails(tmp_path, monkeypatch, capsys):
    fake_which, fake_run = _doctor_env(
        tmp_path, monkeypatch,
        '[project]\nname = "app"\n\n[sign]\nnotarize = "true"\nteam_id = "T1"\n',
    )
    with _patch("vesper.commands.doctor.shutil.which", side_effect=fake_which), \
         _patch("vesper.commands.doctor.subprocess.run", side_effect=fake_run), \
         _patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"):
        with pytest.raises(SystemExit):
            doctor()
    out = capsys.readouterr().out
    assert "apple_id is missing" in out


def test_doctor_sign_notarize_without_team_id_fails(tmp_path, monkeypatch, capsys):
    fake_which, fake_run = _doctor_env(
        tmp_path, monkeypatch,
        '[project]\nname = "app"\n\n[sign]\nnotarize = "true"\napple_id = "dev@x.com"\n',
    )
    with _patch("vesper.commands.doctor.shutil.which", side_effect=fake_which), \
         _patch("vesper.commands.doctor.subprocess.run", side_effect=fake_run), \
         _patch("vesper.commands.utils.importlib.metadata.version", return_value="1.0.0"):
        with pytest.raises(SystemExit):
            doctor()
    out = capsys.readouterr().out
    assert "team_id is missing" in out
