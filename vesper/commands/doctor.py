from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vesper.commands.utils import find_entrypoint, get_installed_version, print_check


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
