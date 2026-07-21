from __future__ import annotations

import argparse
import importlib
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from vesper.commands.utils import (
    find_entrypoint,
    get_installed_version,
    print_check,
    read_vesper_toml,
    read_vesper_toml_section,
)

_PROJECT_VALID_KEYS = {"name", "template", "styles", "bundler", "package_manager", "version"}
_PROJECT_VALID_VALUES: dict[str, set[str]] = {
    "template": {"vanilla", "react", "vue", "svelte"},
    "styles": {"none", "bootstrap", "tailwind"},
    "bundler": {"pyinstaller", "nuitka"},
    "package_manager": {"npm", "pnpm", "yarn"},
}
_UPDATE_VALID_KEYS = {"check_url"}
_SIGN_VALID_KEYS = {"identity", "entitlements", "notarize", "apple_id", "team_id", "certificate", "timestamp_url"}
_SIGN_VALID_VALUES: dict[str, set[str]] = {
    "notarize": {"true", "false"},
}


_BACKEND_LABELS = {
    "gtk": "GTK / WebKit2",
    "qt": "Qt / QtWebEngine",
    "cocoa": "Cocoa / WKWebView",
    "winforms": "WinForms / WebView2",
}

_LINUX_BACKEND_FIX = (
    "Install the system WebView runtime, then recreate your venv with "
    "--system-site-packages (the GTK bindings are a distro package, not a pip package). "
    "Debian/Ubuntu: sudo apt install python3-gi gir1.2-webkit2-4.1 libwebkit2gtk-4.1-0. "
    "Fedora: sudo dnf install python3-gobject webkit2gtk4.1. "
    "Arch: sudo pacman -S python-gobject webkit2gtk-4.1. "
    "Alternative: pip install pyqt5 pyqtwebengine"
)

_MACOS_BACKEND_FIX = (
    "Install the Cocoa bindings: pip install pyobjc-core pyobjc-framework-Cocoa "
    "pyobjc-framework-WebKit. If they are already installed, your Python is likely not a "
    "framework build - use python.org, Xcode, or `brew install python-tk` style framework "
    "Python, since Cocoa windows require one."
)

_WINDOWS_BACKEND_FIX = (
    "Install pythonnet (pip install pythonnet) and the Microsoft Edge WebView2 Runtime "
    "from https://developer.microsoft.com/microsoft-edge/webview2/"
)


def _candidate_backends() -> list[str]:
    """
    Backend import order pywebview will use on this platform.

    Mirrors webview.guilib.initialize() without importing pywebview itself, so the
    check stays cheap and never constructs a GUI application.
    """

    forced = os.environ.get("PYWEBVIEW_GUI", "").lower()
    if not forced and "KDE_FULL_SESSION" in os.environ:
        forced = "qt"

    system = platform.system()

    if system == "Darwin":
        return ["qt", "cocoa"] if forced == "qt" else ["cocoa", "qt"]
    if system in ("Linux", "OpenBSD"):
        return ["qt", "gtk"] if forced == "qt" else ["gtk", "qt"]
    if system == "Windows":
        return ["qt", "winforms"] if forced == "qt" else ["winforms"]

    return []


def _detect_webview_backend() -> tuple[bool, str, str | None]:
    """
    Resolve the WebView backend pywebview would actually use.

    pywebview is a pure-Python package, so `pip install pywebview` succeeding says
    nothing about whether a usable native WebView exists. Importing the backend module
    is what surfaces a missing GTK/WebKit, PyObjC, or pythonnet install - which would
    otherwise only fail at app.run(), long after doctor reported everything green.
    """

    system = platform.system()

    if system not in ("Darwin", "Linux", "OpenBSD", "Windows"):
        return False, f"Unsupported platform: {system or 'unknown'}", None

    fix = {
        "Darwin": _MACOS_BACKEND_FIX,
        "Linux": _LINUX_BACKEND_FIX,
        "OpenBSD": _LINUX_BACKEND_FIX,
        "Windows": _WINDOWS_BACKEND_FIX,
    }[system]

    for backend in _candidate_backends():
        try:
            module = importlib.import_module(f"webview.platforms.{backend}")
        except BaseException:
            # gi.require_version raises ValueError, pythonnet can raise beyond
            # ImportError, and a broken install can raise almost anything. A probe
            # must never take doctor down with it.
            continue

        label = _BACKEND_LABELS.get(backend, backend)

        # On Windows pywebview silently degrades to the legacy MSHTML (IE11) renderer
        # when the WebView2 runtime is absent. It "works", but modern CSS and JS break,
        # so surface it as a failure rather than a passing check.
        if backend == "winforms" and getattr(module, "renderer", None) == "mshtml":
            return (
                False,
                "WebView backend: WinForms fell back to MSHTML (legacy IE11 renderer)",
                "Install the Microsoft Edge WebView2 Runtime from "
                "https://developer.microsoft.com/microsoft-edge/webview2/",
            )

        return True, f"WebView backend available: {label}", None

    return False, "WebView backend: none available", fix


_CAPABILITY_LABELS = {
    "clipboard_text": "Clipboard (text)",
    "clipboard_image": "Clipboard (images)",
    "notifications": "Notifications",
    "trash": "Move to trash",
    "keep_awake": "Keep awake",
    "tray": "System tray",
    "badge": "Taskbar / dock badge",
    "global_shortcuts": "Global shortcuts",
}


def _print_optional_features() -> None:
    """
    Report the optional capability matrix.

    Nothing here counts towards doctor's exit status. These features are optional by
    definition — an app that never opens a tray icon is not broken for lacking
    pystray — so a missing one is information, not a failure.
    """
    from vesper.core import capabilities

    report = capabilities.probe()

    print("")
    print("Optional features")
    print("-----------------")

    for name, entry in report.items():
        label = _CAPABILITY_LABELS.get(name, name)
        print_check(
            entry["available"],
            f"{label}: {entry['detail']}",
            entry["fix"],
            critical=False,
        )

    missing = sum(1 for entry in report.values() if not entry["available"])
    if missing:
        print("")
        print(
            f"{missing} optional feature(s) unavailable. These degrade to no-ops "
            "rather than errors; install the above only if your app uses them."
        )


def doctor() -> None:
    """
    Diagnose the current Vesper project and environment.
    """

    current_directory = Path.cwd()
    has_failures = False

    print("Vesper Doctor")
    print("=============")
    print("")

    python_version = ".".join(str(part) for part in sys.version_info[:3])
    python_ok = sys.version_info >= (3, 10)
    print_check(
        python_ok,
        f"Python version: {python_version}",
        "Install Python 3.10 or newer."
    )
    has_failures = has_failures or not python_ok

    vesper_version = get_installed_version("vesper")
    vesper_ok = vesper_version is not None
    print_check(
        vesper_ok,
        f"Vesper installed: {vesper_version or 'not found'}",
        "Run `pip install -e .` from the Vesper package root."
    )
    has_failures = has_failures or not vesper_ok

    pywebview_version = get_installed_version("pywebview")
    pywebview_ok = pywebview_version is not None
    print_check(
        pywebview_ok,
        f"pywebview installed: {pywebview_version or 'not found'}",
        "Run `pip install pywebview` or reinstall Vesper with `pip install -e .`."
    )
    has_failures = has_failures or not pywebview_ok

    if pywebview_ok:
        backend_ok, backend_message, backend_fix = _detect_webview_backend()
        print_check(backend_ok, backend_message, backend_fix)
        has_failures = has_failures or not backend_ok

    node_path = shutil.which("node")
    node_version: str | None = None
    node_ok = False
    if node_path:
        try:
            result = subprocess.run(
                [node_path, "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                node_version = result.stdout.strip()
                major = int(node_version.lstrip("v").split(".")[0])
                node_ok = major >= 18
        except Exception:
            pass
    print_check(
        node_ok,
        f"Node.js version: {node_version or 'not found'}",
        "Install Node.js 18 or newer from https://nodejs.org",
    )
    has_failures = has_failures or not node_ok

    toml_config = read_vesper_toml(current_directory)
    pm = toml_config.get("package_manager", "npm")
    pm_path = shutil.which(pm)
    pm_ok = pm_path is not None
    print_check(
        pm_ok,
        f"Package manager available: {pm}" if pm_ok else f"Package manager not found: {pm}",
        f"Install {pm} or set 'package_manager' in vesper.toml",
    )
    has_failures = has_failures or not pm_ok

    toml_path = current_directory / "vesper.toml"
    if toml_path.is_file():
        project_section = read_vesper_toml_section(current_directory, "project")
        update_section = read_vesper_toml_section(current_directory, "update")

        toml_errors: list[str] = []
        for key, value in project_section.items():
            if key not in _PROJECT_VALID_KEYS:
                toml_errors.append(f"[project] unknown key '{key}'")
            elif key in _PROJECT_VALID_VALUES and value not in _PROJECT_VALID_VALUES[key]:
                toml_errors.append(f"[project] invalid value for '{key}': '{value}'")
        for key in update_section:
            if key not in _UPDATE_VALID_KEYS:
                toml_errors.append(f"[update] unknown key '{key}'")
        if update_section.get("check_url") and not project_section.get("version"):
            toml_errors.append("[update] check_url is set but [project] version is missing")

        sign_section = read_vesper_toml_section(current_directory, "sign")
        for key, value in sign_section.items():
            if key not in _SIGN_VALID_KEYS:
                toml_errors.append(f"[sign] unknown key '{key}'")
            elif key in _SIGN_VALID_VALUES and value not in _SIGN_VALID_VALUES[key]:
                toml_errors.append(f"[sign] invalid value for '{key}': '{value}'")
        if sign_section.get("notarize", "").lower() == "true":
            if not sign_section.get("apple_id"):
                toml_errors.append("[sign] notarize is true but apple_id is missing")
            if not sign_section.get("team_id"):
                toml_errors.append("[sign] notarize is true but team_id is missing")

        toml_ok = not toml_errors
        msg = (
            "vesper.toml schema is valid"
            if toml_ok
            else f"vesper.toml schema errors: {'; '.join(toml_errors)}"
        )
        print_check(toml_ok, msg, "Check vesper.toml for typos in keys or values.")
        has_failures = has_failures or not toml_ok

        plugins_section = read_vesper_toml_section(current_directory, "plugins")
        for _alias, package_name in plugins_section.items():
            version = get_installed_version(package_name)
            plugin_ok = version is not None
            print_check(
                plugin_ok,
                f"Plugin {package_name} installed: {version}" if plugin_ok else f"Plugin {package_name} not installed",
                f"Run `pip install {package_name}`",
            )
            has_failures = has_failures or not plugin_ok

        if sign_section:
            import sys as _sys
            from vesper.commands.sign import find_signtool
            if _sys.platform == "darwin":
                codesign_ok = shutil.which("codesign") is not None
                print_check(
                    codesign_ok,
                    "codesign available" if codesign_ok else "codesign not found",
                    "Install Xcode Command Line Tools: xcode-select --install",
                )
                has_failures = has_failures or not codesign_ok
                if sign_section.get("notarize", "").lower() == "true":
                    xcrun_ok = shutil.which("xcrun") is not None
                    print_check(
                        xcrun_ok,
                        "xcrun available" if xcrun_ok else "xcrun not found",
                        "Install Xcode Command Line Tools: xcode-select --install",
                    )
                    has_failures = has_failures or not xcrun_ok
            elif _sys.platform == "win32":
                signtool_ok = find_signtool() is not None
                osslsign_ok = shutil.which("osslsigncode") is not None
                tool_ok = signtool_ok or osslsign_ok
                tool_name = "signtool" if signtool_ok else ("osslsigncode" if osslsign_ok else "none")
                print_check(
                    tool_ok,
                    f"Signing tool available: {tool_name}" if tool_ok else "No signing tool found (signtool / osslsigncode)",
                    "Install Windows SDK (signtool) or osslsigncode.",
                )
                has_failures = has_failures or not tool_ok

    entrypoint = find_entrypoint(current_directory)
    entrypoint_ok = entrypoint is not None
    print_check(
        entrypoint_ok,
        f"Entrypoint found: {entrypoint.name if entrypoint else 'not found'}",
        "Run this command from the root of a Vesper app, or create app.py."
    )
    has_failures = has_failures or not entrypoint_ok

    frontend_dir = current_directory / "frontend"
    frontend_dir_ok = frontend_dir.is_dir()
    print_check(
        frontend_dir_ok,
        "Frontend directory found: frontend" if frontend_dir_ok else "Frontend directory missing: frontend",
        "Create a frontend directory or run `vesper init app --name \"my app\"`."
    )
    has_failures = has_failures or not frontend_dir_ok

    index_html = frontend_dir / "index.html"
    index_html_ok = index_html.is_file()
    print_check(
        index_html_ok,
        "Frontend entry found: frontend/index.html" if index_html_ok else "Frontend entry missing: frontend/index.html",
        "Create frontend/index.html."
    )
    has_failures = has_failures or not index_html_ok

    sdk_file = frontend_dir / "vesper.js"
    sdk_file_ok = sdk_file.is_file()
    print_check(
        sdk_file_ok,
        "Vesper SDK found: frontend/vesper.js" if sdk_file_ok else "Vesper SDK missing: frontend/vesper.js",
        "Run `vesper sync-sdk`."
    )
    has_failures = has_failures or not sdk_file_ok

    sdk_script_ok = False

    if index_html_ok:
        index_content = index_html.read_text(encoding="utf-8")
        sdk_script_ok = (
            'src="./vesper.js"' in index_content
            or "src='./vesper.js'" in index_content
            or 'src="vesper.js"' in index_content
            or "src='vesper.js'" in index_content
        )

    print_check(
        sdk_script_ok,
        "SDK script tag found in frontend/index.html" if sdk_script_ok else "SDK script tag missing in frontend/index.html",
        'Add: <script src="./vesper.js"></script>'
    )
    has_failures = has_failures or not sdk_script_ok

    # Last, and deliberately not folded into has_failures: this is its own titled
    # section, and putting it between the critical checks would break their flow.
    _print_optional_features()

    print("")

    if has_failures:
        print("Doctor found issues in this Vesper project.")
        raise SystemExit(1)

    print("All checks passed.")


def add_doctor_parser(subparsers: argparse._SubParsersAction) -> None:
    subparsers.add_parser(
        "doctor",
        help="Diagnose the current Vesper project and environment."
    )


def handle_doctor(args: argparse.Namespace) -> bool:
    if args.command == "doctor":
        doctor()
        return True

    return False
