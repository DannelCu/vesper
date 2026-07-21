# Production Lockdown

A WebView is still a browser: F5 reloads, Ctrl+F opens a find bar, right-click shows
a browser menu. `vesper.security.lockdown()` turns those off so your app behaves like
a desktop app.

```js
vesper.security.lockdown()
```

Opt-in, and **skipped in development** — reload is exactly what you want while
building. Detection is via the dev server URL, so `vesper dev` never locks down and a
production build always does.

## What each flag disables

| Flag | Default | Disables |
|---|---|---|
| `reload` | `true` | F5, Ctrl/Cmd+R, Ctrl/Cmd+Shift+R |
| `find` | `true` | Ctrl/Cmd+F, Ctrl/Cmd+G |
| `print` | `true` | Ctrl/Cmd+P |
| `zoom` | `true` | Ctrl+scroll, Ctrl/Cmd +/-/0 |
| `contextMenu` | `true` | The default right-click menu |
| `selection` | `false` | Text selection outside inputs |
| `allowContextMenuInInputs` | `true` | Keeps the menu in inputs and textareas |
| `force` | `false` | Lock down even in dev |

Two defaults are deliberately permissive:

- **`selection` is off** — users legitimately copy text out of a UI, and disabling it
  is more often an annoyance than a feature.
- **`allowContextMenuInInputs` is on** — losing cut/copy/paste inside a text field is
  a real regression, so the menu survives there even when disabled everywhere else.

## Overriding

```js
vesper.security.lockdown({
  contextMenu: false,   // keep the browser menu
  selection: true,      // also block text selection
})
```

## Undoing it

`lockdown()` returns a function that removes every listener it added:

```js
const undo = vesper.security.lockdown()
// later, e.g. entering a debug mode
undo()
```

## What it does not do

This is a usability measure, not a security boundary. It removes keyboard and mouse
affordances from the WebView; it does not restrict what your frontend code can do.
Use [Guards](guards.md) and `fs_scope` for actual access control.
