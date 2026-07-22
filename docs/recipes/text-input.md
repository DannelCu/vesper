# Asking the User for Text

Vesper's dialogs cover files (`open`, `save`, `pickFolder`), a message box, and yes/no
questions. There is no native dialog that asks for a **string** — no "new name for
this file", no "enter the server URL".

This recipe is the way through, and it works identically on Windows, macOS and Linux
because it never leaves the page.

## Why this is not in the core

PyWebView exposes `create_file_dialog` and `create_confirmation_dialog` and nothing
else, so there is no native text dialog for Vesper to wrap — see
[KNOWN-ISSUES KI7](../../KNOWN-ISSUES.md). `window.prompt()` does not exist inside a
WebView either, so the browser fallback is gone too.

Vesper could ship an in-page modal from the SDK, and deliberately does not. A prompt
is markup and styling inside *your* page: it has to match your app's design, your
dark mode, your focus behaviour. Shipping one would push Vesper's look into every
project to save fifteen lines. That is the "would core inclusion be overkill?" test
in [CONTRIBUTING.md](../../CONTRIBUTING.md#where-a-feature-lives), answered yes.

## The pattern

A dialog element, a promise, and one function. The promise resolves with the string
or with `null` when the user cancels, which lets calling code read like a native
dialog would.

```html
<dialog id="prompt">
  <form method="dialog">
    <label for="prompt-input">New name</label>
    <input id="prompt-input" type="text" autocomplete="off" />
    <menu>
      <button value="cancel">Cancel</button>
      <button value="ok" id="prompt-ok">OK</button>
    </menu>
  </form>
</dialog>
```

```js
/**
 * Ask the user for a string. Resolves to the text, or null if cancelled.
 *
 * <dialog> is doing the work here: it traps focus, closes on Escape, and renders
 * on the top layer above everything else — all behaviour a hand-rolled overlay
 * has to reimplement badly.
 */
function promptText(message, initial = "") {
  const dialog = document.getElementById("prompt")
  const input = document.getElementById("prompt-input")

  dialog.querySelector("label").textContent = message
  input.value = initial

  return new Promise((resolve) => {
    dialog.addEventListener("close", () => {
      // returnValue is the value of the button that submitted the form.
      resolve(dialog.returnValue === "ok" ? input.value.trim() : null)
    }, { once: true })

    dialog.showModal()
    input.select()
  })
}
```

Use it where a native dialog would go:

```js
const name = await promptText("New name for this file", item.name)
if (name && name !== item.name) {
  await vesper.invoke("rename", { path: item.path, new_name: name })
}
```

## Getting the details right

**Enter and Escape** come free. A `<form method="dialog">` submits on Enter, and
`<dialog>` closes on Escape with an empty `returnValue` — which the code above reads
as a cancel. Do not add key handlers for them.

**Validate before you resolve** when the answer has rules. Cancel the submit and let
the user fix it rather than round-tripping to Python for a rejection:

```js
document.getElementById("prompt-ok").addEventListener("click", (event) => {
  if (!input.value.trim()) {
    event.preventDefault()
    input.setCustomValidity("A name is required")
    input.reportValidity()
  }
})
```

**Never trust the result on the Python side.** A filename from the page is untrusted
input like any other. Take the basename and re-check it against your scope, or a
value of `../../etc/passwd` walks straight out of your app's directory:

```python
@app.command
def rename(path: str, new_name: str) -> str:
    source = app.fs_scope.check(path)
    # Path(new_name).name discards any directory part the frontend sent.
    target = app.fs_scope.check(str(source.with_name(Path(new_name).name)))
    source.rename(target)
    return str(target)
```

**Style it as a real dialog.** `<dialog>` has no default look worth keeping, and
`::backdrop` is what dims the page behind it:

```css
dialog { border: none; border-radius: 10px; padding: 18px; min-width: 320px; }
dialog::backdrop { background: rgb(0 0 0 / 55%); }
```

## Platform notes

| Platform | Behaviour |
|---|---|
| Windows (WebView2) | Full `<dialog>` support, including `showModal` and `::backdrop`. |
| macOS (WKWebView) | Same. Supported since Safari 15.4, which is well below any macOS that runs Vesper. |
| Linux (WebKitGTK) | Same, on the WebKit2GTK 4.1 builds Vesper requires. |

Nothing here depends on the platform, which is the advantage of solving it in the
page: one implementation, no capability check, no degradation path.

## Working example

[examples/media-vault](../../examples/media-vault/frontend/app.js) uses this for
renaming files in the library. Press **Rename** on any tile.
