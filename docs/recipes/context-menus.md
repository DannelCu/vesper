# Recipe: Context Menus

PyWebView does not expose a native right-click context menu API. This recipe shows how to build a context menu that looks and feels native using HTML, CSS, and a small amount of JavaScript.

---

## Basic context menu

```html
<!-- Add to your index.html or component -->
<div id="context-menu" class="context-menu">
    <div class="context-item" data-action="open">Open</div>
    <div class="context-item" data-action="copy">Copy path</div>
    <div class="context-separator"></div>
    <div class="context-item context-item--danger" data-action="delete">Delete</div>
</div>
```

```css
.context-menu {
    position: fixed;
    display: none;
    background: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
    padding: 4px 0;
    min-width: 160px;
    z-index: 9999;
    font-size: 13px;
    font-family: system-ui, sans-serif;
}

.context-menu.visible {
    display: block;
}

.context-item {
    padding: 6px 16px;
    cursor: pointer;
    color: #1f2937;
}

.context-item:hover {
    background: #f3f4f6;
}

.context-item--danger {
    color: #dc2626;
}

.context-separator {
    height: 1px;
    background: #e5e7eb;
    margin: 4px 0;
}
```

```js
// context-menu.js

const menu = document.getElementById("context-menu")
let currentTarget = null

// Show the menu at the cursor position
function showContextMenu(event, target) {
    event.preventDefault()
    currentTarget = target

    const x = Math.min(event.clientX, window.innerWidth  - menu.offsetWidth  - 8)
    const y = Math.min(event.clientY, window.innerHeight - menu.offsetHeight - 8)

    menu.style.left = x + "px"
    menu.style.top  = y + "px"
    menu.classList.add("visible")
}

// Hide on click elsewhere
document.addEventListener("click", () => menu.classList.remove("visible"))
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") menu.classList.remove("visible")
})

// Handle menu item clicks
menu.addEventListener("click", async (e) => {
    const item = e.target.closest(".context-item")
    if (!item) return
    menu.classList.remove("visible")

    const action = item.dataset.action

    if (action === "open")   await handleOpen(currentTarget)
    if (action === "copy")   await handleCopy(currentTarget)
    if (action === "delete") await handleDelete(currentTarget)
})

// Attach to any element
export function attachContextMenu(element, getTarget) {
    element.addEventListener("contextmenu", (e) => {
        showContextMenu(e, getTarget ? getTarget(e) : e.currentTarget)
    })
}
```

---

## Using it on a file list

```html
<ul id="file-list"></ul>
```

```js
import { attachContextMenu } from "./context-menu.js"

const fileList = document.getElementById("file-list")

async function renderFiles() {
    const entries = await vesper.fs.list("/home/user/documents")
    fileList.innerHTML = ""

    for (const entry of entries) {
        const li = document.createElement("li")
        li.textContent = entry.name
        li.dataset.path = entry.path
        fileList.appendChild(li)

        attachContextMenu(li, () => entry)
    }
}

async function handleOpen(entry) {
    if (entry.is_dir) {
        // navigate into directory
    } else {
        await vesper.shell.open(entry.path)
    }
}

async function handleCopy(entry) {
    await vesper.clipboard.write(entry.path)
}

async function handleDelete(entry) {
    if (!confirm(`Delete ${entry.name}?`)) return
    await vesper.invoke("delete_file", { path: entry.path })
    renderFiles()
}

renderFiles()
```

---

## Dynamic menu items

Build the menu dynamically based on context:

```js
function showContextMenu(event, entry) {
    event.preventDefault()

    // Build menu items dynamically
    const items = [
        { label: "Open", action: "open" },
        { label: "Copy path", action: "copy" },
    ]

    if (!entry.is_dir) {
        items.push({ separator: true })
        items.push({ label: "Delete", action: "delete", danger: true })
    }

    menu.innerHTML = items.map(item =>
        item.separator
            ? `<div class="context-separator"></div>`
            : `<div class="context-item ${item.danger ? "context-item--danger" : ""}"
                    data-action="${item.action}">${item.label}</div>`
    ).join("")

    // ... position and show as before
}
```

---

## Dark mode support

```css
@media (prefers-color-scheme: dark) {
    .context-menu {
        background: #1f2937;
        border-color: #374151;
    }
    .context-item { color: #f9fafb; }
    .context-item:hover { background: #374151; }
    .context-separator { background: #374151; }
}
```

Or use the `vesper-theme` plugin with CSS variables — see [Recipes — Dark/Light Mode Theming](theming.md).
