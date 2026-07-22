# Code Signing

Code signing proves your app came from you and has not been tampered with. On macOS and Windows, unsigned apps trigger security warnings or are blocked by the OS.

Run `vesper sign` after `vesper package`.

---

## Configuration

Add a `[sign]` section to `vesper.toml`:

```toml
[sign]
# macOS fields
identity  = "Developer ID Application: Your Name (TEAMID)"
notarize  = "true"
apple_id  = "you@example.com"
team_id   = "TEAMID"

# Windows fields
certificate   = "cert.pfx"
timestamp_url = "http://timestamp.digicert.com"
```

---

## macOS

### Requirements

- An Apple Developer account ($99/year)
- A "Developer ID Application" certificate installed in your keychain
- Xcode Command Line Tools

### Sign only

```bash
vesper sign
```

This runs:

```bash
codesign --sign "<identity>" --deep --force --options runtime package/my-app
```

`--deep` signs all embedded frameworks. `--options runtime` is required for notarization.

### Sign and notarize

Set `notarize = "true"` in `[sign]` and set the `VESPER_NOTARIZE_PASSWORD` environment variable to an [app-specific password](https://support.apple.com/en-us/102654):

```bash
export VESPER_NOTARIZE_PASSWORD="xxxx-xxxx-xxxx-xxxx"
vesper sign
```

The sign step runs, then notarizes via `xcrun notarytool submit` and staples with `xcrun stapler staple`.

### Optional: entitlements

For capabilities like network access, camera, or hardened runtime:

```toml
[sign]
identity     = "Developer ID Application: ..."
entitlements = "entitlements.plist"
```

Example `entitlements.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.network.client</key>
    <true/>
</dict>
</plist>
```

See [Apple's entitlements documentation](https://developer.apple.com/documentation/bundleresources/entitlements) for the full list.

---

## Windows

### Requirements

- A code signing certificate (`.pfx` / `.p12`)
  - From a Certificate Authority (DigiCert, Sectigo, etc.) for distribution
  - Self-signed for internal/testing use only
- Either `signtool.exe` (included with the Windows SDK) or `osslsigncode` (for non-Windows build machines)

### Sign

```bash
set VESPER_SIGN_PASSWORD=your-pfx-password
vesper sign
```

This runs:

```
signtool.exe sign /f cert.pfx /p <password> /fd sha256 /tr <timestamp_url> /td sha256 package\my-app.exe
```

If `signtool.exe` is not found, Vesper falls back to `osslsigncode`:

```
osslsigncode sign -pkcs12 cert.pfx -pass <password> -t <timestamp_url> -in package/my-app.exe -out package/my-app.exe
```

### Finding signtool.exe

Vesper auto-discovers `signtool.exe` from common Windows SDK locations:

```
C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe
C:\Program Files\Windows Kits\10\bin\*\x64\signtool.exe
```

If neither path exists, install the [Windows SDK](https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/) or install `osslsigncode` via `winget install osslsigncode`.

### Timestamp servers

A timestamp server embeds a trusted timestamp in the signature so the app remains valid after the certificate expires:

| CA | URL |
|---|---|
| DigiCert | `http://timestamp.digicert.com` |
| Sectigo | `http://timestamp.sectigo.com` |
| GlobalSign | `http://timestamp.globalsign.com/scripts/timstamp.dll` |

---

## Sign an arbitrary binary

```bash
vesper sign --path /path/to/binary
```

Signs the specified path instead of `package/<app-name>[.exe]`.

---

## Signing and installers

`vesper package --installer` integrates with signing on macOS: when `[sign]` has an `identity`, the `.app` bundle is signed (and notarized, if enabled) **before** the `.dmg` is built — a dmg of an unsigned app just postpones the quarantine dialog to the user's machine.

On Windows, sign both binaries when building an installer via the [NSIS recipe](recipes/windows-installer.md): the app exe before wrapping, and the produced setup exe (`vesper sign --path package/MyApp-setup.exe`) — SmartScreen judges the installer itself.

---

## CI / CD

For automated builds, set credentials as environment variables in your CI system (GitHub Actions secrets, etc.):

```yaml
# GitHub Actions example
- name: Sign app
  env:
    VESPER_SIGN_PASSWORD: ${{ secrets.SIGN_PASSWORD }}
    VESPER_NOTARIZE_PASSWORD: ${{ secrets.NOTARIZE_PASSWORD }}
  run: vesper sign
```
