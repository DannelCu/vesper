"""
Tests for the opt-in power event monitor (vesper.core.power).

Nothing here touches a real bus, a real window or real hardware. Each backend is
split into a pure mapping function (raw platform signal → Vesper event name) and
the plumbing that feeds it; the mapping is tested directly, and the plumbing is
tested by driving it with a fake platform source.
"""
from __future__ import annotations

import importlib.util
import sys
import threading
import types
from unittest.mock import MagicMock

import pytest

from vesper.core import power


@pytest.fixture(autouse=True)
def _no_leftover_monitor():
    """A test that starts the process-wide monitor must not leak it into the next."""
    yield
    power.stop_power_monitor()
    power._warned.clear()


# ── PowerMonitor wiring ───────────────────────────────────────────────────────


class _FakeBackend:
    """Stands in for a platform backend; lets a test fire signals by hand."""

    def __init__(self, dispatch, *, available: bool = True) -> None:
        self.dispatch = dispatch
        self.available = available
        self.started = False
        self.stopped = False

    def start(self) -> bool:
        self.started = self.available
        return self.available

    def stop(self) -> None:
        self.stopped = True


@pytest.fixture
def fake_backend(monkeypatch):
    """Replace platform detection with a backend the test can drive."""
    created: list[_FakeBackend] = []

    def factory(dispatch):
        backend = _FakeBackend(dispatch)
        created.append(backend)
        return backend

    monkeypatch.setattr(power, "_make_backend", factory)
    return created


def test_monitor_emits_the_event_the_backend_reports(fake_backend):
    emit = MagicMock()
    monitor = power.PowerMonitor(emit)
    assert monitor.start() is True

    fake_backend[0].dispatch(power.SUSPEND)

    emit.assert_called_once_with("power:suspend", None)


@pytest.mark.parametrize(
    "event, expected",
    [
        (power.SUSPEND, "power:suspend"),
        (power.RESUME, "power:resume"),
        (power.LOCK, "power:lock"),
        (power.UNLOCK, "power:unlock"),
    ],
)
def test_monitor_forwards_every_event_name(fake_backend, event, expected):
    emit = MagicMock()
    monitor = power.PowerMonitor(emit)
    monitor.start()

    fake_backend[0].dispatch(event)

    emit.assert_called_once_with(expected, None)


def test_monitor_survives_a_raising_listener(fake_backend):
    """An exception on a backend thread must not kill the listener."""
    emit = MagicMock(side_effect=RuntimeError("listener exploded"))
    monitor = power.PowerMonitor(emit)
    monitor.start()

    fake_backend[0].dispatch(power.SUSPEND)   # must not raise
    fake_backend[0].dispatch(power.RESUME)

    assert emit.call_count == 2


def test_monitor_start_is_false_when_backend_unavailable(monkeypatch):
    monkeypatch.setattr(power, "_make_backend", lambda d: None)
    assert power.PowerMonitor(MagicMock()).start() is False


def test_monitor_start_is_false_when_backend_declines(monkeypatch):
    monkeypatch.setattr(
        power, "_make_backend", lambda d: _FakeBackend(d, available=False)
    )
    assert power.PowerMonitor(MagicMock()).start() is False


def test_monitor_start_is_false_when_backend_raises(monkeypatch):
    def boom(dispatch):
        raise OSError("no bus")

    monkeypatch.setattr(power, "_make_backend", boom)
    assert power.PowerMonitor(MagicMock()).start() is False


def test_monitor_stop_stops_the_backend(fake_backend):
    monitor = power.PowerMonitor(MagicMock())
    monitor.start()
    monitor.stop()
    assert fake_backend[0].stopped is True


def test_monitor_stop_without_start_is_a_noop():
    power.PowerMonitor(MagicMock()).stop()   # must not raise


def test_monitor_start_twice_reuses_the_backend(fake_backend):
    monitor = power.PowerMonitor(MagicMock())
    assert monitor.start() is True
    assert monitor.start() is True
    assert len(fake_backend) == 1


# ── module-level start/stop ───────────────────────────────────────────────────


def test_start_power_monitor_returns_false_without_a_backend(monkeypatch):
    monkeypatch.setattr(power, "_make_backend", lambda d: None)
    assert power.start_power_monitor(MagicMock()) is False
    assert power._monitor is None


def test_start_power_monitor_is_idempotent(fake_backend):
    assert power.start_power_monitor(MagicMock()) is True
    assert power.start_power_monitor(MagicMock()) is True
    assert len(fake_backend) == 1


def test_stop_power_monitor_clears_the_global(fake_backend):
    power.start_power_monitor(MagicMock())
    power.stop_power_monitor()
    assert power._monitor is None
    assert fake_backend[0].stopped is True


def test_stop_power_monitor_without_start_is_a_noop():
    power.stop_power_monitor()   # must not raise


# ── backend selection ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "platform, expected",
    [
        ("darwin", power._MacPowerEvents),
        ("win32", power._WindowsPowerEvents),
        ("linux", power._LinuxPowerEvents),
        ("freebsd", power._LinuxPowerEvents),   # D-Bus is the best guess elsewhere
    ],
)
def test_backend_matches_the_platform(monkeypatch, platform, expected):
    monkeypatch.setattr(power.sys, "platform", platform)
    assert isinstance(power._make_backend(lambda e: None), expected)


# ── Windows message mapping ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "msg, wparam, expected",
    [
        (power._WM_POWERBROADCAST, power._PBT_APMSUSPEND, power.SUSPEND),
        (power._WM_POWERBROADCAST, power._PBT_APMRESUMESUSPEND, power.RESUME),
        (power._WM_POWERBROADCAST, power._PBT_APMRESUMEAUTOMATIC, power.RESUME),
        (power._WM_WTSSESSION_CHANGE, power._WTS_SESSION_LOCK, power.LOCK),
        (power._WM_WTSSESSION_CHANGE, power._WTS_SESSION_UNLOCK, power.UNLOCK),
    ],
)
def test_windows_maps_its_messages(msg, wparam, expected):
    assert power._windows_event_for(msg, wparam) == expected


@pytest.mark.parametrize(
    "msg, wparam",
    [
        (power._WM_POWERBROADCAST, 0x0009),        # PBT_POWERSETTINGCHANGE
        (power._WM_WTSSESSION_CHANGE, 0x1),        # WTS_CONSOLE_CONNECT
        (0x0001, power._PBT_APMSUSPEND),           # WM_CREATE, wparam coincidence
        (power._WM_DESTROY, 0),
    ],
)
def test_windows_ignores_unrelated_messages(msg, wparam):
    assert power._windows_event_for(msg, wparam) is None


def test_windows_collapses_the_duplicate_resume():
    """
    A user-initiated wake sends RESUMEAUTOMATIC *and* RESUMESUSPEND. The frontend
    should see one resume, not two.
    """
    backend = power._WindowsPowerEvents(lambda e: None)

    assert backend._is_duplicate_resume(power.RESUME) is False
    assert backend._is_duplicate_resume(power.RESUME) is True


def test_windows_does_not_collapse_other_events():
    backend = power._WindowsPowerEvents(lambda e: None)
    assert backend._is_duplicate_resume(power.SUSPEND) is False
    assert backend._is_duplicate_resume(power.SUSPEND) is False


def test_windows_resume_fires_again_after_the_window(monkeypatch):
    backend = power._WindowsPowerEvents(lambda e: None)
    assert backend._is_duplicate_resume(power.RESUME) is False
    backend._last_resume -= 5.0     # pretend a real sleep cycle passed
    assert backend._is_duplicate_resume(power.RESUME) is False


# ── Linux D-Bus signal mapping ────────────────────────────────────────────────


def test_linux_prepare_for_sleep_true_is_suspend():
    assert power._linux_event_for(
        power._LOGIND_IFACE, "PrepareForSleep", (True,)
    ) == power.SUSPEND


def test_linux_prepare_for_sleep_false_is_resume():
    assert power._linux_event_for(
        power._LOGIND_IFACE, "PrepareForSleep", (False,)
    ) == power.RESUME


@pytest.mark.parametrize("iface", power._SCREENSAVER_IFACES)
def test_linux_screensaver_active_is_lock(iface):
    assert power._linux_event_for(iface, "ActiveChanged", (True,)) == power.LOCK
    assert power._linux_event_for(iface, "ActiveChanged", (False,)) == power.UNLOCK


def test_linux_logind_session_lock_and_unlock():
    session = "org.freedesktop.login1.Session"
    assert power._linux_event_for(session, "Lock", ()) == power.LOCK
    assert power._linux_event_for(session, "Unlock", ()) == power.UNLOCK


@pytest.mark.parametrize(
    "interface, member, body",
    [
        ("org.freedesktop.DBus", "NameOwnerChanged", ("a", "b", "c")),
        (power._LOGIND_IFACE, "SessionNew", ("1", "/path")),
        ("org.gnome.ScreenSaver", "WakeUpScreen", ()),
        (None, None, ()),                       # header fields can be absent
    ],
)
def test_linux_ignores_unrelated_signals(interface, member, body):
    assert power._linux_event_for(interface, member, body) is None


@pytest.mark.parametrize("member", ["PrepareForSleep", "ActiveChanged"])
def test_linux_ignores_a_signal_with_an_empty_body(member):
    """A boolean signal with no argument cannot be classified; it must not crash."""
    assert power._linux_event_for(power._LOGIND_IFACE, member, ()) is None
    assert power._linux_event_for("org.gnome.ScreenSaver", member, ()) is None


def test_linux_backend_declines_without_jeepney(monkeypatch):
    """The optional dependency being absent is a no-op, not an error."""
    monkeypatch.setitem(sys.modules, "jeepney", None)
    backend = power._LinuxPowerEvents(lambda e: None)
    assert backend.start() is False


def test_linux_backend_declines_when_no_bus_is_reachable(monkeypatch):
    monkeypatch.setattr(
        power._LinuxPowerEvents, "_listen", lambda self, bus, matches: False
    )
    backend = power._LinuxPowerEvents(lambda e: None)
    assert backend.start() is False


# ── Linux receive loop, driven by a fake connection ───────────────────────────


# The loop reads message headers through jeepney's own HeaderFields enum, so these
# tests use the real one — a hand-rolled stand-in would let a wrong key pass. jeepney
# is optional, so they skip when it is absent; the mapping tests above run everywhere.
# A module-level importorskip would take those down with it.
needs_jeepney = pytest.mark.skipif(
    importlib.util.find_spec("jeepney") is None,
    reason="jeepney is an optional dependency of the power event monitor",
)


class _FakeMessage:
    def __init__(self, interface, member, body) -> None:
        import jeepney

        self.header = types.SimpleNamespace(
            fields={jeepney.HeaderFields.interface: interface,
                    jeepney.HeaderFields.member: member}
        )
        self.body = body


class _FakeConnection:
    """Yields a scripted list of messages, then blocks like a quiet bus would."""

    def __init__(self, messages) -> None:
        self._messages = list(messages)
        self.closed = False
        self.drained = threading.Event()

    def receive(self, timeout=None):
        if self._messages:
            return self._messages.pop(0)
        self.drained.set()
        raise TimeoutError

    def close(self):
        self.closed = True


def _run_receive(messages):
    """Run the real receive loop over fake messages and collect what it dispatched."""
    events: list[str] = []
    backend = power._LinuxPowerEvents(events.append)
    conn = _FakeConnection(messages)

    thread = threading.Thread(target=backend._receive, args=(conn,), daemon=True)
    thread.start()
    assert conn.drained.wait(timeout=5), "receive loop never drained the queue"
    backend._stop.set()
    thread.join(timeout=5)
    assert not thread.is_alive()

    return events


pytest.importorskip("jeepney")


@needs_jeepney
def test_linux_receive_loop_dispatches_a_suspend():
    events = _run_receive([
        _FakeMessage(power._LOGIND_IFACE, "PrepareForSleep", (True,)),
    ])
    assert events == [power.SUSPEND]


@needs_jeepney
def test_linux_receive_loop_dispatches_a_full_sleep_cycle():
    events = _run_receive([
        _FakeMessage(power._LOGIND_IFACE, "PrepareForSleep", (True,)),
        _FakeMessage("org.gnome.ScreenSaver", "ActiveChanged", (True,)),
        _FakeMessage(power._LOGIND_IFACE, "PrepareForSleep", (False,)),
        _FakeMessage("org.gnome.ScreenSaver", "ActiveChanged", (False,)),
    ])
    assert events == [power.SUSPEND, power.LOCK, power.RESUME, power.UNLOCK]


@needs_jeepney
def test_linux_receive_loop_skips_signals_it_does_not_own():
    events = _run_receive([
        _FakeMessage("org.freedesktop.DBus", "NameOwnerChanged", ("a", "b", "c")),
        _FakeMessage(power._LOGIND_IFACE, "PrepareForSleep", (True,)),
    ])
    assert events == [power.SUSPEND]


def test_linux_stop_closes_every_connection():
    backend = power._LinuxPowerEvents(lambda e: None)
    conns = [_FakeConnection([]), _FakeConnection([])]
    backend._connections.extend(conns)

    backend.stop()

    assert all(c.closed for c in conns)
    assert backend._connections == []


# ── macOS observer registration ───────────────────────────────────────────────


class _FakeCenter:
    def __init__(self) -> None:
        self.blocks: dict[str, object] = {}
        self.removed: list[object] = []

    def addObserverForName_object_queue_usingBlock_(self, name, obj, queue, block):
        self.blocks[name] = block
        return f"token:{name}"

    def removeObserver_(self, token):
        self.removed.append(token)

    # NSWorkspace.sharedWorkspace().notificationCenter() shape
    def notificationCenter(self):
        return self


def _install_fake_pyobjc(monkeypatch, workspace_center, distributed_center):
    appkit = types.ModuleType("AppKit")
    appkit.NSWorkspace = types.SimpleNamespace(
        sharedWorkspace=lambda: workspace_center
    )
    foundation = types.ModuleType("Foundation")
    foundation.NSDistributedNotificationCenter = types.SimpleNamespace(
        defaultCenter=lambda: distributed_center
    )
    foundation.NSOperationQueue = types.SimpleNamespace(mainQueue=lambda: "main")
    monkeypatch.setitem(sys.modules, "AppKit", appkit)
    monkeypatch.setitem(sys.modules, "Foundation", foundation)


def test_macos_backend_declines_without_pyobjc(monkeypatch):
    monkeypatch.setitem(sys.modules, "AppKit", None)
    backend = power._MacPowerEvents(lambda e: None)
    assert backend.start() is False


def test_macos_registers_every_notification(monkeypatch):
    workspace, distributed = _FakeCenter(), _FakeCenter()
    _install_fake_pyobjc(monkeypatch, workspace, distributed)

    backend = power._MacPowerEvents(lambda e: None)
    assert backend.start() is True

    assert set(workspace.blocks) == set(power._MAC_WORKSPACE_EVENTS)
    assert set(distributed.blocks) == set(power._MAC_DISTRIBUTED_EVENTS)


@pytest.mark.parametrize(
    "notification, expected",
    [
        ("NSWorkspaceWillSleepNotification", power.SUSPEND),
        ("NSWorkspaceDidWakeNotification", power.RESUME),
        ("com.apple.screenIsLocked", power.LOCK),
        ("com.apple.screenIsUnlocked", power.UNLOCK),
    ],
)
def test_macos_block_dispatches_the_right_event(monkeypatch, notification, expected):
    workspace, distributed = _FakeCenter(), _FakeCenter()
    _install_fake_pyobjc(monkeypatch, workspace, distributed)

    events: list[str] = []
    backend = power._MacPowerEvents(events.append)
    backend.start()

    blocks = {**workspace.blocks, **distributed.blocks}
    blocks[notification](None)     # Cocoa passes the NSNotification; we ignore it

    assert events == [expected]


def test_macos_each_block_captures_its_own_event(monkeypatch):
    """A closure over the loop variable would make every block emit the last event."""
    workspace, distributed = _FakeCenter(), _FakeCenter()
    _install_fake_pyobjc(monkeypatch, workspace, distributed)

    events: list[str] = []
    backend = power._MacPowerEvents(events.append)
    backend.start()

    for block in {**workspace.blocks, **distributed.blocks}.values():
        block(None)

    assert sorted(events) == sorted(
        [*power._MAC_WORKSPACE_EVENTS.values(), *power._MAC_DISTRIBUTED_EVENTS.values()]
    )


def test_macos_stop_removes_every_observer(monkeypatch):
    workspace, distributed = _FakeCenter(), _FakeCenter()
    _install_fake_pyobjc(monkeypatch, workspace, distributed)

    backend = power._MacPowerEvents(lambda e: None)
    backend.start()
    backend.stop()

    assert len(workspace.removed) == len(power._MAC_WORKSPACE_EVENTS)
    assert len(distributed.removed) == len(power._MAC_DISTRIBUTED_EVENTS)
    assert backend._observers == []


# ── App wiring ────────────────────────────────────────────────────────────────


def test_app_does_not_start_the_monitor_by_default(monkeypatch):
    from vesper import App

    started = []
    monkeypatch.setattr(power, "start_power_monitor", lambda emit: started.append(emit))
    app = App()
    assert app._power_events is False
    assert started == []


def test_app_starts_and_stops_the_monitor_when_opted_in(monkeypatch):
    """run() must start the monitor and stop it in the finally, like ipc.close()."""
    from unittest.mock import patch

    from vesper import App

    started, stopped = [], []
    monkeypatch.setattr(
        power, "start_power_monitor", lambda emit: (started.append(emit), True)[1]
    )
    monkeypatch.setattr(power, "stop_power_monitor", lambda: stopped.append(True))

    app = App(power_events=True)
    with patch.object(app.window, "create"), patch.object(app.window, "show"):
        app.run()

    assert started == [app.window.emit], "the monitor must emit through the window"
    assert stopped == [True]


def test_app_stops_the_monitor_even_when_show_raises(monkeypatch):
    from unittest.mock import patch

    from vesper import App

    stopped = []
    monkeypatch.setattr(power, "start_power_monitor", lambda emit: True)
    monkeypatch.setattr(power, "stop_power_monitor", lambda: stopped.append(True))

    app = App(power_events=True)
    with patch.object(app.window, "create"), \
         patch.object(app.window, "show", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            app.run()

    assert stopped == [True]


def test_app_survives_an_unavailable_monitor(monkeypatch):
    """A platform with no backend must not stop the app from running."""
    from unittest.mock import patch

    from vesper import App

    monkeypatch.setattr(power, "start_power_monitor", lambda emit: False)

    app = App(power_events=True)
    with patch.object(app.window, "create"), patch.object(app.window, "show"):
        app.run()   # must not raise
