# Platform Requirements

Vesper renders through the operating system's **native WebView**. This is the one
dependency that cannot be fixed from Python: `pip install vesper` pulls in pywebview,
which is pure Python and does not install any renderer. Without the platform runtime
below, the framework installs cleanly and then fails the moment a window opens.

Everything else Vesper touches is optional and degrades to a no-op — see
[Optional Features](optional-features.md). This page is about the part that does not.

Run `vesper doctor` to see which backend actually resolved on your machine. It
reports the resolved backend by name, which settles most environment questions
immediately.

---

## Windows

Needs the **Microsoft Edge WebView2 Runtime**.

- Preinstalled on Windows 11 and on up-to-date Windows 10.
- Otherwise download the Evergreen Standalone Installer from
  [Microsoft's WebView2 page](https://developer.microsoft.com/microsoft-edge/webview2/).

`pythonnet` is installed automatically as a pywebview dependency.

**The failure mode here is quiet.** With the runtime absent, pywebview falls back to
the legacy MSHTML (IE11) renderer instead of refusing to start. The app launches and
then modern CSS and JavaScript break in ways that look like bugs in your own code.
`vesper doctor` reports that fallback as a failure rather than letting you debug it
blind.

If you ship an installer, bundle the WebView2 bootstrapper or document the runtime as
a prerequisite — a machine without it is not a rare case on Windows 10.

---

## Linux

Needs **GTK + WebKit2GTK**, both the C libraries and the GObject introspection
bindings. These are distribution packages; pip cannot install them.

```bash
# Debian / Ubuntu
sudo apt install python3-gi gir1.2-webkit2-4.1 libwebkit2gtk-4.1-0

# Fedora
sudo dnf install python3-gobject webkit2gtk4.1

# Arch
sudo pacman -S python-gobject webkit2gtk-4.1
```

**Create your virtualenv with `--system-site-packages`.** The GTK bindings live in
the system `site-packages`, and a default venv is isolated from them:

```bash
python3 -m venv --system-site-packages .venv
```

Without it, every window fails with `ModuleNotFoundError: No module named 'gi'` even
though the distro packages are installed correctly. This is the single most common
Linux setup problem with Vesper.

**Qt instead of GTK:** `pip install pyqt5 pyqtwebengine` and set `PYWEBVIEW_GUI=qt`.
Vesper prefers GTK, except under KDE (`KDE_FULL_SESSION` is set), where pywebview
prefers Qt automatically.

**Wayland** works, but a few integrations are weaker than on X11 — see
[Optional Features](optional-features.md).

**Playing video needs codec packages.** WebKitGTK decodes through GStreamer, so what
your `<video>` element can play depends on which plugin packages are installed — a
machine without `gstreamer1.0-libav` refuses H.264 in an `.mp4` that plays fine on
Windows and macOS. This is on top of the limits every platform shares: a WebView plays
*web* formats, so `.avi`, `.wmv` and friends never play anywhere, whatever is
installed. [Playing Video](recipes/video-playback.md) covers both, and how to convert
what the engine cannot open.

```bash
# Debian / Ubuntu — H.264 and the common codecs
sudo apt install gstreamer1.0-libav gstreamer1.0-plugins-good gstreamer1.0-plugins-bad
```

---

## macOS

Needs nothing installed. The Cocoa/WKWebView backend ships with the system, and
PyObjC arrives as a pywebview dependency.

One requirement is easy to miss: **use a framework build of Python.** Cocoa requires
one to create windows, take keyboard focus, and own a menu bar. The python.org
installers, Xcode's Python and Homebrew's `python@3.x` all provide one. A bare
`pyenv install` does **not**:

```bash
PYTHON_CONFIGURE_OPTS="--enable-framework" pyenv install 3.12
```

Symptoms of a non-framework build: the window opens behind other apps, never takes
focus, or the process dies with `NSInternalInconsistencyException`.

**Xcode Command Line Tools** (`xcode-select --install`) are needed only for code
signing — see [Code Signing](code-signing.md).

---

## Summary

| Platform | Runtime | Installed by |
|---|---|---|
| Windows | Edge WebView2 | Microsoft installer, or preinstalled |
| Linux | WebKit2GTK + python3-gi | Your distribution's package manager |
| macOS | WKWebView | Ships with the OS |

Contributors setting up a development environment should read
[CONTRIBUTING.md](../CONTRIBUTING.md), which covers the same ground plus the editable
install and the test suite.
