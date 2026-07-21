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

## Using from Python directly

The same functions are available as a Python module:

```python
from vesper.core import fs

content = fs.read("data.txt")
fs.write("out.txt", "hello")
exists = fs.exists("data.txt")   # → True or False
entries = fs.list_dir(".")       # → [{"name": ..., "path": ..., "is_dir": ...}]
```

---

## IPC command names

These built-ins are filtered from `vesper sync-types` output and accessed via `vesper.fs.*` in JavaScript:
- `vesper:fs:read`
- `vesper:fs:write`
- `vesper:fs:exists`
- `vesper:fs:list`

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

For binary files (images, PDFs), use [File Transfers](file-transfers.md) with Base64 encoding.

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
