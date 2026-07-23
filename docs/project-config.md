# Project Config — vesper.toml

Every project created with `vesper init` has a `vesper.toml` file at its root. All CLI commands that need project context read this file. It is plain TOML.

---

## Full example

```toml
[project]
name = "my-app"
template = "react"
styles = "tailwind"
bundler = "pyinstaller"
package_manager = "pnpm"

[plugins]
store = "vesper-store"
db    = "vesper-db"

[sign]
# macOS
identity  = "Developer ID Application: DannelCu (TEAMID)"
notarize  = "true"
apple_id  = "you@example.com"
team_id   = "TEAMID"
# Windows
certificate   = "cert.pfx"
timestamp_url = "http://timestamp.digicert.com"
```

---

## [project]

| Key | Values | Default | Description |
|---|---|---|---|
| `name` | string | `my-app` | The application name. Used as the window title and the output binary name. |
| `template` | `vanilla`, `react`, `vue`, `svelte` | `vanilla` | The frontend template chosen at `vesper init`. Used by `vesper dev` and `vesper build`. |
| `styles` | `none`, `bootstrap`, `tailwind` | `none` | CSS framework integrated at init time. |
| `bundler` | `pyinstaller`, `nuitka` | `pyinstaller` | Native binary packager used by `vesper package`. |
| `package_manager` | `npm`, `pnpm`, `yarn` | auto-detected | Package manager for JS operations. If absent, auto-detected from lock files: `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, else npm. |

---

## [plugins]

Maps short alias names to pip package names. Used by `vesper sync-sdk` to discover and copy plugin JS SDK files.

```toml
[plugins]
store = "vesper-store"
db    = "vesper-db"
http  = "vesper-http"
```

The key (left side) is an arbitrary alias shown in logs. The value (right side) must match the installed pip package name exactly.

`vesper sync-sdk` reads this section, imports each package, calls `Plugin.sdk_path()`, and copies the returned JS file to `frontend/` or `public/` (depending on template). If a listed package is not installed, a warning is printed and the command continues.

---

## [sign]

Configuration for `vesper sign`. Only needs to be set up for distribution builds.

**macOS keys**

| Key | Description |
|---|---|
| `identity` | Signing identity — the string from `security find-identity -v -p codesigning`. Format: `"Developer ID Application: Name (TEAMID)"`. |
| `notarize` | `"true"` to enable notarization after signing. Requires `apple_id`, `team_id`, and `VESPER_NOTARIZE_PASSWORD` env var. |
| `apple_id` | Your Apple ID email, used for `xcrun notarytool`. |
| `team_id` | Your 10-character Apple Developer team ID. |
| `entitlements` | Optional path to an `entitlements.plist` file passed to `codesign`. |

**Windows keys**

| Key | Description |
|---|---|
| `certificate` | Path to the `.pfx` / `.p12` certificate file. |
| `timestamp_url` | Timestamp server URL. DigiCert: `http://timestamp.digicert.com`. Sectigo: `http://timestamp.sectigo.com`. |

Environment variables used by `vesper sign`:

| Variable | Used for |
|---|---|
| `VESPER_SIGN_PASSWORD` | PFX certificate password (Windows) |
| `VESPER_NOTARIZE_PASSWORD` | App-specific password for notarization (macOS) |

---

## [installer]

Metadata for `vesper package --installer` (`.dmg` on macOS, `.deb` on Debian/Ubuntu). Every key has a sensible default, so the section is optional.

```toml
[installer]
version     = "1.2.0"
description = "Notes that sync themselves"
maintainer  = "Ann Author <ann@example.com>"
category    = "Utility"          # freedesktop menu category (Linux)
icon        = "assets/icon.png"  # 256x256 PNG, used for the Linux menu entry
```

| Key | Default | Used for |
|---|---|---|
| `version` | `0.1.0` | dmg filename, deb version field |
| `description` | `"<name> (built with Vesper)"` | deb control, .desktop comment |
| `maintainer` | placeholder | deb `Maintainer` field |
| `category` | `Utility` | `.desktop` `Categories` |
| `icon` | none | Linux menu icon (`hicolor/256x256`) |

See [CLI Reference](cli.md#vesper-package) for what `--installer` produces per platform.

---

## Serving the frontend over localhost in production

By default a packaged app loads its frontend via `file://`. That is the simplest and most isolated option, but the `file://` origin breaks three things web tooling assumes:

- **ES modules** — `<script type="module">` imports are blocked by CORS on `file://`.
- **SPA routing** — `history.pushState` paths 404 on reload, since there is no server to fall back to `index.html`.
- **Relative `fetch()`** — requests against relative URLs have no origin to resolve against.

If your app needs any of those, opt in to the localhost server:

```python
app = App(
    frontend="dist/index.html",
    serve_frontend=True,
)
```

The frontend directory is then served from `http://127.0.0.1:<ephemeral-port>/<session-token>/`, with an `index.html` fallback for extensionless paths so SPA routes survive a reload. The server lives and dies with the app process — it starts inside `app.run()` and is shut down when the window closes. Under `vesper dev` the flag is ignored: the dev server already serves over HTTP and takes precedence.

It handles connections concurrently, which matters more than it sounds: a ranged `GET` from a `<video>` element stays open for as long as the video plays, so a one-request-at-a-time server would leave every other request — thumbnails, a second video, the SDK — queued behind whatever is currently playing.

**Why is this an `App` parameter and not a `vesper.toml` key?** The config file is a CLI-side artifact — it is not bundled into the packaged binary, so the runtime could not read it. The `App` constructor is the configuration surface the packaged app actually has.

### Threat model — read before enabling

Stated with the same honesty as the single-instance entry in KNOWN-ISSUES:

- The server binds to `127.0.0.1` only; it is never reachable from the network.
- Loopback is reachable by **any local process**, not just your app. The random per-session token in the URL path is what stops another local process from enumerating your assets by scanning ports: requests without it get an undifferentiated 403. It protects against casual snooping — not against a process that can already read this process's memory or command line.
- What you give up versus `file://` is **origin isolation**: every app serving on loopback shares the browser origin `http://127.0.0.1:<port>`. Anything origin-scoped in the WebView (localStorage, IndexedDB) keys off that origin plus the port, which changes per run — do not use origin-scoped browser storage for durable data with this mode; use [vesper-store](plugins.md#vesper-store) or the filesystem API instead.
- The real fix would be a custom scheme (`app://`) with a per-app origin, which PyWebView does not currently expose — see [KNOWN-ISSUES](../KNOWN-ISSUES.md#ki3) for what would unblock it.

---

## Fallback behavior

If `vesper.toml` is absent, commands fall back to sensible defaults:
- Template: `vanilla`
- Bundler: `pyinstaller`
- Package manager: auto-detected from lock files, defaults to `npm`

Missing sections (`[plugins]`, `[sign]`) are silently ignored.

---

## Reading vesper.toml in Python

The framework provides helpers in `commands/utils.py` for CLI use. You do not normally need these in app code:

```python
from vesper.commands.utils import read_vesper_toml, read_vesper_toml_section

config = read_vesper_toml(".")         # → dict[str, str], all [project] keys
sign   = read_vesper_toml_section(".", "sign")  # → dict[str, str] for [sign]
```
