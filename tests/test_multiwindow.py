"""Tests for M3.2 multi-window support."""
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from vesper import App, WindowHandle
from vesper.core.config import WindowConfig
from vesper.core.window import Window


# ── WindowHandle unit ─────────────────────────────────────────────────────────


def test_window_handle_starts_with_no_win():
    cfg = WindowConfig(frontend="dist/index.html")
    handle = WindowHandle(cfg)
    assert handle._win is None


def test_window_handle_attach_sets_win():
    cfg = WindowConfig(frontend="dist/index.html")
    handle = WindowHandle(cfg)
    mock = MagicMock()
    handle._attach(mock)
    assert handle._win is mock


def test_window_handle_show_before_attach_is_noop():
    cfg = WindowConfig(frontend="dist/index.html")
    handle = WindowHandle(cfg)
    handle.show()  # must not raise


def test_window_handle_hide_before_attach_is_noop():
    cfg = WindowConfig(frontend="dist/index.html")
    handle = WindowHandle(cfg)
    handle.hide()


def test_window_handle_close_before_attach_is_noop():
    cfg = WindowConfig(frontend="dist/index.html")
    handle = WindowHandle(cfg)
    handle.close()


def test_window_handle_emit_before_attach_is_noop():
    cfg = WindowConfig(frontend="dist/index.html")
    handle = WindowHandle(cfg)
    handle.emit("ready", {"x": 1})


def test_window_handle_show_calls_win_show():
    cfg = WindowConfig(frontend="dist/index.html")
    handle = WindowHandle(cfg)
    mock = MagicMock()
    handle._attach(mock)
    handle.show()
    mock.show.assert_called_once()


def test_window_handle_hide_calls_win_hide():
    cfg = WindowConfig(frontend="dist/index.html")
    handle = WindowHandle(cfg)
    mock = MagicMock()
    handle._attach(mock)
    handle.hide()
    mock.hide.assert_called_once()


def test_window_handle_close_calls_win_destroy():
    cfg = WindowConfig(frontend="dist/index.html")
    handle = WindowHandle(cfg)
    mock = MagicMock()
    handle._attach(mock)
    handle.close()
    mock.destroy.assert_called_once()


def test_window_handle_emit_dispatches_custom_event():
    cfg = WindowConfig(frontend="dist/index.html")
    handle = WindowHandle(cfg)
    mock = MagicMock()
    handle._attach(mock)
    handle.emit("update", {"count": 3})
    js_call = mock.evaluate_js.call_args[0][0]
    assert 'vesper:update' in js_call
    assert '"count": 3' in js_call or '"count":3' in js_call


def test_window_handle_emit_null_payload():
    cfg = WindowConfig(frontend="dist/index.html")
    handle = WindowHandle(cfg)
    mock = MagicMock()
    handle._attach(mock)
    handle.emit("ping")
    js_call = mock.evaluate_js.call_args[0][0]
    assert 'vesper:ping' in js_call
    assert 'null' in js_call


# ── App.register_window ───────────────────────────────────────────────────────


def test_register_window_returns_handle():
    app = App()
    handle = app.register_window(frontend="dist/settings.html")
    assert isinstance(handle, WindowHandle)


def test_register_window_appended_to_list():
    app = App()
    h1 = app.register_window(frontend="dist/a.html")
    h2 = app.register_window(frontend="dist/b.html")
    assert h1 in app._secondary_windows
    assert h2 in app._secondary_windows
    assert len(app._secondary_windows) == 2


def test_register_window_config_stored():
    app = App()
    handle = app.register_window(
        title="Settings",
        width=400,
        height=300,
        frontend="dist/settings.html",
    )
    assert handle._config.title == "Settings"
    assert handle._config.width == 400
    assert handle._config.height == 300
    assert handle._config.frontend == "dist/settings.html"


def test_register_window_exported_from_package():
    from vesper import WindowHandle as WH
    assert WH is WindowHandle


def test_app_starts_with_empty_secondary_windows():
    app = App()
    assert app._secondary_windows == []


# ── Window.create with secondary_windows ─────────────────────────────────────


def _make_ipc_mock():
    from vesper.core.ipc import IPC
    from vesper.core.registry import CommandRegistry
    reg = CommandRegistry()
    return IPC(reg)


def test_create_secondary_window_calls_webview(tmp_path):
    html = tmp_path / "settings.html"
    html.write_text("<html></html>")

    main_html = tmp_path / "index.html"
    main_html.write_text("<html></html>")

    cfg_main = WindowConfig(frontend=str(main_html))
    cfg_sec = WindowConfig(title="Settings", frontend=str(html))
    handle = WindowHandle(cfg_sec)

    ipc = _make_ipc_mock()
    win = Window()

    created_windows = []

    def fake_create_window(**kwargs):
        m = MagicMock()
        m._kwargs = kwargs
        created_windows.append(m)
        return m

    import webview
    with patch.object(webview, "create_window", side_effect=fake_create_window):
        win.create(ipc_handler=ipc, config=cfg_main, secondary_windows=[handle])

    assert len(created_windows) == 2
    sec_kwargs = created_windows[1]._kwargs
    assert sec_kwargs["title"] == "Settings"
    assert sec_kwargs["hidden"] is True


def test_create_secondary_window_attaches_handle(tmp_path):
    html = tmp_path / "settings.html"
    html.write_text("<html></html>")
    main_html = tmp_path / "index.html"
    main_html.write_text("<html></html>")

    cfg_main = WindowConfig(frontend=str(main_html))
    cfg_sec = WindowConfig(frontend=str(html))
    handle = WindowHandle(cfg_sec)

    ipc = _make_ipc_mock()
    win = Window()

    fake_wins = []

    def fake_create_window(**kwargs):
        m = MagicMock()
        fake_wins.append(m)
        return m

    import webview
    with patch.object(webview, "create_window", side_effect=fake_create_window):
        win.create(ipc_handler=ipc, config=cfg_main, secondary_windows=[handle])

    assert handle._win is fake_wins[1]


def test_create_secondary_window_missing_frontend_raises(tmp_path):
    main_html = tmp_path / "index.html"
    main_html.write_text("<html></html>")

    cfg_main = WindowConfig(frontend=str(main_html))
    cfg_sec = WindowConfig(frontend=str(tmp_path / "nonexistent.html"))
    handle = WindowHandle(cfg_sec)

    ipc = _make_ipc_mock()
    win = Window()

    import webview
    with patch.object(webview, "create_window", return_value=MagicMock()):
        with pytest.raises(FileNotFoundError, match="Secondary window frontend"):
            win.create(ipc_handler=ipc, config=cfg_main, secondary_windows=[handle])


def test_no_secondary_windows_is_fine(tmp_path):
    html = tmp_path / "index.html"
    html.write_text("<html></html>")
    cfg = WindowConfig(frontend=str(html))
    ipc = _make_ipc_mock()
    win = Window()

    import webview
    with patch.object(webview, "create_window", return_value=MagicMock()):
        win.create(ipc_handler=ipc, config=cfg)  # no secondary_windows arg


def test_create_secondary_window_uses_dev_url(monkeypatch):
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:5173")

    cfg_main = WindowConfig(frontend="dist/index.html")
    cfg_sec = WindowConfig(title="Settings", frontend="dist/settings.html")
    handle = WindowHandle(cfg_sec)

    ipc = _make_ipc_mock()
    win = Window()
    created = []

    def fake_create_window(**kwargs):
        m = MagicMock()
        m._kwargs = kwargs
        created.append(m)
        return m

    import webview
    with patch.object(webview, "create_window", side_effect=fake_create_window):
        win.create(ipc_handler=ipc, config=cfg_main, secondary_windows=[handle])

    sec_url = created[1]._kwargs["url"]
    assert sec_url == "http://localhost:5173/settings.html"


def test_create_secondary_window_skips_disk_check_in_dev_mode(monkeypatch):
    monkeypatch.setenv("VESPER_DEV_URL", "http://localhost:5173")

    cfg_main = WindowConfig(frontend="dist/index.html")
    cfg_sec = WindowConfig(frontend="dist/nonexistent.html")
    handle = WindowHandle(cfg_sec)

    ipc = _make_ipc_mock()
    win = Window()

    import webview
    with patch.object(webview, "create_window", return_value=MagicMock()):
        win.create(ipc_handler=ipc, config=cfg_main, secondary_windows=[handle])


def test_multiple_secondary_windows(tmp_path):
    for name in ("index.html", "a.html", "b.html"):
        (tmp_path / name).write_text("<html></html>")

    cfg_main = WindowConfig(frontend=str(tmp_path / "index.html"))
    handles = [
        WindowHandle(WindowConfig(frontend=str(tmp_path / "a.html"))),
        WindowHandle(WindowConfig(frontend=str(tmp_path / "b.html"))),
    ]

    ipc = _make_ipc_mock()
    win = Window()
    created = []

    def fake_create_window(**kwargs):
        m = MagicMock()
        m._kwargs = kwargs
        created.append(m)
        return m

    import webview
    with patch.object(webview, "create_window", side_effect=fake_create_window):
        win.create(ipc_handler=ipc, config=cfg_main, secondary_windows=handles)

    assert len(created) == 3
    assert handles[0]._win is created[1]
    assert handles[1]._win is created[2]


# ── quit() closes every window ───────────────────────────────────────────────
#
# PyWebView's start() returns when the *last* window is gone. quit() used to
# destroy only the main one, so an app with a secondary window kept running with
# nothing on screen: the process never exited and quit() looked like a no-op.
# Found by building examples/media-vault, whose detached player is a second
# window — it hung on quit 4 times out of 4.


def _created_window(secondary_count: int):
    """A Window whose backend windows are all recording mocks."""
    from unittest.mock import MagicMock, patch

    from vesper.core.config import WindowConfig
    from vesper.core.ipc import IPC
    from vesper.core.registry import CommandRegistry
    from vesper.core.window import Window, WindowHandle
    import vesper.core.window as window_mod

    handles = [
        WindowHandle(WindowConfig(title=f"sec{i}", frontend="index.html"))
        for i in range(secondary_count)
    ]

    made = []

    def fake_create_window(**kwargs):
        win = MagicMock()
        made.append(win)
        return win

    window = Window()
    with patch.object(window_mod.webview, "create_window", side_effect=fake_create_window), \
         patch.dict("os.environ", {"VESPER_DEV_URL": "http://localhost:3000"}):
        window.create(
            IPC(CommandRegistry()),
            WindowConfig(frontend="index.html"),
            secondary_windows=handles or None,
        )

    return window, made


def test_quit_destroys_the_main_window():
    window, made = _created_window(0)
    window.quit()
    made[0].destroy.assert_called_once()


def test_quit_destroys_secondary_windows_too():
    window, made = _created_window(2)
    main, secondaries = made[0], made[1:]

    window.quit()

    for win in secondaries:
        win.destroy.assert_called_once()
    main.destroy.assert_called_once()


def test_quit_closes_secondaries_before_the_main_window():
    """The main window is what ends the loop, so it goes last."""
    window, made = _created_window(1)
    order = []
    made[0].destroy.side_effect = lambda: order.append("main")
    made[1].destroy.side_effect = lambda: order.append("secondary")

    window.quit()

    assert order == ["secondary", "main"]


def test_quit_survives_a_secondary_that_is_already_gone():
    """A window the user closed by hand must not strand the rest."""
    window, made = _created_window(2)
    made[1].destroy.side_effect = RuntimeError("already destroyed")

    window.quit()

    made[2].destroy.assert_called_once()
    made[0].destroy.assert_called_once()


def test_quit_is_idempotent():
    window, made = _created_window(1)
    window.quit()
    window.quit()   # must not raise, and must not re-destroy the secondary

    assert made[1].destroy.call_count == 1
