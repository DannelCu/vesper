"""Tests for vesper-notify — mocked desktop-notifier, real asyncio bridge."""
from __future__ import annotations

import pytest

from vesper import App
from vesper_notify import NotifyPlugin


def _send(app, **args):
    payload = {"title": "Hello", **args}
    return app.ipc.handle({"id": "1", "command": "vesper:notify:send", "args": payload})


@pytest.fixture
def app():
    application = App(plugins=[NotifyPlugin(app_name="TestApp")])
    yield application
    application.ipc.close()


def test_command_registered(app):
    assert "vesper:notify:send" in app.registry._commands


def test_send_builds_the_notifier_call(app, mock_desktop_notifier):
    resp = _send(app, body="World", sound=True)
    assert resp["ok"] is True
    assert isinstance(resp["result"], str) and resp["result"]

    mock_desktop_notifier.DesktopNotifier.assert_called_once_with(app_name="TestApp")
    send = mock_desktop_notifier.DesktopNotifier.return_value.send
    send.assert_awaited_once()
    kwargs = send.await_args.kwargs
    assert kwargs["title"] == "Hello"
    assert kwargs["message"] == "World"
    assert kwargs["sound"] == "DEFAULT_SOUND"
    assert callable(kwargs["on_clicked"])


def test_send_without_sound_omits_it(app, mock_desktop_notifier):
    _send(app)
    kwargs = mock_desktop_notifier.DesktopNotifier.return_value.send.await_args.kwargs
    assert "sound" not in kwargs


def test_buttons_become_button_objects(app, mock_desktop_notifier):
    _send(app, buttons=["Open", "Dismiss"])
    kwargs = mock_desktop_notifier.DesktopNotifier.return_value.send.await_args.kwargs
    labels = [b["button"]["title"] for b in kwargs["buttons"]]
    assert labels == ["Open", "Dismiss"]


def test_icon_becomes_icon_object(app, mock_desktop_notifier, tmp_path):
    _send(app, icon=str(tmp_path / "icon.png"))
    kwargs = mock_desktop_notifier.DesktopNotifier.return_value.send.await_args.kwargs
    assert "icon" in kwargs


def test_click_callback_emits_event_with_id(app, mock_desktop_notifier):
    emitted = []
    app.window.emit = lambda event, payload: emitted.append((event, payload))

    notify_id = _send(app)["result"]

    kwargs = mock_desktop_notifier.DesktopNotifier.return_value.send.await_args.kwargs
    kwargs["on_clicked"]()

    assert ("notify:clicked", {"id": notify_id}) in emitted


def test_button_press_emits_action_event(app, mock_desktop_notifier):
    emitted = []
    app.window.emit = lambda event, payload: emitted.append((event, payload))

    notify_id = _send(app, buttons=["Open"])["result"]

    kwargs = mock_desktop_notifier.DesktopNotifier.return_value.send.await_args.kwargs
    kwargs["buttons"][0]["button"]["on_pressed"]()

    assert ("notify:action", {"id": notify_id, "button": "Open"}) in emitted


def test_backend_failure_surfaces_as_ipc_error(app, mock_desktop_notifier):
    send = mock_desktop_notifier.DesktopNotifier.return_value.send
    send.side_effect = RuntimeError("no notification server")

    resp = _send(app)
    assert resp["ok"] is False
    assert resp["error"]["type"] == "RuntimeError"


def test_notifier_is_created_once(app, mock_desktop_notifier):
    _send(app)
    _send(app)
    assert mock_desktop_notifier.DesktopNotifier.call_count == 1


def test_core_notify_untouched(app):
    # The minimal fallback stays registered and independent of this plugin.
    assert "vesper:notify" in app.registry._commands


def test_plugin_alias():
    from vesper_notify import Plugin
    from vesper_notify.plugin import NotifyPlugin as Direct
    assert Plugin is Direct


def test_sdk_path_exists():
    path = NotifyPlugin.sdk_path()
    assert path is not None
    assert path.name == "vesper-notify.js"
