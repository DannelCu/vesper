"""
Tests that frontend-supplied strings cannot become subprocess options.

Every case here uses a value starting with "-": if it reaches the helper binary as
its own argv entry, the binary parses it as a flag instead of as data.
"""
from __future__ import annotations

import ntpath
import os
from unittest.mock import patch

import pytest

from vesper.core import notify, shell


# ── notify-send ──────────────────────────────────────────────────────────────


def test_notify_linux_passes_dash_dash_before_text():
    with patch("vesper.core.notify.subprocess.run") as run:
        notify._notify_linux("title", "body")

    argv = run.call_args[0][0]
    assert argv[:2] == ["notify-send", "--"]
    assert argv[2:] == ["title", "body"]


@pytest.mark.parametrize("hostile", ["-u", "--help", "-t 1", "--expire-time=1"])
def test_notify_linux_option_like_title_stays_data(hostile):
    with patch("vesper.core.notify.subprocess.run") as run:
        notify._notify_linux(hostile, "body")

    argv = run.call_args[0][0]
    # The separator must come before the hostile value, so notify-send stops parsing.
    assert argv.index("--") < argv.index(hostile)


def test_notify_linux_option_like_body_stays_data():
    with patch("vesper.core.notify.subprocess.run") as run:
        notify._notify_linux("title", "--help")

    argv = run.call_args[0][0]
    assert argv.index("--") < argv.index("--help")


# ── reveal() ─────────────────────────────────────────────────────────────────


def _argv_for_reveal(path: str, platform: str, *, isdir: bool = True):
    # Only the Windows case needs its path rules simulated: on a POSIX host,
    # os.path would leave "/select,evil" looking like a Windows switch.
    #
    # The reverse is deliberately NOT simulated. abspath() on a relative path calls
    # os.getcwd(), which always returns a *host* path, so posixpath.abspath("-R") on
    # Windows yields the hybrid "D:\\a\\repo/-R" — neither POSIX-absolute nor
    # meaningful. The host's own abspath is fine here, because what these tests
    # assert is that the result cannot be read as an option, and that holds under
    # either set of path rules.
    abspath = ntpath.abspath if platform == "win32" else os.path.abspath

    with patch("vesper.core.shell.sys.platform", platform), \
         patch("vesper.core.shell.os.path.abspath", abspath), \
         patch("vesper.core.shell.os.path.isdir", return_value=isdir), \
         patch("vesper.core.shell.subprocess.run") as run:
        shell.reveal(path)
    return run.call_args[0][0]


def _assert_not_option_like(value: str, platform: str) -> None:
    """
    The property that matters: the argument cannot be parsed as a flag.

    Asserted directly rather than via isabs() — ntpath cannot produce a drive letter
    when the host cwd is posix, and since Python 3.13 a drive-less "\\foo" is not
    considered absolute, so isabs() would fail on a value that is perfectly safe.
    """
    assert not value.startswith("-"), f"{value!r} reads as a POSIX option"
    if platform == "win32":
        assert not value.startswith("/"), f"{value!r} reads as a Windows switch"


@pytest.mark.parametrize("platform", ["linux", "darwin", "win32"])
def test_reveal_never_passes_an_option_like_argument(platform):
    """A relative path starting with "-" must not survive as its own argv entry."""
    argv = _argv_for_reveal("-R", platform)

    # The path is always the final argument.
    _assert_not_option_like(argv[-1], platform)


@pytest.mark.parametrize("hostile", ["-R", "--version", "-a", "/select,"])
def test_reveal_linux_hostile_path_is_not_an_option(hostile):
    argv = _argv_for_reveal(hostile, "linux")
    assert argv[0] == "xdg-open"
    # Absoluteness is the mechanism; not being parseable as a flag is the point.
    # Asserting the mechanism would mean asserting the host's path rules.
    _assert_not_option_like(argv[1], "linux")


def test_reveal_linux_does_not_use_dash_dash():
    """
    xdg-open rejects any argument beginning with "-", including "--" itself, so a
    separator would break reveal() rather than harden it.
    """
    argv = _argv_for_reveal("/tmp", "linux")
    assert "--" not in argv


def test_reveal_macos_keeps_its_flag_and_a_safe_path():
    argv = _argv_for_reveal("-R", "darwin")
    assert argv[0] == "open"
    # The framework's own flag survives; the user-supplied value does not become one.
    assert argv[1] == "-R"
    _assert_not_option_like(argv[2], "darwin")


def test_reveal_windows_path_is_absolute_and_not_a_switch():
    argv = _argv_for_reveal("/select,evil", "win32")
    assert argv[0] == "explorer"
    assert argv[1] == "/select,"
    # The user-supplied part must not arrive as another "/switch".
    _assert_not_option_like(argv[2], "win32")


def test_reveal_linux_file_resolves_to_containing_directory(tmp_path):
    target = tmp_path / "file.txt"
    target.write_text("x")

    with patch("vesper.core.shell.sys.platform", "linux"), \
         patch("vesper.core.shell.subprocess.run") as run:
        shell.reveal(str(target))

    argv = run.call_args[0][0]
    assert argv[1] == str(tmp_path)


def test_reveal_linux_directory_is_passed_through(tmp_path):
    with patch("vesper.core.shell.sys.platform", "linux"), \
         patch("vesper.core.shell.subprocess.run") as run:
        shell.reveal(str(tmp_path))

    argv = run.call_args[0][0]
    assert argv[1] == str(tmp_path)
