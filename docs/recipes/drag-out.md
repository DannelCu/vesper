# Recipe: Saving Files (Drag-Out Alternative)

PyWebView does not support dragging files from the WebView to the desktop. This is a recipe because the native thing is impossible today — PyWebView does not expose the engines' drag cycle — not because it was skipped; see [KNOWN-ISSUES KI1](../../KNOWN-ISSUES.md#ki1) for what would unblock it. Until then, these are three practical patterns for letting users export files from a Vesper app. (For Copy in the app → Paste in the file manager, see also [`vesper.clipboard.writeFiles`](../clipboard.md#files).)

---

## Pattern 1: Save dialog

The cleanest pattern — show a native save dialog and write directly to the chosen path.

```python
@app.command
def export_csv(data: list) -> str | None:
    import csv, io
    from pathlib import Path

    # Generate CSV in memory
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(data)

    # Show save dialog — returns None if cancelled
    dest = app.window.save_dialog(
        file_types=["CSV files (*.csv)"],
        save_filename="export.csv",
    )
    if not dest:
        return None

    Path(dest).write_text(buf.getvalue(), encoding="utf-8")
    return dest
```

```js
async function exportData() {
    const data = [["Name", "Score"], ["Alice", 95], ["Bob", 87]]
    const path = await vesper.invoke("export_csv", { data })

    if (path) {
        const reveal = confirm(`Saved to ${path}\n\nReveal in file manager?`)
        if (reveal) await vesper.shell.reveal(path)
    }
}
```

Or using the built-in JS dialog API:

```js
async function exportData() {
    const dest = await vesper.dialog.save({
        filename: "export.csv",
        filters: [{ name: "CSV", extensions: ["csv"] }],
    })
    if (!dest) return   // cancelled

    const csv = generateCSV()
    await vesper.fs.write(dest, csv)
    await vesper.shell.reveal(dest)
}
```

---

## Pattern 2: Browser download

For small to medium files, generate the content and trigger a browser download in the WebView.

```python
@app.command
def generate_report() -> dict:
    import base64
    pdf_bytes = render_pdf()   # your generation logic
    return {
        "filename": "report.pdf",
        "data": base64.b64encode(pdf_bytes).decode(),
        "mime": "application/pdf",
    }
```

```js
async function downloadReport() {
    const { filename, data, mime } = await vesper.invoke("generate_report")

    const bytes = Uint8Array.from(atob(data), c => c.charCodeAt(0))
    const blob = new Blob([bytes], { type: mime })
    const url = URL.createObjectURL(blob)

    const a = document.createElement("a")
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
}
```

This triggers the WebView's built-in download behavior. On Windows it usually saves to `Downloads/`; on macOS/Linux the location depends on browser settings (PyWebView uses the system WebView).

---

## Pattern 3: Write to Downloads folder automatically

For a fire-and-forget experience without a dialog:

```python
from pathlib import Path

@app.command
def quick_export(filename: str, content: str) -> str:
    dest = Path.home() / "Downloads" / filename
    # Avoid overwriting — add a counter suffix if file exists
    counter = 1
    while dest.exists():
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        dest = Path.home() / "Downloads" / f"{stem} ({counter}){suffix}"
        counter += 1

    dest.write_text(content, encoding="utf-8")
    return str(dest)
```

```js
async function quickExport() {
    const content = editor.getValue()   // e.g. CodeMirror
    const path = await vesper.invoke("quick_export", {
        filename: "notes.txt",
        content,
    })
    await vesper.shell.reveal(path)   // open in Finder/Explorer, file selected
}
```

---

## Large files

For files that are too large to Base64-encode (> 10 MB), always use Pattern 1 or 3 — write directly to disk in Python. Never try to pass large binary data through IPC.

```python
@app.command
def export_large_dataset() -> str:
    dest = Path.home() / "Downloads" / "dataset.parquet"
    df.to_parquet(dest)   # pandas / polars, writes to disk
    return str(dest)
```
