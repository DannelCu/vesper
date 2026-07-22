# vesper-watch

File watching for Vesper. Watch a directory (or file) and receive change events in the frontend, backed by [watchdog](https://github.com/gorakhargosh/watchdog) — inotify on Linux, FSEvents on macOS, ReadDirectoryChangesW on Windows.

---

## Install

```bash
pip install vesper-watch
```

---

## Setup

```python
from vesper import App
from vesper_watch import WatchPlugin

app = App(
    frontend="dist/index.html",
    fs_scope=["/home/user/my-app-data"],
    plugins=[WatchPlugin()],
)
```

`WatchPlugin(debounce=0.2)` sets the default debounce window in seconds — repeats of the same `(kind, path)` within it are dropped, which tames editors that fire several modify events per save.

Watched paths are validated against the app's `fs_scope`: a sandboxed frontend cannot observe directories it cannot read. All observers are stopped when the app closes.

---

## JavaScript API

```toml
[plugins]
watch = "vesper-watch"
```

```bash
vesper sync-sdk
```

```html
<script src="vesper.js"></script>
<script src="vesper-watch.js"></script>
```

### Watch a path

```js
const watcher = await vesper.watch.watch("/home/user/my-app-data/projects", {
    recursive: true,          // default
    debounce: 0.5,            // seconds, optional
    onChange: (event) => {
        // { id, kind, path, dest_path?, is_dir }
        // kind: "created" | "modified" | "deleted" | "moved"
        console.log(event.kind, event.path)
    },
})

// Later:
await watcher.unwatch()
```

### Listen across all watches

```js
const unsubscribe = vesper.watch.onChange((event) => refreshTree(event))
```

---

## Python API

```python
plugin = WatchPlugin()
app = App(plugins=[plugin])

watch_id = plugin.watch("/data", recursive=True, debounce=0.2)
plugin.unwatch(watch_id)
plugin.stop_all()
```

---

## Platform notes

### Linux: inotify watch limit

Recursive watching of large trees consumes inotify watches, and the kernel's default limit (`fs.inotify.max_user_watches`, often 65536 — sometimes as low as 8192) can run out, at which point watchdog raises `OSError: inotify watch limit reached`. Raise it:

```bash
# Check the current limit
cat /proc/sys/fs/inotify/max_user_watches

# Raise it persistently
echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

This is an action for *the machine running the app* — if you ship an app that watches big trees, document it for your users too.

### Editors and duplicate events

Saving a file is rarely one event: editors write temp files, rename over the target, and touch metadata. Expect `created`+`moved` or several `modified` in a burst — the debounce window absorbs most of it, but treat events as "something changed here", not as an exact operation log.

### Network filesystems

inotify/FSEvents do not report changes made by *other machines* on NFS/SMB mounts. Only local changes are seen — a polling fallback is out of scope for this plugin.
