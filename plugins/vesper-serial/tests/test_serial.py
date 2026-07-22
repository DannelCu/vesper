"""
Tests for vesper-serial.

Real pyserial with the loop:// handler stands in for hardware: whatever is
written comes back as received data, exercising the whole write → reader
thread → event path. Real devices are a documented manual test (README).
"""
from __future__ import annotations

import time

import pytest

from vesper import App
from vesper_serial import SerialPlugin


@pytest.fixture
def plugin():
    return SerialPlugin()


@pytest.fixture
def app(plugin):
    application = App(plugins=[plugin])
    yield application
    plugin.close_all()
    application.ipc.close()


def _events(app):
    events = []
    app.window.emit = lambda event, payload: events.append((event, payload))
    return events


def _wait_for_data(events, fragment, timeout=5.0):
    deadline = time.monotonic() + timeout
    collected = ""
    while time.monotonic() < deadline:
        collected = "".join(p["data"] for e, p in list(events) if e == "serial:data")
        if fragment in collected:
            return collected
        time.sleep(0.02)
    raise AssertionError(f"{fragment!r} never arrived; got {collected!r}")


def test_commands_registered(app):
    for cmd in (
        "vesper:serial:list_ports", "vesper:serial:open",
        "vesper:serial:write", "vesper:serial:close",
    ):
        assert cmd in app.registry._commands


def test_loopback_write_data_round_trip(app):
    events = _events(app)

    conn_id = app.ipc.handle({
        "id": "1", "command": "vesper:serial:open", "args": {"port": "loop://"},
    })["result"]

    written = app.ipc.handle({
        "id": "2", "command": "vesper:serial:write",
        "args": {"id": conn_id, "data": "hello board\n"},
    })
    assert written["ok"] is True
    assert written["result"] == len(b"hello board\n")

    _wait_for_data(events, "hello board")


def test_multiple_ports_have_independent_ids(app):
    events = _events(app)

    first = app.ipc.handle({
        "id": "1", "command": "vesper:serial:open", "args": {"port": "loop://"},
    })["result"]
    second = app.ipc.handle({
        "id": "2", "command": "vesper:serial:open", "args": {"port": "loop://"},
    })["result"]
    assert first != second

    app.ipc.handle({
        "id": "3", "command": "vesper:serial:write", "args": {"id": second, "data": "only-two"},
    })
    _wait_for_data(events, "only-two")

    from_first = [p for e, p in events if e == "serial:data" and p["id"] == first]
    assert from_first == []


def test_close_stops_reader_and_emits_closed(app):
    events = _events(app)

    conn_id = app.ipc.handle({
        "id": "1", "command": "vesper:serial:open", "args": {"port": "loop://"},
    })["result"]

    resp = app.ipc.handle({
        "id": "2", "command": "vesper:serial:close", "args": {"id": conn_id},
    })
    assert resp["result"] is True

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if ("serial:closed", {"id": conn_id}) in events:
            break
        time.sleep(0.02)
    assert ("serial:closed", {"id": conn_id}) in events
    assert conn_id not in app.ipc.registry._commands  # sanity: ids are not commands
    assert conn_id not in SerialPlugin.__dict__.get("_ports", {})


def test_close_unknown_id_is_false(app):
    resp = app.ipc.handle({"id": "1", "command": "vesper:serial:close", "args": {"id": 404}})
    assert resp["result"] is False


def test_write_to_unknown_id_is_a_clear_error(app):
    resp = app.ipc.handle({
        "id": "1", "command": "vesper:serial:write", "args": {"id": 404, "data": "x"},
    })
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ValueError"


def test_open_bad_port_is_an_ipc_error(app):
    resp = app.ipc.handle({
        "id": "1", "command": "vesper:serial:open",
        "args": {"port": "/dev/definitely-not-a-port-xyz"},
    })
    assert resp["ok"] is False


def test_close_all_empties_the_table(app, plugin):
    for _ in range(2):
        app.ipc.handle({"id": "1", "command": "vesper:serial:open", "args": {"port": "loop://"}})
    assert len(plugin._ports) == 2

    plugin.close_all()
    deadline = time.monotonic() + 5
    while plugin._ports and time.monotonic() < deadline:
        time.sleep(0.02)
    assert plugin._ports == {}


def test_list_ports_shape(app):
    resp = app.ipc.handle({"id": "1", "command": "vesper:serial:list_ports", "args": {}})
    assert resp["ok"] is True
    for entry in resp["result"]:
        assert set(entry) == {"device", "description", "hwid"}


def test_plugin_alias():
    from vesper_serial import Plugin
    from vesper_serial.plugin import SerialPlugin as Direct
    assert Plugin is Direct


def test_sdk_path_exists():
    path = SerialPlugin.sdk_path()
    assert path is not None
    assert path.name == "vesper-serial.js"
