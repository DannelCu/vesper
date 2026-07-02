# Shell Integration

Vesper provides two shell integration commands: opening a URL in the default browser and revealing a file in the native file manager.

---

## Open a URL

**From JavaScript:**

```js
await vesper.shell.open("https://example.com")
```

**From Python:**

```python
from vesper.core import shell
shell.open_url("https://example.com")
```

Opens the URL in the default browser using Python's `webbrowser.open()`. Works on all platforms.

Use this to open external links from within your app. If you render `<a href="...">` tags, they open in the WebView by default — calling `vesper.shell.open()` on click is the correct way to open external URLs:

```html
<a href="#" onclick="vesper.shell.open('https://example.com'); return false">
    Visit example.com
</a>
```

---

## Reveal a file in the file manager

**From JavaScript:**

```js
await vesper.shell.reveal("/path/to/file.pdf")
```

**From Python:**

```python
from vesper.core import shell
shell.reveal("/path/to/file.pdf")
```

Opens the native file manager with the file selected:

| Platform | Implementation |
|---|---|
| Windows | `explorer /select,"<path>"` |
| macOS | `open -R "<path>"` |
| Linux | `xdg-open "<parent_dir>"` (reveals the containing folder) |

This is useful after generating or downloading a file — the user can immediately see where it landed.

---

## IPC command names

These are registered as built-in commands:
- `vesper:shell:open_url` — called by `vesper.shell.open()`
- `vesper:shell:reveal` — called by `vesper.shell.reveal()`

They are filtered from `vesper sync-types` output.
