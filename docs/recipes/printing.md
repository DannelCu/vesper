# Recipe: Printing

Printing from a Vesper app, on all three platforms. This is a recipe because the native options — `printToPDF`, silent printing — exist in the WebView engines but are not exposed through PyWebView; see [KNOWN-ISSUES KI4](../../KNOWN-ISSUES.md#ki4). What *is* reliably available is the system print dialog, and it covers most real needs.

---

## The main pattern: `window.print()`

```js
document.getElementById("print-button").onclick = () => window.print()
```

Opens the OS print dialog on all three platforms. The engines differ slightly:

| Platform | Engine | Behaviour |
|---|---|---|
| Windows | WebView2 (Chromium) | Full Chromium print dialog: preview, margins, scale, background graphics toggle. |
| macOS | WKWebKit | Native macOS print panel, including "Save as PDF" in the PDF dropdown. |
| Linux | WebKitGTK | GTK print dialog. No preview on some distro builds; page-size handling is the most spartan of the three. |

**Heads-up:** if you use `vesper.security.lockdown()`, the default blocks Ctrl/Cmd+P (`print: true`). Calling `window.print()` from your own button still works — the lockdown only intercepts the keyboard shortcut.

---

## Print stylesheets

The dialog prints the page as CSS sees it under `@media print`. Ship one — the difference between "prints nicely" and "prints the sidebar over the data" is a few rules:

```css
@media print {
    nav, .toolbar, .no-print { display: none !important; }

    body {
        background: #fff;
        color: #000;
        font-size: 11pt;
    }

    main { margin: 0; padding: 0; }

    table { break-inside: auto; }
    tr    { break-inside: avoid; }

    @page { margin: 18mm; }
}
```

To print a specific fragment (a report, an invoice) rather than the whole UI, the portable pattern is a print-only container:

```css
.print-only { display: none; }

@media print {
    body > *:not(.print-only) { display: none !important; }
    .print-only { display: block; }
}
```

```js
function printReport(html) {
    const container = document.querySelector(".print-only")
    container.innerHTML = html
    window.print()
}
```

---

## Printing to PDF — via the dialog

Every platform can produce a PDF from the same dialog, as a manual user action:

- **Windows** — choose the built-in **Microsoft Print to PDF** printer (present since Windows 10).
- **macOS** — the print panel's **PDF ▾ → Save as PDF** button, built into every print dialog.
- **Linux** — the GTK dialog offers **Print to File** (PDF) out of the box. For a persistent virtual PDF printer, install cups-pdf:

  ```bash
  # Debian / Ubuntu
  sudo apt install printer-driver-cups-pdf

  # Fedora
  sudo dnf install cups-pdf

  # Arch
  sudo pacman -S cups-pdf
  ```

---

## Programmatic PDFs — a Python decision, not a Vesper feature

When you need a PDF *file* without a dialog — invoices to disk, batch reports — generate it in Python, in your own command, with a library your app chooses and ships:

```python
# pip install reportlab   (drawing-oriented)
from reportlab.pdfgen import canvas

@app.command
def export_invoice(dest: str, invoice_id: int) -> str:
    c = canvas.Canvas(dest)
    c.drawString(72, 800, f"Invoice #{invoice_id}")
    c.save()
    return dest
```

```python
# pip install weasyprint  (HTML/CSS-oriented — closest to "print this page")
# NOTE: weasyprint needs system libraries (pango, cairo); check its install docs.
from weasyprint import HTML

@app.command
def export_report(dest: str, html: str) -> str:
    HTML(string=html).write_pdf(dest)
    return dest
```

This is your app's dependency and your app's decision — it does not go through the WebView at all, which is exactly why it works.

---

## What is impossible today

**Silent printing** (no dialog) and **`printToPDF` of the actual rendered page** exist in WebView2 and WKWebView, but PyWebView does not expose them, so Vesper cannot offer them on any platform. That is a known issue with a clear unblocker, not a backlog item — see [KI4](../../KNOWN-ISSUES.md#ki4).
