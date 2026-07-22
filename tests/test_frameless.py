"""Tests for frameless/transparent window chrome, min size, and backdrop materials."""
from __future__ import annotations

import ctypes
from unittest.mock import MagicMock

import pytest

import vesper.core.window as window_mod
from vesper import App
from vesper.core import capabilities, window_effects
from vesper.core.config import WindowConfig
from vesper.core.ipc import IPC
from vesper.core.registry import CommandRegistry
from vesper.core.window import Window, _chrome_kwargs


# ── WindowConfig validation ──────────────────────────────────────────────────


def test_chrome_defaults():
    cfg = WindowConfig()
    assert cfg.frameless is False
    assert cfg.easy_drag is True
    assert cfg.transparent is False
    assert cfg.vibrancy is False
    assert cfg.min_width is None
    assert cfg.min_height is None


@pytest.mark.parametrize("field", ["frameless", "easy_drag", "transparent", "vibrancy"])
def test_chrome_flags_must_be_boolean(field):
    with pytest.raises(TypeError):
        WindowConfig(**{field: "yes"})


def test_min_size_must_be_set_together():
    with pytest.raises(ValueError):
        WindowConfig(min_width=400)
    with pytest.raises(ValueError):
        WindowConfig(min_height=300)


def test_min_size_must_be_positive():
    with pytest.raises(ValueError):
        WindowConfig(min_width=0, min_height=300)


def test_min_size_accepted():
    cfg = WindowConfig(min_width=400, min_height=300)
    assert (cfg.min_width, cfg.min_height) == (400, 300)


# ── _chrome_kwargs ───────────────────────────────────────────────────────────


def test_chrome_kwargs_omit_min_size_by_default():
    kwargs = _chrome_kwargs(WindowConfig())
    assert "min_size" not in kwargs
    assert kwargs["frameless"] is False


def test_chrome_kwargs_include_min_size_when_configured():
    kwargs = _chrome_kwargs(WindowConfig(min_width=640, min_height=480))
    assert kwargs["min_size"] == (640, 480)


# ── propagation to webview.create_window ─────────────────────────────────────


def _create(monkeypatch, config, secondary=None):
    mock_wv = MagicMock()
    mock_wv.create_window.return_value = MagicMock()
    monkeypatch.setattr(window_mod, "webview", mock_wv)
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:3000")

    w = Window()
    w.create(IPC(CommandRegistry()), config, secondary_windows=secondary)
    return mock_wv


def test_main_window_receives_chrome_kwargs(monkeypatch):
    config = WindowConfig(
        frontend="index.html", frameless=True, easy_drag=False,
        transparent=True, min_width=500, min_height=400,
    )
    mock_wv = _create(monkeypatch, config)

    kwargs = mock_wv.create_window.call_args[1]
    assert kwargs["frameless"] is True
    assert kwargs["easy_drag"] is False
    assert kwargs["transparent"] is True
    assert kwargs["min_size"] == (500, 400)


def test_secondary_window_receives_chrome_kwargs(monkeypatch):
    from vesper.core.window import WindowHandle

    handle = WindowHandle(WindowConfig(frontend="panel.html", frameless=True, vibrancy=True))
    mock_wv = _create(monkeypatch, WindowConfig(frontend="index.html"), secondary=[handle])

    sec_kwargs = mock_wv.create_window.call_args_list[1][1]
    assert sec_kwargs["frameless"] is True
    assert sec_kwargs["vibrancy"] is True


def test_app_forwards_chrome_kwargs_to_config():
    app = App(frameless=True, easy_drag=False, min_width=320, min_height=240)
    assert app.config.frameless is True
    assert app.config.easy_drag is False
    assert app.config.min_width == 320


def test_register_window_forwards_chrome_kwargs():
    app = App()
    handle = app.register_window(frontend="panel.html", frameless=True, transparent=True)
    assert handle._config.frameless is True
    assert handle._config.transparent is True


# ── window_effects (backdrop materials) ──────────────────────────────────────


def test_set_backdrop_unknown_kind_is_false():
    assert window_effects.set_backdrop("frosted-glass") is False


def test_set_backdrop_false_when_unsupported(monkeypatch):
    monkeypatch.setattr(window_effects, "supported", lambda: False)
    assert window_effects.set_backdrop("mica") is False


def test_supported_false_off_windows(monkeypatch):
    monkeypatch.setattr(window_effects.sys, "platform", "linux")
    assert window_effects.supported() is False


def _fake_windll(monkeypatch, *, hresult=0, hwnd=1234):
    windll = MagicMock()
    windll.user32.GetForegroundWindow.return_value = hwnd
    windll.dwmapi.DwmSetWindowAttribute.return_value = hresult
    monkeypatch.setattr(window_effects, "supported", lambda: True)
    monkeypatch.setattr(ctypes, "windll", windll, raising=False)
    return windll


def test_set_backdrop_builds_the_dwm_call(monkeypatch):
    windll = _fake_windll(monkeypatch)

    assert window_effects.set_backdrop("mica") is True

    args = windll.dwmapi.DwmSetWindowAttribute.call_args[0]
    assert args[0] == 1234                                   # hwnd
    assert args[1] == window_effects._DWMWA_SYSTEMBACKDROP_TYPE
    assert args[3] == ctypes.sizeof(ctypes.c_int)


def test_set_backdrop_degrades_on_dwm_rejection(monkeypatch):
    # A Windows 10 build that slipped past the version gate answers E_INVALIDARG.
    _fake_windll(monkeypatch, hresult=-2147024809)
    assert window_effects.set_backdrop("mica") is False


def test_set_backdrop_false_without_a_window(monkeypatch):
    _fake_windll(monkeypatch, hwnd=0)
    assert window_effects.set_backdrop("mica") is False


def test_backdrop_command_registered():
    assert "vesper:window:set_backdrop" in App().registry._commands


def test_mica_capability_reported():
    report = capabilities.probe()
    assert "mica" in report
    entry = report["mica"]
    assert entry["available"] in (True, False)
    # Nothing to install either way — a missing backdrop has no fix line.
    assert entry["fix"] is None
