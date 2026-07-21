# Native File Dialogs

Vesper provides built-in commands for native OS file dialogs — open, save, and folder picker. No extra dependencies required.

---

## Open file dialog

```js
const paths = await vesper.dialog.open({
    multiple: false,           // allow multiple selection (default: false)
    filters: [
        { name: "PDF files", extensions: ["pdf"] },
        { name: "Images",    extensions: ["png", "jpg", "jpeg"] },
    ],
    directory: "/home/user/documents",   // initial directory (optional)
})

// paths is a string (single) or array of strings (multiple: true)
// null if the user cancelled
if (paths) {
    console.log(paths)
}
```

---

## Save file dialog

```js
const dest = await vesper.dialog.save({
    filename: "report.pdf",     // default filename (optional)
    filters: [
        { name: "PDF", extensions: ["pdf"] },
    ],
    directory: "/home/user",    // initial directory (optional)
})

// dest is a string path, or null if cancelled
if (dest) {
    await vesper.invoke("export_pdf", { path: dest })
}
```

---

## Folder picker

```js
const dirs = await vesper.dialog.pickFolder({
    directory: "/home/user",    // initial directory (optional)
    multiple: false,            // allow multiple (optional)
})

// dirs is a string or array of strings (multiple: true), null if cancelled
```

---

## File type filters

Filters use the format `{ name: string, extensions: string[] }`. Each extension is without a dot.

```js
filters: [
    { name: "Text files",  extensions: ["txt", "md"] },
    { name: "Spreadsheets", extensions: ["xlsx", "csv"] },
    { name: "All files",   extensions: ["*"] },
]
```

Vesper converts this to PyWebView's tuple format internally: `("Text files (*.txt;*.md)", "Spreadsheets (*.xlsx;*.csv)")`.

---

## Calling from Python

The dialogs are registered as built-in IPC commands (`vesper:dialog:open`, `vesper:dialog:save`, `vesper:dialog:folder`). You can call them from Python via the IPC layer, or use the underlying `Window` methods directly:

```python
# From a command — blocks until user picks a file
@app.command
def import_csv() -> str | None:
    paths = app.window.open_dialog(
        file_types=["CSV files (*.csv)"],
        allow_multiple=False,
    )
    return paths[0] if paths else None
```

---

## Cancelled dialogs

When the user clicks Cancel, all three dialogs return `null` (JS) / `None` (Python). Always check for null before using the result.

```js
const path = await vesper.dialog.open()
if (!path) return   // user cancelled
```

---

## Filtering from TypeScript definitions

`vesper:dialog:*` built-ins are filtered from the generated `vesper.d.ts` — they are accessed via `vesper.dialog.*` methods, not via `vesper.invoke()`.

---

## Message, confirm and ask

Beyond file pickers, Vesper exposes native message dialogs.

```js
await vesper.dialog.message("Export finished.", "Done")

if (await vesper.dialog.confirm("Delete this project?", "Confirm")) {
    await vesper.invoke("delete_project")
}

const wants = await vesper.dialog.ask("Save changes before closing?")
```

| Method | Returns | Use for |
|---|---|---|
| `message(text, title)` | nothing | Telling the user something |
| `confirm(text, title)` | `boolean` | Confirming a pending action |
| `ask(text, title)` | `boolean` | A yes/no question |

`confirm()` and `ask()` show the same dialog — PyWebView provides one primitive — but
read differently at the call site. Pick whichever matches the sentence you are asking.

From Python, the same dialogs are on the window:

```python
if app.window.confirm_dialog("Confirm", "Delete this project?"):
    delete_project()
```

Dialogs need a created window; calling them before `app.run()` raises.
