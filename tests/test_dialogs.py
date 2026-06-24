"""Tests for native file dialog support."""
from unittest.mock import MagicMock, patch

import pytest

from vesper import App
from vesper.core.window import Window, _to_file_types


# ── _to_file_types ────────────────────────────────────────────────────────────


def test_to_file_types_none_returns_empty():
    assert _to_file_types(None) == ()


def test_to_file_types_empty_list_returns_empty():
    assert _to_file_types([]) == ()


def test_to_file_types_single_extension():
    result = _to_file_types([{"name": "PDF", "extensions": ["pdf"]}])
    assert result == ("PDF (*.pdf)",)


def test_to_file_types_multiple_extensions():
    result = _to_file_types([{"name": "Images", "extensions": ["png", "jpg", "gif"]}])
    assert result == ("Images (*.png;*.jpg;*.gif)",)


def test_to_file_types_wildcard_extension():
    result = _to_file_types([{"name": "All Files", "extensions": ["*"]}])
    assert result == ("All Files (*.*)",)


def test_to_file_types_multiple_filters():
    result = _to_file_types([
        {"name": "PDF", "extensions": ["pdf"]},
        {"name": "All Files", "extensions": ["*"]},
    ])
    assert result == ("PDF (*.pdf)", "All Files (*.*)")


def test_to_file_types_missing_name_defaults():
    result = _to_file_types([{"extensions": ["txt"]}])
    assert result == ("Files (*.txt)",)


def test_to_file_types_missing_extensions_defaults_wildcard():
    result = _to_file_types([{"name": "Any"}])
    assert result == ("Any (*.*)",)


# ── Window.open_dialog ────────────────────────────────────────────────────────


def test_open_dialog_raises_when_no_window():
    w = Window()
    with pytest.raises(RuntimeError, match="window is not created"):
        w.open_dialog()


def test_open_dialog_returns_list_of_paths(monkeypatch):
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ("/home/user/a.pdf", "/home/user/b.pdf")
    w.window = mock_win

    import webview
    monkeypatch.setattr(webview, "OPEN_DIALOG", 10)

    result = w.open_dialog(multiple=True)
    assert result == ["/home/user/a.pdf", "/home/user/b.pdf"]


def test_open_dialog_returns_none_on_cancel(monkeypatch):
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = None
    w.window = mock_win

    import webview
    monkeypatch.setattr(webview, "OPEN_DIALOG", 10)

    assert w.open_dialog() is None


def test_open_dialog_returns_none_on_empty_tuple(monkeypatch):
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ()
    w.window = mock_win

    import webview
    monkeypatch.setattr(webview, "OPEN_DIALOG", 10)

    assert w.open_dialog() is None


def test_open_dialog_passes_multiple_flag(monkeypatch):
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ("/f.txt",)
    w.window = mock_win

    import webview
    monkeypatch.setattr(webview, "OPEN_DIALOG", 10)

    w.open_dialog(multiple=True)
    _, kwargs = mock_win.create_file_dialog.call_args
    assert kwargs["allow_multiple"] is True


def test_open_dialog_passes_filters(monkeypatch):
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ("/f.pdf",)
    w.window = mock_win

    import webview
    monkeypatch.setattr(webview, "OPEN_DIALOG", 10)

    w.open_dialog(filters=[{"name": "PDF", "extensions": ["pdf"]}])
    _, kwargs = mock_win.create_file_dialog.call_args
    assert kwargs["file_types"] == ("PDF (*.pdf)",)


def test_open_dialog_passes_directory(monkeypatch):
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ("/f.txt",)
    w.window = mock_win

    import webview
    monkeypatch.setattr(webview, "OPEN_DIALOG", 10)

    w.open_dialog(directory="/home/user")
    _, kwargs = mock_win.create_file_dialog.call_args
    assert kwargs["directory"] == "/home/user"


# ── Window.save_dialog ────────────────────────────────────────────────────────


def test_save_dialog_raises_when_no_window():
    w = Window()
    with pytest.raises(RuntimeError, match="window is not created"):
        w.save_dialog()


def test_save_dialog_returns_string(monkeypatch):
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ("/home/user/report.pdf",)
    w.window = mock_win

    import webview
    monkeypatch.setattr(webview, "SAVE_DIALOG", 20)

    result = w.save_dialog(filename="report.pdf")
    assert result == "/home/user/report.pdf"


def test_save_dialog_returns_none_on_cancel(monkeypatch):
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = None
    w.window = mock_win

    import webview
    monkeypatch.setattr(webview, "SAVE_DIALOG", 20)

    assert w.save_dialog() is None


def test_save_dialog_passes_filename(monkeypatch):
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ("/out.pdf",)
    w.window = mock_win

    import webview
    monkeypatch.setattr(webview, "SAVE_DIALOG", 20)

    w.save_dialog(filename="out.pdf")
    _, kwargs = mock_win.create_file_dialog.call_args
    assert kwargs["save_filename"] == "out.pdf"


# ── Window.pick_folder ────────────────────────────────────────────────────────


def test_pick_folder_raises_when_no_window():
    w = Window()
    with pytest.raises(RuntimeError, match="window is not created"):
        w.pick_folder()


def test_pick_folder_returns_list(monkeypatch):
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ("/home/user/docs",)
    w.window = mock_win

    import webview
    monkeypatch.setattr(webview, "FOLDER_DIALOG", 30)

    result = w.pick_folder()
    assert result == ["/home/user/docs"]


def test_pick_folder_returns_none_on_cancel(monkeypatch):
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = None
    w.window = mock_win

    import webview
    monkeypatch.setattr(webview, "FOLDER_DIALOG", 30)

    assert w.pick_folder() is None


def test_pick_folder_multiple(monkeypatch):
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ("/a", "/b")
    w.window = mock_win

    import webview
    monkeypatch.setattr(webview, "FOLDER_DIALOG", 30)

    result = w.pick_folder(multiple=True)
    assert result == ["/a", "/b"]

    _, kwargs = mock_win.create_file_dialog.call_args
    assert kwargs["allow_multiple"] is True


# ── App registers dialog commands ─────────────────────────────────────────────


def test_app_registers_dialog_open():
    app = App()
    assert "vesper:dialog:open" in app.registry._commands


def test_app_registers_dialog_save():
    app = App()
    assert "vesper:dialog:save" in app.registry._commands


def test_app_registers_dialog_folder():
    app = App()
    assert "vesper:dialog:folder" in app.registry._commands


def test_dialog_commands_not_in_user_namespace():
    """vesper: commands must not shadow any user-registered command."""
    app = App()

    @app.command
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    user_cmds = [k for k in app.registry._commands if not k.startswith("vesper:")]
    assert user_cmds == ["greet"]


# ── IPC routes dialog commands ────────────────────────────────────────────────


def test_ipc_routes_open_dialog(monkeypatch):
    import webview
    monkeypatch.setattr(webview, "OPEN_DIALOG", 10)

    app = App()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ("/selected.pdf",)
    app.window.window = mock_win

    resp = app.ipc.handle({
        "id": "1",
        "command": "vesper:dialog:open",
        "args": {"filters": [{"name": "PDF", "extensions": ["pdf"]}]},
    })

    assert resp["ok"] is True
    assert resp["result"] == ["/selected.pdf"]


def test_ipc_routes_save_dialog(monkeypatch):
    import webview
    monkeypatch.setattr(webview, "SAVE_DIALOG", 20)

    app = App()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ("/out/report.pdf",)
    app.window.window = mock_win

    resp = app.ipc.handle({
        "id": "1",
        "command": "vesper:dialog:save",
        "args": {"filename": "report.pdf"},
    })

    assert resp["ok"] is True
    assert resp["result"] == "/out/report.pdf"


def test_ipc_dialog_returns_none_on_cancel(monkeypatch):
    import webview
    monkeypatch.setattr(webview, "OPEN_DIALOG", 10)

    app = App()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = None
    app.window.window = mock_win

    resp = app.ipc.handle({
        "id": "1",
        "command": "vesper:dialog:open",
        "args": {},
    })

    assert resp["ok"] is True
    assert resp["result"] is None


def test_ipc_dialog_error_when_no_window():
    app = App()
    # window.window is None — calling the dialog raises RuntimeError
    resp = app.ipc.handle({
        "id": "1",
        "command": "vesper:dialog:open",
        "args": {},
    })
    assert resp["ok"] is False
    assert resp["error"]["type"] == "RuntimeError"


# ── sync-types excludes vesper: commands ─────────────────────────────────────


def test_sync_types_excludes_dialog_commands():
    from vesper.commands.sync_types import generate_dts

    app = App()

    @app.command
    def greet() -> str:
        return "hi"

    user_cmds = {k: v for k, v in app.registry._commands.items() if not k.startswith("vesper:")}
    dts = generate_dts(user_cmds)

    assert '"greet"' in dts
    assert "vesper:dialog" not in dts
