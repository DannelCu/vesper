"""Tests for native file dialog support."""
import enum
import types
from unittest.mock import MagicMock, patch

import pytest

from vesper import App
from vesper.core import window as window_mod
from vesper.core.window import Window, _file_dialog_const, _to_file_types


# ── _file_dialog_const — PyWebView version tolerance ──────────────────────────


class _FakeFileDialog(enum.IntEnum):
    OPEN = 10
    FOLDER = 20
    SAVE = 30


def test_file_dialog_const_prefers_the_enum(monkeypatch):
    """PyWebView 5: the enum exists, so the deprecated name is never touched."""
    modern = types.SimpleNamespace(FileDialog=_FakeFileDialog)
    monkeypatch.setattr(window_mod, "webview", modern)

    assert _file_dialog_const("OPEN", "OPEN_DIALOG") is _FakeFileDialog.OPEN
    assert _file_dialog_const("SAVE", "SAVE_DIALOG") is _FakeFileDialog.SAVE
    assert _file_dialog_const("FOLDER", "FOLDER_DIALOG") is _FakeFileDialog.FOLDER


def test_file_dialog_const_falls_back_to_legacy_names(monkeypatch):
    """PyWebView 4: no FileDialog enum at all, only the module-level constants."""
    legacy = types.SimpleNamespace(OPEN_DIALOG=10, FOLDER_DIALOG=20, SAVE_DIALOG=30)
    assert not hasattr(legacy, "FileDialog")
    monkeypatch.setattr(window_mod, "webview", legacy)

    assert _file_dialog_const("OPEN", "OPEN_DIALOG") == 10
    assert _file_dialog_const("SAVE", "SAVE_DIALOG") == 30
    assert _file_dialog_const("FOLDER", "FOLDER_DIALOG") == 20


def test_file_dialog_const_falls_back_when_enum_lacks_the_member(monkeypatch):
    """A FileDialog that exists but is missing a member must not resolve to None."""
    partial = types.SimpleNamespace(
        FileDialog=types.SimpleNamespace(OPEN=10), SAVE_DIALOG=30
    )
    monkeypatch.setattr(window_mod, "webview", partial)

    assert _file_dialog_const("SAVE", "SAVE_DIALOG") == 30


def test_resolved_constants_are_not_none():
    """Whatever PyWebView is installed, all three resolved at import time."""
    assert window_mod._FD_OPEN is not None
    assert window_mod._FD_SAVE is not None
    assert window_mod._FD_FOLDER is not None


def test_dialogs_pass_the_resolved_constants():
    """The deprecated spelling must not reach create_file_dialog."""
    w = Window()
    w.window = MagicMock()
    w.window.create_file_dialog.return_value = ("/f.txt",)

    for call, expected in (
        (w.open_dialog, window_mod._FD_OPEN),
        (w.save_dialog, window_mod._FD_SAVE),
        (w.pick_folder, window_mod._FD_FOLDER),
    ):
        call()
        assert w.window.create_file_dialog.call_args[0][0] is expected


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


def test_open_dialog_returns_list_of_paths():
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ("/home/user/a.pdf", "/home/user/b.pdf")
    w.window = mock_win

    result = w.open_dialog(multiple=True)
    assert result == ["/home/user/a.pdf", "/home/user/b.pdf"]


def test_open_dialog_returns_none_on_cancel():
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = None
    w.window = mock_win

    assert w.open_dialog() is None


def test_open_dialog_returns_none_on_empty_tuple():
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ()
    w.window = mock_win

    assert w.open_dialog() is None


def test_open_dialog_passes_multiple_flag():
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ("/f.txt",)
    w.window = mock_win

    w.open_dialog(multiple=True)
    _, kwargs = mock_win.create_file_dialog.call_args
    assert kwargs["allow_multiple"] is True


def test_open_dialog_passes_filters():
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ("/f.pdf",)
    w.window = mock_win

    w.open_dialog(filters=[{"name": "PDF", "extensions": ["pdf"]}])
    _, kwargs = mock_win.create_file_dialog.call_args
    assert kwargs["file_types"] == ("PDF (*.pdf)",)


def test_open_dialog_passes_directory():
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ("/f.txt",)
    w.window = mock_win

    w.open_dialog(directory="/home/user")
    _, kwargs = mock_win.create_file_dialog.call_args
    assert kwargs["directory"] == "/home/user"


# ── Window.save_dialog ────────────────────────────────────────────────────────


def test_save_dialog_raises_when_no_window():
    w = Window()
    with pytest.raises(RuntimeError, match="window is not created"):
        w.save_dialog()


def test_save_dialog_returns_string():
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ("/home/user/report.pdf",)
    w.window = mock_win

    result = w.save_dialog(filename="report.pdf")
    assert result == "/home/user/report.pdf"


def test_save_dialog_returns_none_on_cancel():
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = None
    w.window = mock_win

    assert w.save_dialog() is None


def test_save_dialog_passes_filename():
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ("/out.pdf",)
    w.window = mock_win

    w.save_dialog(filename="out.pdf")
    _, kwargs = mock_win.create_file_dialog.call_args
    assert kwargs["save_filename"] == "out.pdf"


# ── Window.pick_folder ────────────────────────────────────────────────────────


def test_pick_folder_raises_when_no_window():
    w = Window()
    with pytest.raises(RuntimeError, match="window is not created"):
        w.pick_folder()


def test_pick_folder_returns_list():
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ("/home/user/docs",)
    w.window = mock_win

    result = w.pick_folder()
    assert result == ["/home/user/docs"]


def test_pick_folder_returns_none_on_cancel():
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = None
    w.window = mock_win

    assert w.pick_folder() is None


def test_pick_folder_multiple():
    w = Window()
    mock_win = MagicMock()
    mock_win.create_file_dialog.return_value = ("/a", "/b")
    w.window = mock_win

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


def test_ipc_routes_open_dialog():
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


def test_ipc_routes_save_dialog():
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


def test_ipc_dialog_returns_none_on_cancel():
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
