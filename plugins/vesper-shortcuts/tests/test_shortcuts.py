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
    # f4 is a named key, so pynput wants it bracketed. This assertion used to
    # read "<alt>+f4", which is what pynput rejects.
    p = ShortcutsPlugin()
    assert p._to_pynput("alt+f4") == "<alt>+<f4>"


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


@pytest.mark.parametrize("accelerator, expected", [
    ("ctrl+alt+space", "<ctrl>+<alt>+<space>"),
    ("ctrl+shift+enter", "<ctrl>+<shift>+<enter>"),
    ("ctrl+alt+up", "<ctrl>+<alt>+<up>"),
    ("ctrl+alt+backspace", "<ctrl>+<alt>+<backspace>"),
    ("ctrl+f12", "<ctrl>+<f12>"),
])
def test_to_pynput_brackets_named_keys(accelerator, expected):
    """The whole class of key that could not be registered before."""
    p = ShortcutsPlugin()
    assert p._to_pynput(accelerator) == expected


@pytest.mark.parametrize("spelling, canonical", [
    ("escape", "esc"),
    ("return", "enter"),
    ("del", "delete"),
    ("pgup", "page_up"),
    ("pagedown", "page_down"),
    ("arrowleft", "left"),
    ("spacebar", "space"),
    ("printscreen", "print_screen"),
])
def test_to_pynput_accepts_common_spellings(spelling, canonical):
    p = ShortcutsPlugin()
    assert p._to_pynput(f"ctrl+{spelling}") == f"<ctrl>+<{canonical}>"


def test_to_pynput_leaves_punctuation_keys_alone():
    p = ShortcutsPlugin()
    assert p._to_pynput("ctrl+/") == "<ctrl>+/"


# ── Against the real pynput ───────────────────────────────────────────────────
#
# The mock above accepts anything, which is exactly how "ctrl+alt+space" shipped
# as the documented example of an accelerator while being impossible to register.
# These check the conversion against the parser it actually has to satisfy.

real_keyboard = None
try:  # pragma: no cover - depends on the machine having an input backend
    from pynput import keyboard as real_keyboard
except Exception:  # ImportError, or a headless X failure
    pass

requires_pynput = pytest.mark.skipif(
    real_keyboard is None, reason="pynput cannot load an input backend here"
)


@requires_pynput
@pytest.mark.parametrize("accelerator", [
    "ctrl+alt+space", "ctrl+shift+enter", "alt+f4", "ctrl+alt+up",
    "ctrl+alt+esc", "ctrl+alt+delete", "ctrl+k", "cmd+shift+3",
])
def test_documented_accelerators_parse_in_pynput(accelerator):
    # real_keyboard was imported before the autouse mock replaced sys.modules,
    # and _to_pynput is pure string work, so this needs no unpatching.
    p = ShortcutsPluginDirect()
    real_keyboard.HotKey.parse(p._to_pynput(accelerator))


@requires_pynput
def test_every_named_key_pynput_knows_can_be_used_in_an_accelerator():
    p = ShortcutsPluginDirect()
    # ctrl+ctrl is a duplicate, not a shortcut — skip the modifiers themselves.
    modifiers = {"ctrl", "ctrl_r", "shift", "shift_r", "alt", "alt_r", "alt_gr", "cmd", "cmd_r"}
    for key in real_keyboard.Key:
        if key.name in modifiers:
            continue
        real_keyboard.HotKey.parse(p._to_pynput(f"ctrl+{key.name}"))


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


def test_remove_unknown_key_leaves_the_listener_alone(mock_pynput):
    """Restarting the listener for a no-op is a pointless window to race in."""
    mock_kb, mock_listener = mock_pynput
    p = ShortcutsPlugin()
    p.add("ctrl+a", lambda: None)
    mock_listener.stop.reset_mock()
    p.remove("ctrl+z")
    mock_listener.stop.assert_not_called()


# ── Bad accelerators must not take working ones down with them ────────────────


def _reject_unknown_keys(mock_kb):
    """Give the mocked pynput the one behaviour that matters here: refusing a
    key it does not know, the way the real HotKey.parse does."""
    known = {"space", "enter", "esc", "f4", "up", "delete", "ctrl", "shift", "alt", "cmd"}

    def parse(spec):
        for part in spec.split("+"):
            if part.startswith("<") and part.endswith(">"):
                if part[1:-1] not in known:
                    raise ValueError(part)
            elif len(part) != 1:
                raise ValueError(part)
        return []

    mock_kb.HotKey.parse.side_effect = parse
    mock_kb.Key = []
    return mock_kb


def test_invalid_accelerator_raises_valueerror_that_names_it(mock_pynput):
    mock_kb, _ = mock_pynput
    _reject_unknown_keys(mock_kb)
    p = ShortcutsPlugin()

    with pytest.raises(ValueError) as excinfo:
        p.add("ctrl+alt+nosuchkey", lambda: None)

    message = str(excinfo.value)
    assert "ctrl+alt+nosuchkey" in message
    assert "nosuchkey" in message


def test_invalid_accelerator_keeps_existing_shortcuts_working(mock_pynput):
    """
    The regression: a rejected accelerator used to stay in the map, so every
    later add() re-raised on it and the app lost every shortcut it already had.
    """
    mock_kb, mock_listener = mock_pynput
    _reject_unknown_keys(mock_kb)
    p = ShortcutsPlugin()
    p.add("ctrl+alt+space", lambda: None)

    with pytest.raises(ValueError):
        p.add("ctrl+alt+nosuchkey", lambda: None)

    assert list(p._hotkeys) == ["ctrl+alt+space"]

    # …and the plugin still works afterwards.
    p.add("ctrl+alt+up", lambda: None)
    assert sorted(p._hotkeys) == ["ctrl+alt+space", "ctrl+alt+up"]


def test_listener_that_fails_to_start_rolls_back_to_the_previous_set(mock_pynput):
    mock_kb, mock_listener = mock_pynput
    p = ShortcutsPlugin()
    p.add("ctrl+a", lambda: None)

    # The next construction blows up; the one after it (the rollback) succeeds.
    mock_kb.GlobalHotKeys.side_effect = [RuntimeError("no input backend"), mock_listener]

    with pytest.raises(RuntimeError):
        p.add("ctrl+b", lambda: None)

    assert list(p._hotkeys) == ["ctrl+a"]
    assert p._listener is mock_listener


def test_add_survives_pynput_stop_race(mock_pynput):
    """
    pynput's stop() raises AttributeError when the backend thread has not
    finished starting. That used to escape add() and leave the plugin holding a
    listener it believed it had replaced.
    """
    mock_kb, mock_listener = mock_pynput
    p = ShortcutsPlugin()
    p.add("ctrl+a", lambda: None)
    mock_listener.stop.side_effect = AttributeError("_display_record")

    p.add("ctrl+b", lambda: None)

    assert sorted(p._hotkeys) == ["ctrl+a", "ctrl+b"]
    assert p._listener is mock_listener


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
