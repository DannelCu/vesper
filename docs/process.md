# Process Execution

Run external binaries from the frontend — behind a declarative allowlist, the same way filesystem access sits behind `fs_scope`.

```python
from vesper import App

app = App(
    shell_scope=["ffmpeg", "git"],
)
```

```js
const { code, stdout } = await vesper.process.run(["git", "log", "--oneline", "-5"])
```

---

## Secure by default

Without a `shell_scope`, **every invocation is rejected** before a process is created. There is no "allow everything" convenience value: an app that runs binaries must say which ones.

Commands are argv lists end to end — there is no shell involved (`shell=True` does not exist in this API), so quoting bugs and shell injection are structurally impossible rather than carefully avoided.

## Declaring the scope

Two forms:

```python
# List: these executables, any arguments.
app = App(shell_scope=["ffmpeg", "/usr/local/bin/exiftool"])

# Dict: per-executable fnmatch argument patterns.
# Every argument must match at least one pattern; None allows any arguments.
app = App(shell_scope={
    "ffmpeg": ["-i", "*.mp4", "*.webm", "-vcodec", "libvpx"],
    "git": None,
})
```

Rules worth knowing:

- A **bare name** (`"ffmpeg"`) allows invocation by that name, resolved through `PATH` when the process starts.
- A **path** (`"/usr/local/bin/exiftool"`) allows invocation by that exact resolved path only.
- The two do not cross-match: allowing `"git"` does **not** allow running `/tmp/evil/git` by path, and vice versa.
- You can also build the scope yourself and pass it in: `App(shell_scope=ShellScope({...}))` (`from vesper import ShellScope`).

Argument patterns are a coarse gate, not a full grammar — they stop the frontend from smuggling `--exec`-style flags into a permissive binary, but reviewing what the allowed binary itself can do (does it have a `--upload` flag?) is still your job.

---

## `run` — blocking, captured

```js
const result = await vesper.process.run(["ffmpeg", "-i", "in.mp4", "out.webm"], {
    cwd: "/tmp/render",     // optional
    timeout: 120,           // optional, seconds; the process is killed on expiry
})
// result = { code: 0, stdout: "...", stderr: "..." }
```

A nonzero exit code **resolves normally** — inspect `code`. The promise only rejects for scope violations, a timeout, or a binary that cannot be started.

---

## `spawn` — streaming

For long-running work, `spawn` streams output line by line and reports the exit:

```js
const proc = await vesper.process.spawn(
    ["ffmpeg", "-i", "input.mp4", "-progress", "pipe:1", "output.webm"],
    {
        onStdout: (line) => updateProgressFrom(line),
        onStderr: (line) => console.warn("[ffmpeg]", line),
        onExit:   (code) => showDone(code === 0),
    }
)

// Later, if the user cancels:
await proc.kill()
```

`onExit` fires exactly once, after the final output line, and cleans up the event subscriptions. `kill()` terminates politely and escalates to a hard kill if the process ignores it; it resolves `false` for a process that already finished.

Under the hood these are the events `vesper:process:stdout`, `vesper:process:stderr` (`{id, line}`) and `vesper:process:exit` (`{id, code}`) — subscribe with `vesper.on(...)` directly if you need raw access across components.

**Lifecycle:** every process spawned through this API is terminated when the app closes. A closed window never leaves orphan children running.

---

## Worked example: wrapping ffmpeg

Python side — declare the tightest scope the feature needs:

```python
from vesper import App

app = App(
    shell_scope={
        # Convert only: -i plus mp4/webm paths and a fixed codec choice.
        "ffmpeg": ["-i", "*.mp4", "*.webm", "-vcodec", "libvpx", "-y"],
    },
)
```

Frontend:

```js
async function convert(input, output) {
    const proc = await vesper.process.spawn(
        ["ffmpeg", "-y", "-i", input, "-vcodec", "libvpx", output],
        {
            onStderr: (line) => {
                // ffmpeg reports progress on stderr
                const m = line.match(/time=(\d+):(\d+):(\d+)/)
                if (m) updateBar(m)
            },
            onExit: (code) => code === 0 ? done(output) : fail(),
        }
    )
    cancelButton.onclick = () => proc.kill()
}
```

Whether `ffmpeg` is installed at all is a fact about the user's machine — check `(await vesper.process.run(["ffmpeg", "-version"])).code === 0` at startup and degrade the UI honestly if it fails, in the same spirit as `vesper.capabilities()`.

---

## Python API

```python
from vesper import ShellScope
from vesper.core import process

scope = ShellScope(["ffmpeg"])

result = process.run(["ffmpeg", "-version"], scope=scope)          # {"code", "stdout", "stderr"}

manager = process.ProcessManager(emit=app.emit)
proc_id = manager.spawn(["ffmpeg", ...], scope=scope)
manager.kill(proc_id)
```

`ShellScopeError` crosses the IPC bridge as `{ok: false, error: {type: "ShellScopeError"}}`, the same shape as `FsScopeError` from the filesystem API.
