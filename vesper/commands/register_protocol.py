from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def add_register_protocol_parser(subparsers):
    p = subparsers.add_parser(
        "register-protocol",
        help="Register a custom URL protocol handler (e.g. myapp://)",
    )
    p.add_argument("scheme", nargs="?", help="Protocol scheme without '://' (e.g. myapp)")
    return p


def handle_register_protocol(args) -> bool:
    if args.command != "register-protocol":
        return False

    scheme = getattr(args, "scheme", None)
    if not scheme:
        print("Usage: vesper register-protocol <scheme>")
        print("Example: vesper register-protocol myapp")
        return True

    if sys.platform == "win32":
        _register_windows(scheme)
    elif sys.platform == "darwin":
        _register_macos(scheme)
    else:
        _register_linux(scheme)

    return True


def _register_windows(scheme: str) -> None:
    import winreg

    exe = sys.executable
    key_path = f"SOFTWARE\\Classes\\{scheme}"

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        winreg.SetValue(key, "", winreg.REG_SZ, f"URL:{scheme} Protocol")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{key_path}\\shell\\open\\command") as key:
        winreg.SetValue(key, "", winreg.REG_SZ, f'"{exe}" "%1"')

    print(f"Registered '{scheme}://' in Windows registry (HKCU\\SOFTWARE\\Classes\\{scheme}).")
    print("Re-run after packaging to point to the packaged executable.")


def _register_macos(scheme: str) -> None:
    print(f"On macOS, add the following to your app's Info.plist:")
    print()
    print("  <key>CFBundleURLTypes</key>")
    print("  <array>")
    print("    <dict>")
    print(f"      <key>CFBundleURLName</key>")
    print(f"      <string>{scheme}</string>")
    print(f"      <key>CFBundleURLSchemes</key>")
    print(f"      <array><string>{scheme}</string></array>")
    print("    </dict>")
    print("  </array>")
    print()
    print("See: https://developer.apple.com/documentation/xcode/defining-a-custom-url-scheme-for-your-app")


def _register_linux(scheme: str) -> None:
    exe = sys.executable
    app_name = scheme

    desktop_dir = Path.home() / ".local" / "share" / "applications"
    desktop_dir.mkdir(parents=True, exist_ok=True)

    desktop_file = desktop_dir / f"{app_name}.desktop"
    desktop_file.write_text(
        f"[Desktop Entry]\n"
        f"Name={app_name}\n"
        f"Exec={exe} %u\n"
        f"Type=Application\n"
        f"MimeType=x-scheme-handler/{scheme};\n"
    )

    subprocess.run(
        ["xdg-mime", "default", f"{app_name}.desktop", f"x-scheme-handler/{scheme}"],
        check=False,
    )
    subprocess.run(
        ["update-desktop-database", str(desktop_dir)],
        check=False,
    )

    print(f"Registered '{scheme}://' protocol handler.")
    print(f"Desktop file written to: {desktop_file}")
