from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from vesper.commands.utils import (
    FRAMEWORK_TEMPLATES,
    find_entrypoint,
    find_npx,
    read_vesper_toml,
)


# PyWebView hidden imports required by PyInstaller per platform
_PYWEBVIEW_HIDDEN_IMPORTS: dict[str, list[str]] = {
    "win32": [
        "webview.platforms.winforms",
        "clr",
    ],
    "darwin": [
        "webview.platforms.cocoa",
    ],
    "linux": [
        "webview.platforms.gtk",
        "gi",
        "gi.repository.Gtk",
        "gi.repository.WebKit2",
    ],
}


def _platform_key() -> str:
    if sys.platform == "win32":
        return "win32"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def _resolve_frontend_data(project_dir: Path, template: str) -> tuple[str, str]:
    if template in FRAMEWORK_TEMPLATES:
        if not (project_dir / "dist").is_dir():
            print("dist/ not found. Run 'vesper build' first.")
            raise SystemExit(1)
        return "dist", "dist"

    if not (project_dir / "frontend").is_dir():
        print("frontend/ not found.")
        print("")
        print("Run this command from the root of a Vesper project.")
        raise SystemExit(1)

    return "frontend", "frontend"


# ─── PyInstaller ─────────────────────────────────────────────────────────────


def _check_pyinstaller() -> str:
    import shutil

    path = shutil.which("pyinstaller")

    if path is None:
        print("PyInstaller not found.")
        print("")
        print("Install it with:")
        print("  pip install pyinstaller")
        raise SystemExit(1)

    return path


def package_with_pyinstaller(
    project_dir: Path,
    entrypoint: Path,
    app_name: str,
    data_src: str,
    data_dst: str,
) -> None:
    pyinstaller = _check_pyinstaller()

    package_dir = project_dir / "package"
    work_dir = project_dir / ".pyinstaller"

    separator = ";" if sys.platform == "win32" else ":"
    add_data = f"{data_src}{separator}{data_dst}"

    hidden = _PYWEBVIEW_HIDDEN_IMPORTS.get(_platform_key(), [])

    cmd = [
        pyinstaller,
        str(entrypoint),
        "--name", app_name,
        "--windowed",
        "--onefile",
        "--clean",
        "--noconfirm",
        "--distpath", str(package_dir),
        "--workpath", str(work_dir / "build"),
        "--specpath", str(work_dir),
        "--add-data", add_data,
    ]

    for import_name in hidden:
        cmd.extend(["--hidden-import", import_name])

    print("Packaging with PyInstaller...")
    print(f"  Entrypoint : {entrypoint.name}")
    print(f"  Frontend   : {data_src}/")
    print(f"  Output     : package/")
    print("")

    try:
        subprocess.run(cmd, cwd=project_dir, check=True)
    except subprocess.CalledProcessError as e:
        print("")
        print("PyInstaller failed.")
        raise SystemExit(e.returncode)

    suffix = ".exe" if sys.platform == "win32" else ""
    exe = package_dir / f"{app_name}{suffix}"

    print("")
    print(f"Package created: {exe}")
    print("")
    _print_distribution_note(bundler="pyinstaller")


# ─── Nuitka ──────────────────────────────────────────────────────────────────


def _check_nuitka() -> None:
    try:
        subprocess.run(
            [sys.executable, "-m", "nuitka", "--version"],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Nuitka not found.")
        print("")
        print("Install it with:")
        print("  pip install nuitka")
        raise SystemExit(1)


def package_with_nuitka(
    project_dir: Path,
    entrypoint: Path,
    app_name: str,
    data_src: str,
    data_dst: str,
) -> None:
    _check_nuitka()

    package_dir = project_dir / "package"

    cmd = [
        sys.executable,
        "-m", "nuitka",
        "--standalone",
        "--onefile",
        f"--output-filename={app_name}",
        f"--output-dir={package_dir}",
        f"--include-data-dir={data_src}={data_dst}",
    ]

    key = _platform_key()

    if key == "win32":
        cmd.append("--windows-disable-console")
    elif key == "darwin":
        cmd.append("--macos-disable-console")

    cmd.append(str(entrypoint))

    print("Packaging with Nuitka (this may take several minutes)...")
    print(f"  Entrypoint : {entrypoint.name}")
    print(f"  Frontend   : {data_src}/")
    print(f"  Output     : package/")
    print("")

    try:
        subprocess.run(cmd, cwd=project_dir, check=True)
    except subprocess.CalledProcessError as e:
        print("")
        print("Nuitka failed.")
        raise SystemExit(e.returncode)

    suffix = ".exe" if sys.platform == "win32" else ""
    exe = package_dir / f"{app_name}{suffix}"

    print("")
    print(f"Package created: {exe}")
    print("")
    _print_distribution_note(bundler="nuitka")


# ─── Post-package output ─────────────────────────────────────────────────────


def _print_distribution_note(*, bundler: str) -> None:
    if sys.platform == "win32":
        print("To distribute: share the .exe file from package/")
        print("Note: Windows users need Edge WebView2 Runtime (built-in on Windows 10/11).")
    elif sys.platform == "darwin":
        print("To distribute: share the binary from package/")
        print("Note: macOS may block unsigned binaries. Consider code signing for distribution.")
    else:
        print("To distribute: share the binary from package/")

    if bundler == "pyinstaller":
        print("")
        print("Build artifacts are in .pyinstaller/ — run 'vesper clean' to remove them.")


# ─── Dispatcher ──────────────────────────────────────────────────────────────


def package() -> None:
    project_dir = Path.cwd()
    config = read_vesper_toml(project_dir)

    template = config.get("template", "vanilla")
    bundler = config.get("bundler", "pyinstaller")
    app_name = config.get("name", project_dir.name)

    entrypoint = find_entrypoint(project_dir)

    if entrypoint is None:
        print("Could not find a Vesper app entrypoint.")
        print("")
        print("Run this command from the root of a Vesper project.")
        raise SystemExit(1)

    data_src, data_dst = _resolve_frontend_data(project_dir, template)

    if bundler == "nuitka":
        package_with_nuitka(project_dir, entrypoint, app_name, data_src, data_dst)
    else:
        package_with_pyinstaller(project_dir, entrypoint, app_name, data_src, data_dst)


# ─── CLI ─────────────────────────────────────────────────────────────────────


def add_package_parser(subparsers: argparse._SubParsersAction) -> None:
    subparsers.add_parser(
        "package",
        help="Package the Vesper app into a native executable.",
    )


def handle_package(args: argparse.Namespace) -> bool:
    if args.command == "package":
        package()
        return True

    return False
