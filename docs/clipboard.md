# Clipboard

Vesper provides built-in commands to read from and write to the system clipboard.

---

## Read from the clipboard

**From JavaScript:**

```js
const text = await vesper.clipboard.read()
console.log(text)   // current clipboard content as a string
```

**From Python:**

```python
from vesper.core import clipboard
text = clipboard.read()
```

---

## Write to the clipboard

**From JavaScript:**

```js
await vesper.clipboard.write("Hello, clipboard!")
```

**From Python:**

```python
from vesper.core import clipboard
clipboard.write("Hello, clipboard!")
```

---

## Platform implementation

| Platform | Read | Write |
|---|---|---|
| Windows | `PowerShell Get-Clipboard` | `PowerShell Set-Clipboard` |
| macOS | `pbpaste` | `pbcopy` |
| Linux | `xclip -selection clipboard -o` | `xclip -selection clipboard` |

**Linux note:** Requires `xclip` to be installed (`apt install xclip` / `pacman -S xclip`). If `xclip` is not available, the commands return an empty string or silently fail.

**Windows note:** A trailing `\r\n` is stripped from `Get-Clipboard` output automatically — the returned string never ends with a newline.

---

## IPC command names

- `vesper:clipboard:read` — called by `vesper.clipboard.read()`
- `vesper:clipboard:write` — called by `vesper.clipboard.write()`

Both are filtered from `vesper sync-types` output.

---

## Security note

Reading the clipboard gives your app access to whatever the user has copied — including passwords from password managers. Only read the clipboard in response to an explicit user action (a button click, a keyboard shortcut). Do not read it automatically on app start or on a timer.
