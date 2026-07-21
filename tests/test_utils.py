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

# ── print_check ───────────────────────────────────────────────────────────────


def test_print_check_ok(capsys):
    from vesper.commands.utils import print_check

    print_check(True, "everything is fine")
    assert capsys.readouterr().out == "[OK] everything is fine\n"


def test_print_check_failure_is_critical_by_default(capsys):
    """The existing callers pass no flag and must keep printing [FAIL]."""
    from vesper.commands.utils import print_check

    print_check(False, "broken")
    assert "[FAIL] broken" in capsys.readouterr().out


def test_print_check_non_critical_failure_warns(capsys):
    from vesper.commands.utils import print_check

    print_check(False, "optional thing", critical=False)
    out = capsys.readouterr().out
    assert "[WARN] optional thing" in out
    assert "[FAIL]" not in out


def test_print_check_prints_the_fix_when_it_failed(capsys):
    from vesper.commands.utils import print_check

    print_check(False, "broken", "run this")
    assert "Fix: run this" in capsys.readouterr().out


def test_print_check_hides_the_fix_when_it_passed(capsys):
    """Nothing to fix means nothing to print, whatever the caller passed."""
    from vesper.commands.utils import print_check

    print_check(True, "fine", "run this")
    assert "Fix" not in capsys.readouterr().out


def test_print_check_non_critical_still_shows_its_fix(capsys):
    from vesper.commands.utils import print_check

    print_check(False, "optional", "install it", critical=False)
    out = capsys.readouterr().out
    assert "[WARN]" in out and "Fix: install it" in out


# ── colour ────────────────────────────────────────────────────────────────────
#
# Colour is decoration. Most of these tests exist to prove the plain-text path still
# works, because doctor's output is redirected to a file or a CI log at least as
# often as it is read on a terminal.
#
# Two seams, used deliberately:
#   * supports_color() is tested by faking sys.stdout — patched inside the test
#     body, never in a fixture. pytest re-assigns sys.stdout when it resumes
#     capturing between fixture setup and the test call, so a patch applied during
#     setup is silently reverted before the test runs.
#   * print_check() output is tested by patching supports_color() itself, since
#     replacing sys.stdout would take the output away from capsys.

from vesper.commands import utils as utils_mod


class _FakeStream:
    def __init__(self, tty: bool) -> None:
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty

    def write(self, _text):
        pass

    def flush(self):
        pass


def fake_stdout(monkeypatch, *, tty: bool, platform: str = "linux") -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(utils_mod.sys, "platform", platform)
    monkeypatch.setattr(utils_mod.sys, "stdout", _FakeStream(tty))


# ── supports_color ────────────────────────────────────────────────────────────


def test_supports_color_on_a_tty(monkeypatch):
    fake_stdout(monkeypatch, tty=True)
    assert utils_mod.supports_color() is True


def test_no_color_when_not_a_tty(monkeypatch):
    """Redirecting to a file must not fill it with escape codes."""
    fake_stdout(monkeypatch, tty=False)
    assert utils_mod.supports_color() is False


def test_no_color_env_var_wins_over_a_tty(monkeypatch):
    fake_stdout(monkeypatch, tty=True)
    monkeypatch.setenv("NO_COLOR", "1")
    assert utils_mod.supports_color() is False


def test_no_color_is_honoured_when_empty(monkeypatch):
    """no-color.org specifies presence, not value — an empty string still counts."""
    fake_stdout(monkeypatch, tty=True)
    monkeypatch.setenv("NO_COLOR", "")
    assert utils_mod.supports_color() is False


def test_no_color_when_stdout_has_no_isatty(monkeypatch):
    """Some capture and logging objects are not file-like at all."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(utils_mod.sys, "stdout", object())
    assert utils_mod.supports_color() is False


def test_no_color_when_stdout_is_closed(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)

    class _Closed:
        def isatty(self):
            raise ValueError("I/O operation on closed file")

    monkeypatch.setattr(utils_mod.sys, "stdout", _Closed())
    assert utils_mod.supports_color() is False


# ── colour on Windows ─────────────────────────────────────────────────────────


def test_windows_enables_vt_processing(monkeypatch):
    """The console must be told to interpret escapes before any are emitted."""
    fake_stdout(monkeypatch, tty=True, platform="win32")
    monkeypatch.setattr(utils_mod, "_enable_windows_vt", lambda: True)
    assert utils_mod.supports_color() is True


def test_windows_falls_back_to_plain_when_vt_is_unavailable(monkeypatch):
    """Raw escapes in a console that cannot read them are worse than no colour."""
    fake_stdout(monkeypatch, tty=True, platform="win32")
    monkeypatch.setattr(utils_mod, "_enable_windows_vt", lambda: False)
    assert utils_mod.supports_color() is False


def test_windows_vt_failure_does_not_propagate(monkeypatch):
    """No ctypes error may escape into the middle of doctor's output."""
    fake_stdout(monkeypatch, tty=True, platform="win32")

    def boom():
        raise OSError("no console")

    monkeypatch.setattr(utils_mod, "_enable_windows_vt", boom)
    assert utils_mod.supports_color() is False


# ── colorize ──────────────────────────────────────────────────────────────────


def test_colorize_wraps_when_enabled(monkeypatch):
    monkeypatch.setattr(utils_mod, "supports_color", lambda: True)
    result = utils_mod.colorize("hello", utils_mod._GREEN)
    assert result == f"\x1b[32mhello\x1b[0m"


def test_colorize_is_a_passthrough_when_disabled(monkeypatch):
    monkeypatch.setattr(utils_mod, "supports_color", lambda: False)
    assert utils_mod.colorize("hello", utils_mod._GREEN) == "hello"


def test_colorize_without_a_color_is_a_passthrough(monkeypatch):
    monkeypatch.setattr(utils_mod, "supports_color", lambda: True)
    assert utils_mod.colorize("hello", "") == "hello"


# ── print_check: colour ───────────────────────────────────────────────────────


@pytest.fixture
def no_color(monkeypatch):
    monkeypatch.setattr(utils_mod, "supports_color", lambda: False)


@pytest.fixture
def with_color(monkeypatch):
    monkeypatch.setattr(utils_mod, "supports_color", lambda: True)


def test_print_check_output_is_plain_without_color(capsys, no_color):
    from vesper.commands.utils import FAIL, NA, OK, WARN, print_check

    for status in (OK, WARN, FAIL, NA):
        print_check(False, "message", "a fix", status=status)

    out = capsys.readouterr().out
    assert "\x1b" not in out, "escape codes leaked into a redirected stream"


def test_print_check_plain_output_keeps_every_label(capsys, no_color):
    """Dropping colour must not drop information — the labels carry the state."""
    from vesper.commands.utils import FAIL, NA, OK, WARN, print_check

    for status in (OK, WARN, FAIL, NA):
        print_check(False, "message", status=status)

    out = capsys.readouterr().out
    for label in ("[OK]", "[WARN]", "[FAIL]", "[N/A]"):
        assert label in out, label


@pytest.mark.parametrize("status, color", [
    ("ok", "\x1b[32m"),
    ("warn", "\x1b[33m"),
    ("fail", "\x1b[31m"),
    ("na", "\x1b[2m"),
])
def test_print_check_colors_each_state(capsys, with_color, status, color):
    from vesper.commands.utils import print_check

    print_check(False, "x", status=status)
    out = capsys.readouterr().out
    assert color in out
    assert out.endswith("x\n"), "the message itself must not be coloured"


def test_print_check_color_resets_after_the_label(capsys, with_color):
    """An unterminated sequence would tint the rest of the terminal."""
    from vesper.commands.utils import print_check

    print_check(True, "fine")
    assert capsys.readouterr().out == "\x1b[32m[OK]\x1b[0m fine\n"


# ── print_check: states ───────────────────────────────────────────────────────


def test_print_check_na_state(capsys, no_color):
    from vesper.commands.utils import NA, print_check

    print_check(False, "no protocol here", status=NA)
    assert "[N/A] no protocol here" in capsys.readouterr().out


def test_print_check_na_never_prints_a_fix(capsys, no_color):
    """N/A means nothing can be installed — a Fix line would send people hunting."""
    from vesper.commands.utils import NA, print_check

    print_check(False, "unsupported", "pip install something", status=NA)
    assert "Fix" not in capsys.readouterr().out


def test_print_check_ok_state_ignores_a_fix(capsys, no_color):
    from vesper.commands.utils import OK, print_check

    print_check(True, "fine", "do not print me", status=OK)
    assert "Fix" not in capsys.readouterr().out


def test_print_check_explicit_status_overrides_the_flags(capsys, no_color):
    from vesper.commands.utils import WARN, print_check

    print_check(False, "x", critical=True, status=WARN)
    assert "[WARN]" in capsys.readouterr().out


def test_print_check_warn_still_shows_its_fix(capsys, no_color):
    from vesper.commands.utils import print_check

    print_check(False, "optional", "install it", critical=False)
    out = capsys.readouterr().out
    assert "[WARN]" in out and "Fix: install it" in out


# ── print_check: unchanged behaviour for existing callers ─────────────────────


def test_print_check_ok(capsys, no_color):
    from vesper.commands.utils import print_check

    print_check(True, "everything is fine")
    assert capsys.readouterr().out == "[OK] everything is fine\n"


def test_print_check_failure_is_critical_by_default(capsys, no_color):
    """The existing callers pass no flag and must keep printing [FAIL]."""
    from vesper.commands.utils import print_check

    print_check(False, "broken")
    assert "[FAIL] broken" in capsys.readouterr().out


def test_print_check_non_critical_failure_warns(capsys, no_color):
    from vesper.commands.utils import print_check

    print_check(False, "optional thing", critical=False)
    out = capsys.readouterr().out
    assert "[WARN] optional thing" in out
    assert "[FAIL]" not in out


def test_print_check_prints_the_fix_when_it_failed(capsys, no_color):
    from vesper.commands.utils import print_check

    print_check(False, "broken", "run this")
    assert "Fix: run this" in capsys.readouterr().out


def test_print_check_hides_the_fix_when_it_passed(capsys, no_color):
    """Nothing to fix means nothing to print, whatever the caller passed."""
    from vesper.commands.utils import print_check

    print_check(True, "fine", "run this")
    assert "Fix" not in capsys.readouterr().out
