"""Tests for vesper-sysinfo — real psutil (pure userspace reads, CI-safe)."""
from __future__ import annotations

import threading
import time

import pytest

from vesper import App
from vesper_sysinfo import SysinfoPlugin


@pytest.fixture
def plugin():
    return SysinfoPlugin()


@pytest.fixture
def app(plugin):
    application = App(plugins=[plugin])
    yield application
    plugin.unsubscribe()
    application.ipc.close()


def test_commands_registered(app):
    for cmd in (
        "vesper:sysinfo:snapshot", "vesper:sysinfo:subscribe", "vesper:sysinfo:unsubscribe",
    ):
        assert cmd in app.registry._commands


def test_snapshot_shape(app):
    resp = app.ipc.handle({"id": "1", "command": "vesper:sysinfo:snapshot", "args": {}})
    assert resp["ok"] is True
    info = resp["result"]

    assert set(info) == {"cpu", "memory", "disks", "net", "battery", "uptime"}
    assert info["cpu"]["count"] >= 1
    assert 0 <= info["cpu"]["percent"] <= 100 * info["cpu"]["count"]
    assert info["memory"]["total"] > 0
    assert 0 <= info["memory"]["percent"] <= 100
    assert info["uptime"] > 0
    for disk in info["disks"]:
        assert set(disk) == {"device", "mountpoint", "total", "used", "percent"}
    assert info["battery"] is None or set(info["battery"]) == {"percent", "plugged"}


def test_subscription_emits_ticks(app, plugin):
    events = []
    got_two = threading.Event()

    def emit(event, payload):
        events.append((event, payload))
        if len([e for e, _ in events if e == "sysinfo:tick"]) >= 2:
            got_two.set()

    app.window.emit = emit

    resp = app.ipc.handle({
        "id": "1", "command": "vesper:sysinfo:subscribe", "args": {"interval": 0.1},
    })
    assert resp["ok"] is True

    assert got_two.wait(timeout=10), f"expected ticks, got {events}"
    tick = events[0][1]
    assert "cpu" in tick and "memory" in tick


def test_unsubscribe_stops_cleanly_without_orphan_thread(app, plugin):
    app.window.emit = lambda *a: None
    plugin.subscribe(interval=0.1)

    thread = plugin._thread
    assert thread is not None and thread.is_alive()

    assert plugin.unsubscribe() is True
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert plugin._thread is None


def test_unsubscribe_without_subscription_is_false(app, plugin):
    assert plugin.unsubscribe() is False


def test_second_subscribe_retunes_instead_of_stacking(app, plugin):
    app.window.emit = lambda *a: None
    plugin.subscribe(interval=1.0)
    first_thread = plugin._thread

    plugin.subscribe(interval=0.2)
    assert plugin._thread is first_thread
    assert plugin._interval == 0.2

    plugin.unsubscribe()


def test_close_hook_registered(app, plugin):
    # The app's close hook must stop the ticker so the app never leaves an
    # orphan thread behind.
    assert plugin.unsubscribe in app._hooks.get("close", [])


def test_plugin_alias():
    from vesper_sysinfo import Plugin
    from vesper_sysinfo.plugin import SysinfoPlugin as Direct
    assert Plugin is Direct


def test_sdk_path_exists():
    path = SysinfoPlugin.sdk_path()
    assert path is not None
    assert path.name == "vesper-sysinfo.js"
