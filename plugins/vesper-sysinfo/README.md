# vesper-sysinfo

System information for Vesper via [psutil](https://github.com/giampaolo/psutil): CPU usage and core count, memory, per-partition disk usage, network counters, battery (when the machine has one), and uptime. On-demand snapshots or a subscription stream for dashboards.

---

## Install

```bash
pip install vesper-sysinfo
```

---

## Setup

```python
from vesper import App
from vesper_sysinfo import SysinfoPlugin

app = App(
    frontend="dist/index.html",
    plugins=[SysinfoPlugin()],
)
```

---

## JavaScript API

```toml
[plugins]
sysinfo = "vesper-sysinfo"
```

```bash
vesper sync-sdk
```

```html
<script src="vesper.js"></script>
<script src="vesper-sysinfo.js"></script>
```

### Snapshot

```js
const info = await vesper.sysinfo.snapshot()
// {
//   cpu:     { percent: 12.5, count: 8 },
//   memory:  { total, available, percent },
//   disks:   [{ device, mountpoint, total, used, percent }, ...],
//   net:     { bytes_sent, bytes_recv },
//   battery: { percent: 87, plugged: true } | null,
//   uptime:  123456.7   // seconds
// }
```

### Live stream

```js
const stream = await vesper.sysinfo.subscribe({
    interval: 1,                       // seconds
    onTick: (info) => updateGauges(info),
})

// Later:
await stream.unsubscribe()
```

One stream per app — subscribing again retunes the interval instead of stacking tickers. The stream stops cleanly when the app closes: no orphan threads.

---

## Python API

```python
plugin = SysinfoPlugin()
app = App(plugins=[plugin])

info = plugin.snapshot()
plugin.subscribe(interval=1.0)      # emits "sysinfo:tick" events
plugin.unsubscribe()
```

---

## Notes

- **CPU percent** is measured since the previous reading (non-blocking). The very first value after startup can read `0.0` — expected psutil behaviour.
- **Network counters** are totals since boot; compute rates by diffing consecutive ticks.
- **Disks** silently skip unreadable mounts (restricted FUSE, empty optical drives) rather than failing the whole snapshot.
- **Battery** is `null` on desktops. On some Linux systems without upower the reading may also be unavailable.
- Everything here is a pure userspace read — no permissions or elevation needed on any platform.
