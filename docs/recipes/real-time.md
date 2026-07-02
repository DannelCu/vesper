# Recipe: Real-Time Data Push

This recipe shows how to stream live data from Python to the frontend — sensor readings, log tails, download progress, stock prices, or any data that updates continuously.

---

## Pattern 1: Polling timer in a background thread

The simplest pattern: a Python thread collects data and emits events.

```python
import threading, time, random
from vesper import App

app = App(title="Live Data", frontend="frontend/index.html")

_streaming = False

@app.command
def start_stream():
    global _streaming
    if _streaming:
        return
    _streaming = True
    threading.Thread(target=_stream_loop, daemon=True).start()

@app.command
def stop_stream():
    global _streaming
    _streaming = False

def _stream_loop():
    while _streaming:
        value = read_sensor()   # your data source
        app.emit("data-point", {"value": value, "ts": time.time()})
        time.sleep(0.1)         # 10 Hz

def read_sensor() -> float:
    # Replace with real sensor, database query, file tail, etc.
    return random.gauss(50, 5)

if __name__ == "__main__":
    app.run()
```

```js
// frontend/index.html
const points = []
const MAX_POINTS = 100

vesper.on("data-point", ({ value, ts }) => {
    points.push({ value, ts })
    if (points.length > MAX_POINTS) points.shift()
    updateChart(points)
})

document.getElementById("start").onclick = () => vesper.invoke("start_stream")
document.getElementById("stop").onclick  = () => vesper.invoke("stop_stream")
```

---

## Pattern 2: File tail (log viewer)

Stream lines from a growing log file:

```python
import threading, time
from pathlib import Path

LOG_FILE = Path("/var/log/my-app.log")

@app.command
def start_log_tail():
    threading.Thread(target=_tail, daemon=True).start()
    return True

def _tail():
    with LOG_FILE.open() as f:
        f.seek(0, 2)   # seek to end
        while True:
            line = f.readline()
            if line:
                app.emit("log-line", {"text": line.rstrip()})
            else:
                time.sleep(0.1)
```

```js
const logEl = document.getElementById("log")

vesper.on("log-line", ({ text }) => {
    const line = document.createElement("div")
    line.className = "log-line"
    line.textContent = text
    logEl.appendChild(line)
    logEl.scrollTop = logEl.scrollHeight   // auto-scroll to bottom
})

await vesper.invoke("start_log_tail")
```

---

## Pattern 3: Async generator (asyncio)

For async data sources (WebSocket, async database cursors, etc.):

```python
import asyncio

async def _feed():
    async for event in my_async_source():
        app.emit("update", event)

@app.command
async def start_feed():
    asyncio.ensure_future(_feed())
    return True
```

`asyncio.ensure_future` schedules the coroutine on Vesper's IPC event loop. The command returns immediately while the feed runs in the background.

---

## Pattern 4: Progress events

For one-shot operations with progress (uploads, builds, exports):

```python
import time

@app.command
def process_files(paths: list) -> dict:
    total = len(paths)
    for i, path in enumerate(paths):
        do_work(path)   # your processing logic
        app.emit("progress", {
            "current": i + 1,
            "total": total,
            "percent": round((i + 1) / total * 100),
            "file": path,
        })
    return {"ok": True, "processed": total}
```

```js
const progressBar = document.getElementById("progress")
const statusText  = document.getElementById("status")

vesper.on("progress", ({ current, total, percent, file }) => {
    progressBar.style.width = percent + "%"
    progressBar.setAttribute("aria-valuenow", percent)
    statusText.textContent = `Processing ${current}/${total}: ${file}`
})

const result = await vesper.invoke("process_files", { paths: selectedPaths })
statusText.textContent = `Done! Processed ${result.processed} files.`
```

---

## Stopping streams on window close

Register a teardown command or lifecycle hook to stop background threads when the app exits:

```python
import threading

_stop_event = threading.Event()

def _stream_loop():
    while not _stop_event.is_set():
        app.emit("data-point", {"value": read_sensor()})
        time.sleep(0.1)

@app.on("closed")
def on_closed():
    _stop_event.set()   # signal the thread to exit
```

---

## Rate limiting high-frequency data

If your data source produces thousands of events per second, throttle the emit rate to avoid flooding the WebView:

```python
import time

class ThrottledEmitter:
    def __init__(self, min_interval: float = 0.016):  # ~60 Hz max
        self._last = 0.0
        self._interval = min_interval
        self._pending = None

    def emit(self, event: str, payload: dict):
        now = time.monotonic()
        self._pending = (event, payload)
        if now - self._last >= self._interval:
            app.emit(*self._pending)
            self._last = now
            self._pending = None

emitter = ThrottledEmitter(min_interval=0.05)   # 20 Hz max

def _stream_loop():
    while _streaming:
        value = read_high_freq_sensor()
        emitter.emit("data-point", {"value": value})
        time.sleep(0.001)
```
