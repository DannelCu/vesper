# File Transfers

IPC payloads are JSON-serialized. Binary data must be Base64-encoded before crossing the IPC boundary.

---

## Python → Frontend (sending a file to the browser)

Use this when Python generates or reads a binary file and needs to send it to the frontend — for example, a generated PDF, a resized image, or a fetched binary.

**Python:**

```python
import base64
from pathlib import Path

@app.command
def get_image(path: str) -> dict:
    data = Path(path).read_bytes()
    return {
        "name": Path(path).name,
        "mime": "image/png",
        "data": base64.b64encode(data).decode(),
    }
```

**JavaScript:**

```js
const { name, mime, data } = await vesper.invoke("get_image", {
    path: "/path/to/image.png"
})

const bytes = Uint8Array.from(atob(data), c => c.charCodeAt(0))
const blob = new Blob([bytes], { type: mime })
const url = URL.createObjectURL(blob)

const img = document.createElement("img")
img.src = url
document.body.appendChild(img)
```

---

## Frontend → Python (uploading a file from the browser)

Use this when the user picks a file in the UI and it needs to be processed or saved by Python.

**HTML:**

```html
<input type="file" id="picker" />
<button onclick="upload()">Upload</button>
```

**JavaScript:**

```js
async function upload() {
    const file = document.getElementById("picker").files[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = async (e) => {
        // Strip the "data:<mime>;base64," prefix
        const b64 = e.target.result.split(",")[1]
        const result = await vesper.invoke("save_file", {
            name: file.name,
            data: b64,
        })
        console.log("Saved to:", result)
    }
    reader.readAsDataURL(file)
}
```

**Python:**

```python
import base64
from pathlib import Path

@app.command
def save_file(name: str, data: str) -> str:
    dest = Path.home() / "Downloads" / name
    dest.write_bytes(base64.b64decode(data))
    return str(dest)
```

---

## Generating and downloading a PDF

```python
import base64

@app.command
def generate_report(title: str) -> dict:
    pdf_bytes = render_pdf(title)   # your PDF generation logic
    return {
        "filename": f"{title}.pdf",
        "data": base64.b64encode(pdf_bytes).decode(),
    }
```

```js
const { filename, data } = await vesper.invoke("generate_report", {
    title: "Q4 Report"
})

const bytes = Uint8Array.from(atob(data), c => c.charCodeAt(0))
const blob = new Blob([bytes], { type: "application/pdf" })
const a = document.createElement("a")
a.href = URL.createObjectURL(blob)
a.download = filename
a.click()
```

---

## Large files

Base64 adds ~33% size overhead. Files over ~10 MB may cause noticeable lag in the WebView due to JSON serialization.

For large files, the recommended approach is to have Python write the file to disk and return the path:

```python
@app.command
def export_large_file() -> str:
    dest = Path.home() / "Downloads" / "export.csv"
    write_large_csv(dest)   # writes directly to disk
    return str(dest)
```

Then optionally reveal it in the file manager:

```js
const path = await vesper.invoke("export_large_file")
await vesper.shell.reveal(path)
```

---

## Reading files from the filesystem

For reading files from known paths, the built-in [Filesystem API](filesystem.md) (`vesper.fs.read`) is simpler than the Base64 approach. Use Base64 transfers only when the file content needs to be displayed or downloaded as a blob in the browser.
