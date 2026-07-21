"""
Power management: keeping the machine awake, and hearing when it sleeps.

**Keep-awake** — ``prevent_sleep()`` / ``allow_sleep()``:

macOS:   a ``caffeinate`` subprocess, killed to release the assertion
Windows: SetThreadExecutionState via ctypes
Linux:   ``systemd-inhibit`` if present, otherwise ``xdg-screensaver``

**System events** — ``start_power_monitor()`` / ``stop_power_monitor()``, opt-in via
``App(power_events=True)``. Emits ``power:suspend``, ``power:resume``, ``power:lock``
and ``power:unlock`` to the frontend, which listens with
``vesper.on("power:suspend", cb)``.

Every backend is resolved lazily and every failure degrades to a no-op: a missing
helper binary, an absent optional dependency or a locked-down desktop must never take
down ``app.run()``. Callers can check the return value when they care whether the
request took effect.
"""
from __future__ import annotations

import ctypes
import shutil
import subprocess
import sys
import threading

from vesper.core.logging import get_logger

logger = get_logger("power")

# Set once a backend is found to be unavailable, so a machine without the optional
# dependency logs the reason once rather than on every start.
_warned: set[str] = set()


def _warn_once(key: str, message: str) -> None:
    if key not in _warned:
        _warned.add(key)
        logger.debug(message)

# SetThreadExecutionState flags (winbase.h).
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002

_lock = threading.Lock()
_process: subprocess.Popen | None = None
_active = False


def is_preventing_sleep() -> bool:
    """Whether a sleep-prevention request is currently held."""
    return _active


def prevent_sleep(reason: str = "Vesper app is busy") -> bool:
    """
    Ask the system not to sleep or blank the screen.

    Idempotent: calling it while already active keeps the existing request rather
    than stacking a second one, since only allow_sleep() releases it.

    Returns True when the request was registered.
    """
    global _process, _active

    with _lock:
        if _active:
            return True

        try:
            if sys.platform == "darwin":
                ok = _macos_prevent()
            elif sys.platform == "win32":
                ok = _windows_prevent()
            else:
                ok = _linux_prevent(reason)
        except Exception:
            logger.exception("Could not prevent sleep")
            return False

        _active = ok
        if not ok:
            logger.debug("Sleep prevention unavailable on this system")
        return ok


def allow_sleep() -> bool:
    """
    Release a previous prevent_sleep(). Safe to call when nothing is held.

    Returns True when no request remains.
    """
    global _process, _active

    with _lock:
        if not _active:
            return True

        try:
            if sys.platform == "win32":
                _windows_allow()
            elif _process is not None:
                _process.terminate()
                try:
                    _process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    _process.kill()
        except Exception:
            logger.exception("Could not release sleep prevention")
            return False
        finally:
            _process = None
            _active = False

        return True


# ── macOS ────────────────────────────────────────────────────────────────────


def _macos_prevent() -> bool:
    global _process

    if shutil.which("caffeinate") is None:
        return False

    # -d display, -i idle sleep. The assertion lives as long as the process does.
    _process = subprocess.Popen(
        ["caffeinate", "-d", "-i"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


# ── Windows ──────────────────────────────────────────────────────────────────


def _windows_prevent() -> bool:
    # ES_CONTINUOUS makes the request persist until it is cleared, rather than
    # resetting the idle timer once.
    result = ctypes.windll.kernel32.SetThreadExecutionState(
        _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED | _ES_DISPLAY_REQUIRED
    )
    return result != 0


def _windows_allow() -> None:
    ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)


# ── Linux ────────────────────────────────────────────────────────────────────


def _linux_prevent(reason: str) -> bool:
    global _process

    if shutil.which("systemd-inhibit"):
        # The inhibitor is held for as long as the child runs, so it is parked on
        # a sleep rather than given real work to do.
        _process = subprocess.Popen(
            [
                "systemd-inhibit",
                "--what=idle:sleep",
                "--who=Vesper",
                f"--why={reason}",
                "--mode=block",
                "sleep", "infinity",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True

    if shutil.which("xdg-screensaver"):
        result = subprocess.run(
            ["xdg-screensaver", "reset"], capture_output=True, check=False
        )
        # Only suspends the screensaver momentarily, so it is a weaker guarantee
        # than the systemd path — better than nothing, but not a real inhibitor.
        return result.returncode == 0

    return False


# ═════════════════════════════════════════════════════════════════════════════
# System power events
# ═════════════════════════════════════════════════════════════════════════════
#
# Four events, emitted to the frontend without the "vesper:" prefix — Window.emit
# adds it, so the browser sees "vesper:power:suspend".
#
# These are best-effort by design. Every backend depends on something the platform
# may not provide (an optional Python package, a D-Bus service, a desktop that
# implements the interface), and none of them is worth failing app startup over.

SUSPEND = "power:suspend"
RESUME = "power:resume"
LOCK = "power:lock"
UNLOCK = "power:unlock"

# How long stop() waits for a backend thread to notice and unwind. The threads are
# daemons, so exceeding this delays nothing — it only means the thread is still
# blocked in a platform call when the process exits.
_STOP_TIMEOUT = 2.0

# Poll interval for backends that block on a socket or a queue. Short enough that
# stop() returns promptly, long enough not to spin.
_POLL_SECONDS = 0.5


class PowerMonitor:
    """
    Translates platform power/session signals into Vesper events.

    ``emit`` is called as ``emit(event_name, payload)`` — in practice
    ``app.window.emit``. It is invoked from a backend thread, not the main thread.
    """

    def __init__(self, emit) -> None:
        self._emit = emit
        self._backend = None

    def start(self) -> bool:
        """
        Begin listening. Returns True when a backend was available.

        Never raises: an unsupported platform, a missing optional dependency or a
        refused connection all return False.
        """
        if self._backend is not None:
            return True

        try:
            backend = _make_backend(self._dispatch)
        except Exception:
            logger.exception("Could not create a power event backend")
            return False

        if backend is None:
            return False

        try:
            if not backend.start():
                return False
        except Exception:
            logger.exception("Could not start the power event backend")
            return False

        self._backend = backend
        return True

    def stop(self) -> None:
        """Stop listening. Safe to call when never started."""
        backend, self._backend = self._backend, None
        if backend is None:
            return
        try:
            backend.stop()
        except Exception:
            logger.exception("Could not stop the power event backend")

    def _dispatch(self, event: str) -> None:
        """
        Hand one event to the emit callback.

        Wrapped because this runs on a backend thread: an exception raised here
        would be swallowed by the platform's callback machinery or kill the
        listening thread, and either way the next event would be lost silently.
        """
        try:
            self._emit(event, None)
        except Exception:
            logger.exception("Power event listener raised for %s", event)


_monitor: PowerMonitor | None = None


def start_power_monitor(emit) -> bool:
    """
    Start the process-wide power monitor. Returns True when it is listening.

    Calling it while one is already running is a no-op that returns True.
    """
    global _monitor

    if _monitor is not None:
        return True

    monitor = PowerMonitor(emit)
    if not monitor.start():
        return False

    _monitor = monitor
    return True


def stop_power_monitor() -> None:
    """Stop the process-wide power monitor. Safe when none is running."""
    global _monitor

    monitor, _monitor = _monitor, None
    if monitor is not None:
        monitor.stop()


def _make_backend(dispatch):
    """Pick the backend for this platform, or None where there is nothing to use."""
    if sys.platform == "darwin":
        return _MacPowerEvents(dispatch)
    if sys.platform == "win32":
        return _WindowsPowerEvents(dispatch)
    return _LinuxPowerEvents(dispatch)


# ── macOS ────────────────────────────────────────────────────────────────────
#
# Sleep/wake come from NSWorkspace's own notification center. Lock/unlock are not
# published there at all — they go to the *distributed* notification center under
# names Apple has never documented, which is the only way to observe them.

_MAC_WORKSPACE_EVENTS = {
    "NSWorkspaceWillSleepNotification": SUSPEND,
    "NSWorkspaceDidWakeNotification": RESUME,
}

_MAC_DISTRIBUTED_EVENTS = {
    "com.apple.screenIsLocked": LOCK,
    "com.apple.screenIsUnlocked": UNLOCK,
}


class _MacPowerEvents:
    def __init__(self, dispatch) -> None:
        self._dispatch = dispatch
        self._observers: list = []

    def start(self) -> bool:
        try:
            from AppKit import NSWorkspace
            from Foundation import NSDistributedNotificationCenter, NSOperationQueue
        except ImportError:
            _warn_once(
                "mac-power-events",
                "Power events need pyobjc (AppKit/Foundation); not listening",
            )
            return False

        queue = NSOperationQueue.mainQueue()
        centers = (
            (NSWorkspace.sharedWorkspace().notificationCenter(), _MAC_WORKSPACE_EVENTS),
            (NSDistributedNotificationCenter.defaultCenter(), _MAC_DISTRIBUTED_EVENTS),
        )

        for center, mapping in centers:
            for name, event in mapping.items():
                token = center.addObserverForName_object_queue_usingBlock_(
                    name, None, queue, self._make_block(event)
                )
                self._observers.append((center, token))

        # No thread: Cocoa delivers these on the main run loop, which pywebview is
        # already running. Without that run loop nothing arrives, which is exactly
        # the best-effort contract.
        return bool(self._observers)

    def _make_block(self, event: str):
        # Bound outside the loop so each block captures its own event name rather
        # than the last one the loop variable held.
        return lambda _note: self._dispatch(event)

    def stop(self) -> None:
        for center, token in self._observers:
            try:
                center.removeObserver_(token)
            except Exception:
                logger.debug("Could not remove a power notification observer")
        self._observers.clear()


# ── Windows ──────────────────────────────────────────────────────────────────
#
# Both signals arrive as window messages, so this needs a window — a message-only
# one (HWND_MESSAGE), which is never displayed and exists solely to receive them.
# Session lock/unlock additionally has to be subscribed to explicitly.

_WM_POWERBROADCAST = 0x0218
_WM_WTSSESSION_CHANGE = 0x02B1
_WM_DESTROY = 0x0002
_WM_CLOSE = 0x0010

_PBT_APMSUSPEND = 0x0004
_PBT_APMRESUMESUSPEND = 0x0007
_PBT_APMRESUMEAUTOMATIC = 0x0012

_WTS_SESSION_LOCK = 0x7
_WTS_SESSION_UNLOCK = 0x8

_NOTIFY_FOR_THIS_SESSION = 0
_HWND_MESSAGE = -3


def _windows_event_for(msg: int, wparam: int) -> str | None:
    """
    Map a window message to a Vesper event, or None when it is not one of ours.

    Split out from the message loop so the mapping can be tested without creating
    a window: this is the part with the logic, the loop around it is plumbing.
    """
    if msg == _WM_POWERBROADCAST:
        if wparam == _PBT_APMSUSPEND:
            return SUSPEND
        # Windows sends RESUMEAUTOMATIC when the machine woke on a timer and
        # RESUMESUSPEND when the user did it. Both mean "we are back"; a machine
        # woken by the user sends both, hence the de-duplication in the loop.
        if wparam in (_PBT_APMRESUMESUSPEND, _PBT_APMRESUMEAUTOMATIC):
            return RESUME
    elif msg == _WM_WTSSESSION_CHANGE:
        if wparam == _WTS_SESSION_LOCK:
            return LOCK
        if wparam == _WTS_SESSION_UNLOCK:
            return UNLOCK
    return None


class _WindowsPowerEvents:
    def __init__(self, dispatch) -> None:
        self._dispatch = dispatch
        self._thread: threading.Thread | None = None
        self._hwnd = None
        self._ready = threading.Event()
        self._started = False
        self._last_resume = 0.0
        self._wndproc = None  # kept alive: Windows holds a raw pointer to it

    def start(self) -> bool:
        self._thread = threading.Thread(
            target=self._run, name="vesper-power-events", daemon=True
        )
        self._thread.start()
        # The window has to exist before stop() can post to it, so wait for the
        # loop to say it is up rather than racing it.
        self._ready.wait(timeout=_STOP_TIMEOUT)
        return self._started

    def _run(self) -> None:
        try:
            self._pump()
        except Exception:
            logger.exception("Power event loop stopped")
        finally:
            self._ready.set()

    def _pump(self) -> None:
        import ctypes.wintypes as wintypes

        user32 = ctypes.windll.user32
        wtsapi32 = ctypes.windll.wtsapi32

        proc_type = ctypes.WINFUNCTYPE(
            ctypes.c_longlong, wintypes.HWND, ctypes.c_uint,
            ctypes.c_ulonglong, ctypes.c_longlong,
        )

        def wndproc(hwnd, msg, wparam, lparam):
            event = _windows_event_for(msg, wparam)
            if event is not None and not self._is_duplicate_resume(event):
                self._dispatch(event)
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc = proc_type(wndproc)

        wndclass = _WNDCLASS()
        wndclass.lpfnWndProc = self._wndproc
        wndclass.lpszClassName = "VesperPowerEvents"
        wndclass.hInstance = ctypes.windll.kernel32.GetModuleHandleW(None)

        atom = user32.RegisterClassW(ctypes.byref(wndclass))
        if not atom:
            _warn_once("win-power-class", "Could not register power event window class")
            return

        hwnd = user32.CreateWindowExW(
            0, atom, "VesperPowerEvents", 0, 0, 0, 0, 0,
            _HWND_MESSAGE, None, wndclass.hInstance, None,
        )
        if not hwnd:
            _warn_once("win-power-window", "Could not create power event window")
            return

        self._hwnd = hwnd
        # Power broadcasts reach every window for free; session change does not.
        if not wtsapi32.WTSRegisterSessionNotification(hwnd, _NOTIFY_FOR_THIS_SESSION):
            _warn_once(
                "win-session-notify",
                "Session lock/unlock unavailable; suspend/resume still active",
            )

        self._started = True
        self._ready.set()

        msg = _MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        try:
            wtsapi32.WTSUnRegisterSessionNotification(hwnd)
        except Exception:
            logger.debug("Could not unregister session notification")

    def _is_duplicate_resume(self, event: str) -> bool:
        """Collapse the RESUMEAUTOMATIC/RESUMESUSPEND pair into one resume."""
        if event != RESUME:
            return False
        import time

        now = time.monotonic()
        duplicate = (now - self._last_resume) < 1.0
        self._last_resume = now
        return duplicate

    def stop(self) -> None:
        if self._hwnd:
            try:
                ctypes.windll.user32.PostMessageW(self._hwnd, _WM_CLOSE, 0, 0)
            except Exception:
                logger.debug("Could not post close to the power event window")
        if self._thread is not None:
            self._thread.join(timeout=_STOP_TIMEOUT)
        self._hwnd = None
        self._started = False


if sys.platform == "win32":  # pragma: no cover - structures only valid on Windows
    import ctypes.wintypes as _wintypes

    class _WNDCLASS(ctypes.Structure):
        _fields_ = [
            ("style", ctypes.c_uint),
            ("lpfnWndProc", ctypes.WINFUNCTYPE(
                ctypes.c_longlong, _wintypes.HWND, ctypes.c_uint,
                ctypes.c_ulonglong, ctypes.c_longlong,
            )),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", _wintypes.HINSTANCE),
            ("hIcon", _wintypes.HICON),
            ("hCursor", ctypes.c_void_p),
            ("hbrBackground", ctypes.c_void_p),
            ("lpszMenuName", _wintypes.LPCWSTR),
            ("lpszClassName", _wintypes.LPCWSTR),
        ]

    class _MSG(ctypes.Structure):
        _fields_ = [
            ("hWnd", _wintypes.HWND),
            ("message", ctypes.c_uint),
            ("wParam", ctypes.c_ulonglong),
            ("lParam", ctypes.c_longlong),
            ("time", ctypes.c_ulong),
            ("pt_x", ctypes.c_long),
            ("pt_y", ctypes.c_long),
        ]
else:
    # Defined so the module imports everywhere; the Windows backend is the only
    # thing that touches them and it never runs off Windows.
    _WNDCLASS = None
    _MSG = None


# ── Linux ────────────────────────────────────────────────────────────────────
#
# systemd-logind publishes PrepareForSleep on the system bus, and screen lock is
# whatever the desktop's screensaver publishes on the session bus. Both are D-Bus,
# reached through jeepney — pure Python, no compiled bindings, and optional: no
# jeepney means no events, not a broken app.

_LOGIND_PATH = "/org/freedesktop/login1"
_LOGIND_IFACE = "org.freedesktop.login1.Manager"

# Every desktop names its screensaver interface after itself, and there is no
# cross-desktop standard, so all the common ones are matched at once. Only the one
# the running desktop actually publishes will ever fire.
_SCREENSAVER_IFACES = (
    "org.freedesktop.ScreenSaver",
    "org.gnome.ScreenSaver",
    "org.cinnamon.ScreenSaver",
)


def _linux_event_for(interface: str, member: str, body) -> str | None:
    """
    Map a D-Bus signal to a Vesper event, or None when it is not one of ours.

    Kept separate from the receive loop so the mapping is testable without a bus.
    """
    if interface == _LOGIND_IFACE and member == "PrepareForSleep":
        # The signal fires twice per sleep cycle: True just before suspending,
        # False once resumed.
        if not body:
            return None
        return SUSPEND if body[0] else RESUME

    if interface in _SCREENSAVER_IFACES and member == "ActiveChanged":
        if not body:
            return None
        return LOCK if body[0] else UNLOCK

    if interface == "org.freedesktop.login1.Session":
        if member == "Lock":
            return LOCK
        if member == "Unlock":
            return UNLOCK

    return None


class _LinuxPowerEvents:
    def __init__(self, dispatch) -> None:
        self._dispatch = dispatch
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._connections: list = []

    def start(self) -> bool:
        try:
            import jeepney  # noqa: F401
        except ImportError:
            _warn_once(
                "linux-power-events",
                "Power events need jeepney (pip install jeepney); not listening",
            )
            return False

        rules = (
            ("SYSTEM", [(_LOGIND_IFACE, "PrepareForSleep", _LOGIND_PATH)]),
            ("SESSION", [(iface, "ActiveChanged", None) for iface in _SCREENSAVER_IFACES]),
        )

        for bus, matches in rules:
            if not self._listen(bus, matches):
                # One bus being unreachable does not invalidate the other: a system
                # without logind can still report screen locks and vice versa.
                logger.debug("Power events: %s bus unavailable", bus)

        return bool(self._threads)

    def _listen(self, bus: str, matches) -> bool:
        from jeepney import MatchRule, message_bus
        from jeepney.io.blocking import open_dbus_connection

        try:
            conn = open_dbus_connection(bus=bus)
        except Exception:
            return False

        try:
            for interface, member, path in matches:
                rule = MatchRule(type="signal", interface=interface, member=member,
                                 path=path)
                conn.send_and_get_reply(message_bus.AddMatch(rule))
        except Exception:
            logger.debug("Could not add a %s bus match rule", bus)
            conn.close()
            return False

        self._connections.append(conn)
        thread = threading.Thread(
            target=self._receive, args=(conn,),
            name=f"vesper-power-{bus.lower()}", daemon=True,
        )
        thread.start()
        self._threads.append(thread)
        return True

    def _receive(self, conn) -> None:
        while not self._stop.is_set():
            try:
                # A timeout rather than a blocking wait, so stop() is noticed
                # without needing the bus to send anything first.
                msg = conn.receive(timeout=_POLL_SECONDS)
            except TimeoutError:
                continue
            except Exception:
                # The connection is gone — on shutdown that is expected.
                if not self._stop.is_set():
                    logger.debug("Power event connection closed")
                return

            fields = msg.header.fields
            try:
                from jeepney import HeaderFields

                interface = fields.get(HeaderFields.interface)
                member = fields.get(HeaderFields.member)
            except Exception:
                continue

            event = _linux_event_for(interface, member, msg.body)
            if event is not None:
                self._dispatch(event)

    def stop(self) -> None:
        self._stop.set()
        for conn in self._connections:
            try:
                conn.close()
            except Exception:
                logger.debug("Could not close a power event connection")
        for thread in self._threads:
            thread.join(timeout=_STOP_TIMEOUT)
        self._connections.clear()
        self._threads.clear()
