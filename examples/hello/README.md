# Vesper Hello

A complete Vesper app in two files: `app.py` (Python backend) and
`frontend/index.html` (UI). It demonstrates IPC calls, the scoped filesystem API,
native dialogs, and notifications.

## Run it

```bash
pip install -e ../..      # or: pip install vesper
vesper dev
```

`vesper dev` restarts Python on backend changes and reloads the window on frontend
changes. Use `vesper run` for a single run without watching.

No Node.js required — this is the vanilla template.

## What to look at

- `app.py` — `@app.command` turns a Python function into something JS can call.
  `fs_scope` confines the filesystem API to this directory.
- `frontend/index.html` — `vesper.invoke()`, `vesper.dialog.*`, `vesper.fs.*`,
  `vesper.notify()`. `vesper.js` is the generated bridge; regenerate it with
  `vesper sync-sdk`.
