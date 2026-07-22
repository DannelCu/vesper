# Filesystem API

Vesper provides built-in filesystem commands accessible from JavaScript. They let the frontend read, write, and browse files without registering custom commands for common operations.

---

## Read a file

```js
const content = await vesper.fs.read("/path/to/file.txt")
// content is a string
```

```js
// With explicit encoding (default: utf-8)
const content = await vesper.fs.read("/path/to/file.txt", "utf-8")
```

---

## Write a file

```js
await vesper.fs.write("/path/to/output.txt", "Hello, world!")
```

Parent directories are created automatically if they do not exist. Content is a string — for binary data, see [File Transfers](file-transfers.md).

---

## Check if a path exists

```js
const exists = await vesper.fs.exists("/path/to/file.txt")
// true or false
```

---

## List a directory

```js
const entries = await vesper.fs.list("/path/to/dir")
// [{ name: "file.txt", path: "/path/to/dir/file.txt", is_dir: false }, ...]
```

Entries are sorted directories-first. Each entry has:
- `name` — filename or directory name
- `path` — absolute path
- `is_dir` — `true` for directories, `false` for files

---

## Create a directory

```js
await vesper.fs.mkdir("/path/to/newdir")
await vesper.fs.mkdir("/path/to/a/b/c", true)   // create missing ancestors too
```

Fails if the directory already exists. Note the difference with `fs.write`, which creates parent directories implicitly — `mkdir` is for when the directory itself is the point.

---

## Copy and move

```js
await vesper.fs.copy("/data/report.pdf", "/backup/report.pdf")
await vesper.fs.copy("/data/project", "/backup/project")      // whole tree

await vesper.fs.move("/data/draft.txt", "/data/final.txt")    // also a rename
```

`copy` copies files with metadata and directories recursively (the destination directory must not already exist). `move` moves or renames either. With a configured scope, **both ends** are validated — a copy is a read of the source and a write of the destination, so neither may fall outside the sandbox.

---

## Delete permanently

```js
await vesper.fs.remove("/path/to/file.txt")
await vesper.fs.remove("/path/to/dir", true)    // directories require the flag
```

`remove` is permanent. Deleting a directory without passing `recursive: true` fails explicitly rather than silently taking the whole tree. For anything the user might want back, prefer [`fs.trash`](#moving-files-to-the-trash).

---

## File metadata

```js
const info = await vesper.fs.stat("/path/to/file.txt")
// { size: 1024, mtime: 1712345678.9, is_dir: false, type: "file" }
```

`mtime` is seconds since the epoch. `type` is `"file"` or `"dir"`, mirroring `is_dir`.

---

## Binary files

```js
// Read raw bytes as base64
const b64 = await vesper.fs.readBytes("/path/to/image.png")
const img = document.createElement("img")
img.src = "data:image/png;base64," + b64

// Write base64 back to disk as raw bytes
await vesper.fs.writeBytes("/path/to/copy.png", b64)
```

The IPC bridge is JSON, which cannot carry raw bytes — base64 is the canonical encoding for binary data crossing it. `writeBytes` creates parent directories like `write`, and rejects invalid base64 instead of writing a corrupted file. For the full upload/download patterns (blobs, `FileReader`, size limits), see [File Transfers](file-transfers.md).

---

## Using from Python directly

The same functions are available as a Python module:

```python
from vesper.core import fs

content = fs.read("data.txt")
fs.write("out.txt", "hello")
exists = fs.exists("data.txt")   # → True or False
entries = fs.list_dir(".")       # → [{"name": ..., "path": ..., "is_dir": ...}]

fs.mkdir("newdir", parents=True)
fs.copy("a.txt", "b.txt")
fs.move("b.txt", "c.txt")
fs.remove("c.txt")               # remove("dir", recursive=True) for directories
info = fs.stat("data.txt")       # → {"size": ..., "mtime": ..., "is_dir": ..., "type": ...}
b64 = fs.read_bytes("logo.png")  # → base64 string
fs.write_bytes("copy.png", b64)
```

---

## IPC command names

These built-ins are filtered from `vesper sync-types` output and accessed via `vesper.fs.*` in JavaScript:
- `vesper:fs:read`
- `vesper:fs:write`
- `vesper:fs:exists`
- `vesper:fs:list`
- `vesper:fs:mkdir`
- `vesper:fs:copy`
- `vesper:fs:move`
- `vesper:fs:remove`
- `vesper:fs:stat`
- `vesper:fs:read_bytes`
- `vesper:fs:write_bytes`

---

## Path handling

Paths follow the OS convention. On Windows, use forward slashes or escaped backslashes:

```js
await vesper.fs.read("C:/Users/user/Documents/file.txt")
await vesper.fs.read("C:\\Users\\user\\Documents\\file.txt")
```

For paths relative to the user's home directory, construct the full path in a Python command using `pathlib.Path.home()`:

```python
from pathlib import Path

@app.command
def get_config_path() -> str:
    return str(Path.home() / ".config" / "my-app" / "settings.json")
```

```js
const configPath = await vesper.invoke("get_config_path")
const config = await vesper.fs.read(configPath)
```

---

## Large files

The filesystem API reads entire files into memory as strings. For files larger than a few megabytes, prefer a streaming approach: read the file in a Python command and return only the portion the frontend needs, or use `vesper.fs.read` only for configuration files and small text assets.

For binary files (images, PDFs), use `readBytes` / `writeBytes` above; [File Transfers](file-transfers.md) covers the browser-side patterns built on them.

---

## Security — path scope

By default the filesystem built-ins have **no access restrictions**: the frontend can read or write any path on the machine that the OS user has permission to access. This is intentional for development convenience, but you should restrict it in production.

### Configuring a scope

Pass `fs_scope` to `App` to limit filesystem access to a list of allowed root directories:

```python
import os
from pathlib import Path

app = App(
    frontend="dist/index.html",
    fs_scope=[
        str(Path.home() / "Documents" / "my-app"),   # user data folder
        os.environ.get("APPDATA", "") + "/my-app",   # Windows app data
    ],
)
```

Any path that resolves (after symlink resolution) outside every listed root raises `FsScopeError`, which the IPC layer returns as `{ok: false, error: {type: "FsScopeError"}}`.

To allow unrestricted access explicitly (not recommended):

```python
app = App(fs_scope="*")
```

### Recommended practice

Restrict `fs_scope` to the application's own data directory:

```python
from pathlib import Path
import os

if os.name == "nt":
    data_dir = Path(os.environ["APPDATA"]) / "my-app"
else:
    data_dir = Path.home() / ".local" / "share" / "my-app"

data_dir.mkdir(parents=True, exist_ok=True)

app = App(
    frontend="dist/index.html",
    fs_scope=[str(data_dir)],
)
```

Without a scope, a malicious or compromised frontend could exfiltrate `/etc/passwd`, private keys, or overwrite system files.

---

## Moving files to the trash

`trash()` sends a file or directory to the system trash, where the user can restore
it — unlike a delete.

```js
await vesper.fs.trash("/path/to/file.txt")
```

```python
from vesper.core import fs

fs.trash("/path/to/file.txt", scope=my_scope)
```

It honours `fs_scope` exactly like the rest of the filesystem API, so a scoped app
cannot trash files outside its allowed roots.

**It never falls back to deleting.** When no trash backend is available it raises
`RuntimeError` rather than removing the file permanently — silently turning a
recoverable operation into an irreversible one would be a far worse failure than
reporting that trash is unavailable.

For the best behaviour install the optional dependency, which implements the
platform trash specifications properly, including the metadata that makes "restore"
work on Linux:

```bash
pip install "vesper[trash]"
```

Without it, Vesper falls back to `gio trash`, the Finder, or the Windows Recycle Bin
API.
