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

---

## Images

```js
const dataUrl = await vesper.clipboard.readImage()
if (dataUrl) {
    document.querySelector("img").src = dataUrl   // usable directly
}

await vesper.clipboard.writeImage(dataUrl)
```

```python
from vesper.core import clipboard

data_url = clipboard.read_image()      # None when the clipboard holds no image
clipboard.write_image(data_url)        # True when the platform accepted it
```

Images cross the bridge as base64 PNG data URLs — the IPC channel is JSON and cannot
carry raw bytes, and a data URL drops straight into an `<img src>`.
`writeImage()` accepts either a full `data:image/png;base64,...` URL or bare base64.

`readImage()` returns `None` both when the clipboard holds no image and when the
platform tool is missing. The caller cannot act on the difference, and an app polling
the clipboard should not have to catch an exception for the ordinary empty case.

Backends: `xclip` on Linux, `osascript` on macOS, PowerShell (`-STA`, which the
Windows clipboard API requires) on Windows.
