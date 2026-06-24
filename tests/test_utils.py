import pytest
from vesper.commands.utils import (
    detect_package_manager,
    get_project_package_manager,
    read_vesper_toml,
)


# ─── read_vesper_toml ─────────────────────────────────────────────────────────


def test_read_vesper_toml_parses_values(tmp_path):
    (tmp_path / "vesper.toml").write_text(
        '[project]\ntemplate = "react"\nstyles = "tailwind"\n',
        encoding="utf-8",
    )
    config = read_vesper_toml(tmp_path)
    assert config["template"] == "react"
    assert config["styles"] == "tailwind"


def test_read_vesper_toml_missing_file_returns_empty(tmp_path):
    assert read_vesper_toml(tmp_path) == {}


def test_read_vesper_toml_ignores_section_headers(tmp_path):
    (tmp_path / "vesper.toml").write_text(
        '[project]\nname = "my-app"\n',
        encoding="utf-8",
    )
    config = read_vesper_toml(tmp_path)
    assert "project" not in config
    assert config["name"] == "my-app"


def test_read_vesper_toml_ignores_comments(tmp_path):
    (tmp_path / "vesper.toml").write_text(
        '# comment\n[project]\nname = "app"\n',
        encoding="utf-8",
    )
    config = read_vesper_toml(tmp_path)
    assert config == {"name": "app"}


def test_read_vesper_toml_strips_quotes(tmp_path):
    (tmp_path / "vesper.toml").write_text(
        '[project]\nbundler = "pyinstaller"\n',
        encoding="utf-8",
    )
    config = read_vesper_toml(tmp_path)
    assert config["bundler"] == "pyinstaller"


# ─── detect_package_manager ───────────────────────────────────────────────────


def test_detect_pnpm_from_lockfile(tmp_path):
    (tmp_path / "pnpm-lock.yaml").touch()
    assert detect_package_manager(tmp_path) == "pnpm"


def test_detect_yarn_from_lockfile(tmp_path):
    (tmp_path / "yarn.lock").touch()
    assert detect_package_manager(tmp_path) == "yarn"


def test_detect_defaults_to_npm(tmp_path):
    assert detect_package_manager(tmp_path) == "npm"


def test_pnpm_lockfile_takes_priority_over_yarn(tmp_path):
    (tmp_path / "pnpm-lock.yaml").touch()
    (tmp_path / "yarn.lock").touch()
    assert detect_package_manager(tmp_path) == "pnpm"


# ─── get_project_package_manager ─────────────────────────────────────────────


def test_get_pm_reads_from_toml(tmp_path):
    (tmp_path / "vesper.toml").write_text(
        '[project]\npackage_manager = "pnpm"\n',
        encoding="utf-8",
    )
    assert get_project_package_manager(tmp_path) == "pnpm"


def test_get_pm_falls_back_to_lockfile(tmp_path):
    (tmp_path / "yarn.lock").touch()
    assert get_project_package_manager(tmp_path) == "yarn"


def test_get_pm_toml_takes_priority_over_lockfile(tmp_path):
    (tmp_path / "vesper.toml").write_text(
        '[project]\npackage_manager = "pnpm"\n',
        encoding="utf-8",
    )
    (tmp_path / "yarn.lock").touch()
    assert get_project_package_manager(tmp_path) == "pnpm"


def test_get_pm_defaults_to_npm(tmp_path):
    assert get_project_package_manager(tmp_path) == "npm"


def test_get_pm_ignores_unknown_value_in_toml(tmp_path):
    (tmp_path / "vesper.toml").write_text(
        '[project]\npackage_manager = "bun"\n',
        encoding="utf-8",
    )
    assert get_project_package_manager(tmp_path) == "npm"