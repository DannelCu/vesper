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
identity  = "Developer ID Application: Dannel LLC (TEAMID)"
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
