# Production Lockdown

A WebView is still a browser: F5 reloads, Ctrl+F opens a find bar, right-click shows
a browser menu. `vesper.security.lockdown()` turns those off so your app behaves like
a desktop app.

```js
vesper.security.lockdown()
```

Opt-in, and **skipped in development** — reload is exactly what you want while
building.

## Detecting development vs. production

`vesper init` scaffolds the right call for each template automatically — you rarely
need to think about this — but it is worth understanding what actually decides "dev"
from "production," because getting it wrong means shipping a build that never locks
down, or a dev build that fights you with no reload.

**Framework templates (React/Vue/Svelte, Vite-based).** The scaffolded `main.jsx` /
`main.js` checks `import.meta.env.DEV` — Vite's own build-time flag, `true` under
`vesper dev` and `false` in a production `vite build`, with zero configuration:

```js
if (!import.meta.env.DEV) {
  window.vesper.security.lockdown()
}
```

This is the reliable signal for these templates. It is *not* the same thing as
`lockdown()`'s own built-in runtime heuristic (below) — the scaffolded code decides
whether to call `lockdown()` at all, rather than relying on `lockdown()` to detect dev
mode by itself.

**Vanilla template.** `vesper dev`'s server injects `window.VESPER_DEV_URL` into every
served page, and `lockdown()` checks that global directly — see below. Calling
`lockdown()` unconditionally is safe here; there is no `import.meta.env` without a
bundler.

## `lockdown()`'s own runtime heuristic — and its one sharp edge

Without a `force` option, `lockdown()` skips locking down when it thinks it is running
under `vesper dev`. It checks, in order: `window.VESPER_DEV_URL` (set by the vanilla
dev server), then the page's own origin — `http://` or `https://` on `localhost` or
`127.0.0.1`.

That second check is a heuristic, and it has exactly one failure mode worth knowing:
**`App(serve_frontend=True)`** (used for SPA routing, relative `fetch()`, or ES modules
in production — see [project-config.md](project-config.md)) serves your *production*
build from `http://127.0.0.1:<port>` too — indistinguishable from `vesper dev` by
origin alone. An app using `serve_frontend=True` that relies only on `lockdown()`'s
default heuristic will never actually lock down in production.

The fix is the same `import.meta.env.DEV` check already described above — decide
whether to call `lockdown()` yourself, and pass `force: true` so `lockdown()` doesn't
re-apply its own (in this case wrong) heuristic on top:

```js
if (!import.meta.env.DEV) {
  window.vesper.security.lockdown({ force: true })
}
```

`force: true` on its own, with no surrounding check, would also lock down under
`vesper dev` for a framework template, since `window.VESPER_DEV_URL` is a vanilla-only
signal — always pair it with the `import.meta.env.DEV` check for Vite-based apps.

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
