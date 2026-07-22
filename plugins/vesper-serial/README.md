# vesper-serial

Serial port access for Vesper via [pyserial](https://github.com/pyserial/pyserial): list devices, open several ports at once, stream incoming data to the frontend, write back, close. Built for apps that talk to Arduinos, sensors, printers, and anything else on a UART.

---

## Install

```bash
pip install vesper-serial
```

---

## Setup

```python
from vesper import App
from vesper_serial import SerialPlugin

app = App(
    frontend="dist/index.html",
    plugins=[SerialPlugin()],
)
```

All open ports and reader threads are closed when the app closes.

---

## JavaScript API

```toml
[plugins]
serial = "vesper-serial"
```

```bash
vesper sync-sdk
```

```html
<script src="vesper.js"></script>
<script src="vesper-serial.js"></script>
```

```js
// Discover devices
const ports = await vesper.serial.listPorts()
// [{ device: "/dev/ttyUSB0", description: "USB Serial", hwid: "..." }]

// Open, stream, write, close
const arduino = await vesper.serial.open("/dev/ttyUSB0", {
    baudrate: 115200,
    onData: (text) => terminal.append(text),
    onClose: () => showDisconnected(),     // also fires if the device is unplugged
})

await arduino.write("LED ON\n")
await arduino.close()
```

Several ports can be open at once; each carries its own id, and the `onData`/`onClose` handlers are filtered per port. Raw events are `vesper:serial:data` (`{id, data}`) and `vesper:serial:closed` (`{id}`).

Incoming bytes are delivered as UTF-8 text with undecodable bytes replaced — for binary protocols, frame and hex/base64-encode on the device side or handle the port in a Python command instead.

---

## Python API

```python
plugin = SerialPlugin()
app = App(plugins=[plugin])

conn_id = plugin.open("/dev/ttyUSB0", baudrate=115200)
plugin.write(conn_id, "PING\n")
plugin.close(conn_id)
plugin.close_all()
```

Ports open through `serial.serial_for_url`, so pyserial URL handlers work too — `loop://` (loopback, used by the test suite), `socket://host:port`, `rfc2217://...`.

---

## Platform notes

### Linux: the `dialout` group (manual, per user)

Serial devices belong to group `dialout` (Debian/Ubuntu/Arch) or `uucp`/`dialout` (Fedora). A user outside that group gets `Permission denied` opening the port. The fix is a manual action on each machine that runs the app:

```bash
# Debian / Ubuntu / Arch
sudo usermod -aG dialout $USER

# Fedora
sudo usermod -aG dialout $USER    # some setups: uucp

# Then log out and back in — group membership is read at login.
```

Ship this instruction with your app; there is no way to do it programmatically.

### Windows: drivers

Most boards need a USB-UART driver before a COM port appears: CH340/CH341 (common on Arduino clones), CP210x (Silicon Labs), FTDI. Windows Update usually installs them automatically; when a board shows up in Device Manager with a warning triangle, install the vendor driver. Genuine Arduinos and anything using USB CDC work driver-free on Windows 10+.

### macOS

USB-UART bridges appear as `/dev/cu.usbserial-*` / `/dev/cu.usbmodem-*`. Prefer the `cu.` device over `tty.`. CH340 needs a vendor driver on older macOS versions; CDC devices work out of the box.

---

## Verification note

CI exercises the full write → reader thread → event path against pyserial's `loop://` handler. Real hardware (an actual board echoing over USB) is a documented manual test — the loopback proves the plugin's plumbing, not your wiring.
