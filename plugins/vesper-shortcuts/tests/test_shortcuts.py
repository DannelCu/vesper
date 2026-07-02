"""Tests for vesper-shortcuts plugin."""
from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from vesper import App
from vesper_shortcuts import ShortcutsPlugin
from vesper_shortcuts.plugin import ShortcutsPlugin as ShortcutsPluginDirect


# ── _to_pynput accelerator conversion ────────────────────────────────────────


def test_to_pynput_single_key():
    p = ShortcutsPlugin()
    assert p._to_pynput("s") == "s"


def test_to_pynput_ctrl_modifier():
    p = ShortcutsPlugin()
    assert p._to_pynput("ctrl+s") == "<ctrl>+s"


def test_to_pynput_multiple_modifiers():
    p = ShortcutsPlugin()
    assert p._to_pynput("ctrl+shift+s") == "<ctrl>+<shift>+s"


def test_to_pynput_alt_modifier():
    p = ShortcutsPlugin()
    assert p._to_pynput("alt+f4") == "<alt>+f4"


def test_to_pynput_cmd_modifier():
    p = ShortcutsPlugin()
    assert p._to_pynput("cmd+s") == "<cmd>+s"


def test_to_pynput_win_alias():
    p = ShortcutsPlugin()
    assert p._to_pynput("win+s") == "<cmd>+s"


def test_to_pynput_super_alias():
    p = ShortcutsPlugin()
    assert p._to_pynput("super+s") == "<cmd>+s"


def test_to_pynput_lowercases_input():
    p = ShortcutsPlugin()
    assert p._to_pynput("Ctrl+Shift+S") == "<ctrl>+<shift>+s"


# ── add() / remove() / remove_all() ──────────────────────────────────────────


def test_add_stores_hotkey(mock_pynput):
    p = ShortcutsPlugin()
    fn = lambda: None
    p.add("ctrl+s", fn)
    assert "ctrl+s" in p._hotkeys
    assert p._hotkeys["ctrl+s"] is fn


def test_add_starts_listener(mock_pynput):
    mock_kb, mock_listener = mock_pynput
    p = ShortcutsPlugin()
    p.add("ctrl+s", lambda: None)
    mock_kb.GlobalHotKeys.assert_called_once()
    mock_listener.start.assert_called_once()


def test_remove_deletes_hotkey(mock_pynput):
    p = ShortcutsPlugin()
    p.add("ctrl+s", lambda: None)
    p.remove("ctrl+s")
    assert "ctrl+s" not in p._hotkeys


def test_remove_unknown_key_is_noop(mock_pynput):
    p = ShortcutsPlugin()
    p.remove("ctrl+z")  # should not raise


def test_remove_all_clears_all(mock_pynput):
    p = ShortcutsPlugin()
    p.add("ctrl+a", lambda: None)
    p.add("ctrl+b", lambda: None)
    p.remove_all()
    assert p._hotkeys == {}


def test_restart_listener_stops_old_one(mock_pynput):
    mock_kb, mock_listener = mock_pynput
    p = ShortcutsPlugin()
    p.add("ctrl+a", lambda: None)
    p.add("ctrl+b", lambda: None)  # triggers restart
    mock_listener.stop.assert_called()


# ── IPC commands ──────────────────────────────────────────────────────────────


def test_register_command_registered():
    app = App(plugins=[ShortcutsPlugin()])
    assert "vesper:shortcuts:register" in app.registry._commands


def test_unregister_command_registered():
    app = App(plugins=[ShortcutsPlugin()])
    assert "vesper:shortcuts:unregister" in app.registry._commands


def test_unregister_all_command_registered():
    app = App(plugins=[ShortcutsPlugin()])
    assert "vesper:shortcuts:unregister_all" in app.registry._commands


def test_ipc_register_adds_hotkey(mock_pynput):
    plugin = ShortcutsPlugin()
    app = App(plugins=[plugin])

    resp = app.ipc.handle({
        "id": "1",
        "command": "vesper:shortcuts:register",
        "args": {"accelerator": "ctrl+k"},
    })

    assert resp["ok"] is True
    assert "ctrl+k" in plugin._hotkeys


def test_ipc_unregister_removes_hotkey(mock_pynput):
    plugin = ShortcutsPlugin()
    app = App(plugins=[plugin])

    plugin.add("ctrl+k", lambda: None)
    resp = app.ipc.handle({
        "id": "2",
        "command": "vesper:shortcuts:unregister",
        "args": {"accelerator": "ctrl+k"},
    })

    assert resp["ok"] is True
    assert "ctrl+k" not in plugin._hotkeys


def test_ipc_unregister_all_clears_hotkeys(mock_pynput):
    plugin = ShortcutsPlugin()
    app = App(plugins=[plugin])

    plugin.add("ctrl+a", lambda: None)
    plugin.add("ctrl+b", lambda: None)
    resp = app.ipc.handle({
        "id": "3",
        "command": "vesper:shortcuts:unregister_all",
        "args": {},
    })

    assert resp["ok"] is True
    assert plugin._hotkeys == {}


def test_ipc_register_emits_js_event_on_trigger(mock_pynput):
    plugin = ShortcutsPlugin()
    app = App(plugins=[plugin])
    emitted = []
    app.window.emit = lambda event, payload: emitted.append((event, payload))

    app.ipc.handle({
        "id": "1",
        "command": "vesper:shortcuts:register",
        "args": {"accelerator": "ctrl+k"},
    })

    # Simulate the hotkey firing
    plugin._hotkeys["ctrl+k"]()

    assert ("shortcut", {"accelerator": "ctrl+k"}) in emitted


# ── Plugin export ─────────────────────────────────────────────────────────────


def test_plugin_alias():
    from vesper_shortcuts import Plugin
    assert Plugin is ShortcutsPluginDirect
