from __future__ import annotations

import itertools
import threading
from pathlib import Path

from vesper.core.plugin import VesperPlugin


class SerialPlugin(VesperPlugin):
    """
    Serial port access for Vesper via pyserial.

    Multiple ports can be open at once, each with an id; incoming bytes stream
    to the frontend as ``vesper:serial:data`` events (``{id, data}``, text with
    undecodable bytes replaced). A ``vesper:serial:closed`` event (``{id}``)
    fires when a port closes — including a device unplugged mid-session.

    Ports are opened through ``serial.serial_for_url``, so both real devices
    ("COM3", "/dev/ttyUSB0") and pyserial URL handlers ("loop://",
    "socket://...") work — the loopback handler is what the test suite uses in
    place of hardware.

    Usage::

        from vesper_serial import SerialPlugin

        app = App(plugins=[SerialPlugin()])
    """

    def __init__(self) -> None:
        self._app = None
        self._ports: dict[int, dict] = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def register(self, app) -> None:
        self._app = app

        def _list_ports() -> list:
            return self.list_ports()

        def _open(port: str, baudrate: int = 9600, timeout: float = 0.2) -> int:
            return self.open(port, baudrate=baudrate, timeout=timeout)

        def _write(id: int, data: str) -> int:
            return self.write(id, data)

        def _close(id: int) -> bool:
            return self.close(id)

        app.registry.register(_list_ports, name="vesper:serial:list_ports")
        app.registry.register(_open, name="vesper:serial:open")
        app.registry.register(_write, name="vesper:serial:write")
        app.registry.register(_close, name="vesper:serial:close")

        # Reader threads and open handles must not outlive the window.
        app.on("close")(self.close_all)

    def list_ports(self) -> list[dict]:
        """Connected serial devices: ``{device, description, hwid}`` each."""
        from serial.tools import list_ports

        return [
            {"device": p.device, "description": p.description, "hwid": p.hwid}
            for p in list_ports.comports()
        ]

    def open(self, port: str, *, baudrate: int = 9600, timeout: float = 0.2) -> int:
        """
        Open a port and start streaming its data. Returns the connection id.

        *timeout* is the read poll interval, not a failure timeout — it bounds
        how quickly the reader notices a close request.
        """
        import serial

        connection = serial.serial_for_url(port, baudrate=baudrate, timeout=timeout)

        conn_id = next(self._ids)
        stop = threading.Event()
        emit = self._app.emit

        def _reader() -> None:
            try:
                while not stop.is_set() and connection.is_open:
                    waiting = getattr(connection, "in_waiting", 0)
                    data = connection.read(waiting or 1)
                    if data:
                        try:
                            emit("serial:data", {
                                "id": conn_id,
                                "data": data.decode("utf-8", errors="replace"),
                            })
                        except Exception:
                            pass
            except Exception:
                # Device unplugged or read failed — fall through to the
                # closed event so the frontend learns the port is gone.
                pass
            finally:
                with self._lock:
                    self._ports.pop(conn_id, None)
                try:
                    if connection.is_open:
                        connection.close()
                except Exception:
                    pass
                try:
                    emit("serial:closed", {"id": conn_id})
                except Exception:
                    pass

        thread = threading.Thread(target=_reader, daemon=True, name=f"vesper-serial-{conn_id}")
        with self._lock:
            self._ports[conn_id] = {"connection": connection, "stop": stop, "thread": thread}
        thread.start()
        return conn_id

    def write(self, conn_id: int, data: str) -> int:
        """Write text to an open port. Returns the number of bytes written."""
        with self._lock:
            entry = self._ports.get(conn_id)
        if entry is None:
            raise ValueError(f"No open serial connection with id {conn_id}.")
        return entry["connection"].write(data.encode("utf-8"))

    def close(self, conn_id: int) -> bool:
        """Close a connection and stop its reader. False for an unknown id."""
        with self._lock:
            entry = self._ports.get(conn_id)
        if entry is None:
            return False

        entry["stop"].set()
        entry["thread"].join(timeout=2)
        return True

    def close_all(self) -> None:
        with self._lock:
            ids = list(self._ports)
        for conn_id in ids:
            self.close(conn_id)

    @classmethod
    def sdk_path(cls) -> Path | None:
        from importlib.resources import files
        return Path(str(files("vesper_serial").joinpath("sdk/vesper-serial.js")))
