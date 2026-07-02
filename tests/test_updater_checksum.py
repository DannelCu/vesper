"""Tests for updater checksum verification and install guards."""
from __future__ import annotations

import hashlib
import os

import pytest

from vesper.core.updater import install, verify_checksum


def _write_binary(path, content: bytes = b"fake-binary-data") -> str:
    with open(path, "wb") as f:
        f.write(content)
    return path


def _sha256_of(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def test_verify_checksum_matches(tmp_path):
    content = b"hello world"
    f = tmp_path / "binary"
    f.write_bytes(content)
    assert verify_checksum(str(f), _sha256_of(content)) is True


def test_verify_checksum_mismatch(tmp_path):
    f = tmp_path / "binary"
    f.write_bytes(b"hello world")
    assert verify_checksum(str(f), _sha256_of(b"different content")) is False


def test_verify_checksum_empty_expected_returns_false(tmp_path):
    f = tmp_path / "binary"
    f.write_bytes(b"data")
    assert verify_checksum(str(f), "") is False


def test_verify_checksum_case_insensitive(tmp_path):
    content = b"case test"
    f = tmp_path / "binary"
    f.write_bytes(content)
    digest = _sha256_of(content).upper()
    assert verify_checksum(str(f), digest) is True


def test_install_refuses_without_hash(tmp_path):
    f = tmp_path / "binary"
    f.write_bytes(b"data")
    with pytest.raises(ValueError, match="expected_sha256"):
        install(str(f))


def test_install_refuses_on_bad_hash(tmp_path):
    content = b"real binary"
    f = tmp_path / "binary"
    f.write_bytes(content)
    bad_hash = _sha256_of(b"wrong content")
    with pytest.raises(ValueError, match="checksum"):
        install(str(f), expected_sha256=bad_hash)


def test_install_allow_unverified_skips_check(tmp_path, monkeypatch):
    f = tmp_path / "binary"
    f.write_bytes(b"data")
    # Patch _install_posix / _install_windows so we don't actually replace the process
    import vesper.core.updater as _updater
    called = []
    monkeypatch.setattr(_updater, "_install_posix", lambda c, n: called.append("posix"))
    monkeypatch.setattr(_updater, "_install_windows", lambda c, n: called.append("windows"))
    install(str(f), allow_unverified=True)
    assert len(called) == 1
