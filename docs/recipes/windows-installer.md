# Recipe: Windows Installer (NSIS) and Linux AppImage

`vesper package --installer` builds a `.dmg` on macOS and a `.deb` on Debian/Ubuntu, because `hdiutil` and `dpkg-deb` ship with those systems. A Windows `.exe` installer needs **NSIS** (or WiX), and an AppImage needs **appimagetool** — external tools pip cannot install, which places them outside Vesper's zero-dependency core. This recipe covers driving them yourself.

**A note on scope:** recipes normally must cover all three platforms. An installer format is inherently single-platform — a Windows installer only means anything on Windows — so this recipe is the legitimate exception to that rule, not a precedent for skipping platforms elsewhere.

---

## Windows: NSIS

### 1. Install NSIS

```powershell
winget install NSIS
# or download from https://nsis.sourceforge.io
```

`vesper doctor` reports whether `makensis` is on your PATH (the `nsis` optional capability).

### 2. Package the app first

```bash
vesper build
vesper package        # → package/MyApp.exe
vesper sign           # recommended: sign the exe before wrapping it
```

### 3. Installer script

Save as `installer.nsi` in the project root and adjust the four `!define`s:

```nsis
!define APP_NAME    "MyApp"
!define APP_VERSION "1.0.0"
!define APP_EXE     "package\MyApp.exe"
!define PUBLISHER   "Your Name"

Name "${APP_NAME}"
OutFile "package\${APP_NAME}-${APP_VERSION}-setup.exe"
InstallDir "$LOCALAPPDATA\${APP_NAME}"
RequestExecutionLevel user          ; per-user install, no UAC prompt

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "Install"
    SetOutPath "$INSTDIR"
    File "${APP_EXE}"

    ; Start Menu shortcut
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_NAME}.exe"

    ; Uninstaller + Add/Remove Programs entry
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "DisplayName" "${APP_NAME}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "Publisher" "${PUBLISHER}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "UninstallString" '"$INSTDIR\Uninstall.exe"'
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\${APP_NAME}.exe"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir "$INSTDIR"
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    RMDir "$SMPROGRAMS\${APP_NAME}"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
SectionEnd
```

### 4. Build

```powershell
makensis installer.nsi
# → package\MyApp-1.0.0-setup.exe
```

Sign the resulting setup exe too (`vesper sign --path package/MyApp-1.0.0-setup.exe`) — SmartScreen judges the installer, not just the app inside it.

Remember that users still need the **Edge WebView2 Runtime** (preinstalled on Windows 11). For older Windows 10 machines, add the [WebView2 bootstrapper](https://developer.microsoft.com/microsoft-edge/webview2/) to the install section.

---

## Linux: AppImage

The `.deb` from `vesper package --installer` covers Debian/Ubuntu. An AppImage runs on any distribution without installation.

### 1. Get appimagetool

```bash
wget https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool-x86_64.AppImage
```

### 2. Build the AppDir

```bash
vesper build && vesper package     # → package/myapp

APP=myapp
mkdir -p MyApp.AppDir/usr/bin
cp package/$APP MyApp.AppDir/usr/bin/$APP
cp icon.png MyApp.AppDir/$APP.png

cat > MyApp.AppDir/$APP.desktop <<EOF
[Desktop Entry]
Type=Application
Name=MyApp
Exec=$APP
Icon=$APP
Categories=Utility;
EOF

cat > MyApp.AppDir/AppRun <<EOF
#!/bin/sh
exec "\$(dirname "\$0")/usr/bin/$APP" "\$@"
EOF
chmod +x MyApp.AppDir/AppRun
```

### 3. Build the image

```bash
./appimagetool-x86_64.AppImage MyApp.AppDir package/MyApp-x86_64.AppImage
```

**Caveat:** the app still renders through the system WebKitGTK — an AppImage bundles your binary, not the WebView. Users need the distribution packages listed in [Platform Requirements](../platform-requirements.md), exactly as with the raw binary.
