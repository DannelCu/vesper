# Recipe: Camera and Microphone (getUserMedia)

Making `navigator.mediaDevices.getUserMedia()` work inside a Vesper app — per platform, with the honest caveat up front:

**This recipe improves the odds; it cannot guarantee them.** The WebView's permission handler — the API that would let Vesper answer "yes, allow the camera" programmatically — is not exposed by PyWebView, so whether the prompt appears (or is silently denied) is ultimately up to the engine and the OS. See [KNOWN-ISSUES KI5](../../KNOWN-ISSUES.md#ki5). Everything below is the manual configuration that maximises the chance the engine says yes, plus the detection pattern your UI needs for when it says no.

---

## macOS

WKWebView refuses media capture unless the *host app* declares why it needs it, and the declaration only counts when the app is a real, signed bundle.

1. **Package the app** (`vesper package` — the `.app` bundle from PyInstaller's `--windowed` mode).

2. **Add usage descriptions to `Info.plist`** inside the bundle (`dist/MyApp.app/Contents/Info.plist`). These strings appear in the OS permission prompt:

   ```xml
   <key>NSCameraUsageDescription</key>
   <string>My App uses the camera for video notes.</string>
   <key>NSMicrophoneUsageDescription</key>
   <string>My App uses the microphone to record audio.</string>
   ```

   An unpackaged `python app.py` has no bundle and no `Info.plist` — capture generally fails in development on macOS. Test packaged.

3. **Entitlements + signing.** Create (or extend) an entitlements file:

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
     "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>com.apple.security.device.camera</key><true/>
       <key>com.apple.security.device.audio-input</key><true/>
   </dict>
   </plist>
   ```

   Reference it from `vesper.toml` and sign:

   ```toml
   [sign]
   identity     = "Developer ID Application: You (TEAMID)"
   entitlements = "entitlements.plist"
   ```

   ```bash
   vesper sign
   ```

   See [Code Signing](../code-signing.md).

4. The user still gets the OS prompt on first use, and can revoke it later in **System Settings → Privacy & Security → Camera / Microphone**.

---

## Windows

WebView2 delegates to the Chromium permission model plus the OS privacy settings:

1. **OS-level toggles gate everything**: **Settings → Privacy & security → Camera / Microphone**. Both the global toggle and "Let desktop apps access your camera" must be on — when they are off, `getUserMedia` fails with `NotAllowedError` and no prompt.
2. WebView2 shows its own permission prompt per origin. With the localhost server (`App(serve_frontend=True)`) the origin is `http://127.0.0.1:<port>` and the port changes per run, so **the grant may not persist between runs** — expect the prompt again. Loading via `file://` has an opaque origin, which some WebView2 versions treat less favourably; if capture matters to your app, prefer the localhost mode.
3. Nothing needs to be installed; there are no manifest declarations for an unpackaged desktop app.

---

## Linux

WebKitGTK's capture support depends on how the distribution built it:

1. WebKitGTK needs **GStreamer** and its plugin sets at runtime:

   ```bash
   # Debian / Ubuntu
   sudo apt install gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-pipewire

   # Fedora (usually present)
   sudo dnf install gstreamer1-plugins-good gstreamer1-plugins-bad-free

   # Arch
   sudo pacman -S gst-plugins-good gst-plugins-bad gst-plugin-pipewire
   ```

2. Some distro builds of WebKitGTK were compiled **without** `ENABLE_MEDIA_STREAM` — on those, `navigator.mediaDevices` is simply `undefined` and no package fixes it short of a different WebKitGTK build. This is the platform reality the fallback below exists for.
3. On Wayland, camera access increasingly routes through PipeWire (hence the pipewire plugin above).

---

## The fallback pattern — always ship this

Permission can be denied, revoked, or structurally unavailable, and your UI must degrade instead of hanging on a black `<video>`:

```js
async function startCamera(videoEl) {
    // Engine compiled without media support (some Linux WebKitGTK builds)
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        return { ok: false, reason: "unsupported" }
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: true,
            audio: false,
        })
        videoEl.srcObject = stream
        return { ok: true, stream }
    } catch (err) {
        // NotAllowedError: denied (user, OS setting, or engine policy)
        // NotFoundError:   no camera device
        // NotReadableError: device busy or backend failure
        return { ok: false, reason: err.name }
    }
}

const result = await startCamera(video)
if (!result.ok) {
    video.hidden = true
    fallbackMessage.textContent = {
        unsupported:      "Camera capture isn't available in this environment.",
        NotAllowedError:  "Camera permission was denied — check your system privacy settings.",
        NotFoundError:    "No camera was found.",
    }[result.reason] || "The camera could not be started."

    // A file picker is a universal fallback for "attach a photo".
    filePicker.hidden = false
}
```

For "attach a photo/video" flows, `<input type="file" accept="image/*" capture>` sidesteps `getUserMedia` entirely and works everywhere a file picker works.

---

## Why this is a recipe and not a feature

Electron exposes a session permission handler; the engines under PyWebView have equivalents (WKWebView's `decidePolicyForMediaCapturePermission`, WebView2's `PermissionRequested`) — but PyWebView does not surface them, so Vesper cannot grant or even observe the permission programmatically. When it does, this recipe collapses into an API. Tracked as [KI5](../../KNOWN-ISSUES.md#ki5).
