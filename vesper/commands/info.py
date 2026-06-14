from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

from vesper.commands.utils import find_entrypoint, get_installed_version


def info() -> None:
    current_directory = Path.cwd()

    vesper_version = get_installed_version("vesper") or "not installed"
    pywebview_version = get_installed_version("pywebview") or "not installed"
    python_version = ".".join(str(part) for part in sys.version_info[:3])
    platform_name = platform.platform()

    entrypoint = find_entrypoint(current_directory)

    frontend = current_directory / "frontend" / "index.html"
    sdk = current_directory / "frontend" / "vesper.js"

    print("Vesper Info")
    print("===========")
    print("")
    print(f"Vesper version: {vesper_version}")
    print(f"Python version: {python_version}")
    print(f"Platform: {platform_name}")
    print(f"pywebview version: {pywebview_version}")
    print(f"Current directory: {current_directory}")
    print(f"Entrypoint: {entrypoint.name if entrypoint else 'not found'}")
    print(f"Frontend: {'frontend/index.html' if frontend.is_file() else 'not found'}")
    print(f"SDK: {'frontend/vesper.js' if sdk.is_file() else 'not found'}")


def add_info_parser(subparsers: argparse._SubParsersAction) -> None:
    subparsers.add_parser(
        "info",
        help="Show information about the current Vesper environment."
    )


def handle_info(args: argparse.Namespace) -> bool:
    if args.command == "info":
        info()
        return True

    return False
