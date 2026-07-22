"""Tests for DevTools wiring: `vesper dev` → VESPER_DEVTOOLS → webview.start(debug=True).

The inspector must exist exactly when the dev server does: `vesper dev` enables it
by default, `--no-devtools` turns it off, and `vesper run` / packaged builds never
set the variable at all.
"""
from __future__ import annotations

import argparse
from unittest.mock import MagicMock

import vesper.core.window as window_mod
from vesper.commands import dev as dev_mod
from vesper.core.config import WindowConfig
from vesper.core.ipc import IPC
from vesper.core.registry import CommandRegistry
from vesper.core.window import Window


# ── Window.show() reads VESPER_DEVTOOLS ──────────────────────────────────────


def _shown_window(monkeypatch):
    mock_wv = MagicMock()
    mock_wv.create_window.return_value = MagicMock()
    monkeypatch.setattr(window_mod, "webview", mock_wv)
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    w = Window()
    w.create(IPC(CommandRegistry()), WindowConfig(frontend="index.html"))
    w.show()
    return mock_wv


def test_show_passes_debug_when_devtools_env_set(monkeypatch):
    monkeypatch.setenv("VESPER_DEVTOOLS", "1")
    mock_wv = _shown_window(monkeypatch)

    mock_wv.start.assert_called_once()
    assert mock_wv.start.call_args[1].get("debug") is True


def test_show_omits_debug_without_devtools_env(monkeypatch):
    monkeypatch.delenv("VESPER_DEVTOOLS", raising=False)
    mock_wv = _shown_window(monkeypatch)

    mock_wv.start.assert_called_once()
    assert "debug" not in mock_wv.start.call_args[1]


# ── CLI flag ─────────────────────────────────────────────────────────────────


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    dev_mod.add_dev_parser(subparsers)
    return parser.parse_args(argv)


def test_dev_parser_defaults_to_devtools_on():
    args = _parse(["dev"])
    assert args.no_devtools is False


def test_dev_parser_accepts_no_devtools():
    args = _parse(["dev", "--no-devtools"])
    assert args.no_devtools is True


def test_handle_dev_forwards_devtools_flag(monkeypatch):
    captured = {}
    monkeypatch.setattr(dev_mod, "dev", lambda *, devtools: captured.setdefault("devtools", devtools))

    assert dev_mod.handle_dev(_parse(["dev", "--no-devtools"])) is True
    assert captured["devtools"] is False


# ── dev() puts the variable in the child environment ─────────────────────────


def _run_vanilla(monkeypatch, tmp_path, *, devtools: bool) -> dict:
    (tmp_path / "app.py").write_text("", encoding="utf-8")
    (tmp_path / "frontend").mkdir()

    captured = {}

    def fake_watch(project_dir, entrypoint, extra_env=None, **kwargs):
        captured["extra_env"] = extra_env

    server = MagicMock()
    server.server_address = ("127.0.0.1", 5000)
    monkeypatch.setattr(dev_mod, "_start_dev_server", lambda d: (server, [0]))
    monkeypatch.setattr(dev_mod, "_watch_and_restart", fake_watch)

    dev_mod.run_vanilla_dev(tmp_path, devtools=devtools)
    return captured["extra_env"]


def test_vanilla_dev_sets_devtools_env_by_default(monkeypatch, tmp_path):
    env = _run_vanilla(monkeypatch, tmp_path, devtools=True)
    assert env["VESPER_DEVTOOLS"] == "1"


def test_vanilla_dev_omits_devtools_env_when_disabled(monkeypatch, tmp_path):
    env = _run_vanilla(monkeypatch, tmp_path, devtools=False)
    assert "VESPER_DEVTOOLS" not in env
