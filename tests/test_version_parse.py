"""Tests for packaging.version.Version-based _parse_version in updater."""
from __future__ import annotations

from vesper.core.updater import _parse_version


def test_prerelease_is_less_than_release():
    assert _parse_version("1.0.0a1") < _parse_version("1.0.0")


def test_numeric_ordering_is_correct():
    assert _parse_version("1.2") < _parse_version("1.10")


def test_v_prefix_stripped():
    assert _parse_version("v2.0.0") == _parse_version("2.0.0")


def test_garbage_is_zero():
    assert _parse_version("not-a-version") == _parse_version("0")


def test_semver_patch_ordering():
    assert _parse_version("1.0.9") < _parse_version("1.0.10")


def test_equal_versions():
    assert _parse_version("1.2.3") == _parse_version("1.2.3")
