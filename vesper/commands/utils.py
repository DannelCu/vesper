from __future__ import annotations

import importlib.metadata
import shutil
from importlib.resources import files
from pathlib import Path


APP_ENTRYPOINTS = (
    "app.py",
    "main.py",
    "vesper_app.py",
)


def find_entrypoint(directory: Path) -> Path | None:
    """
    Find the Vesper application entrypoint in a directory.
    """

    for entrypoint_name in APP_ENTRYPOINTS:
        entrypoint = directory / entrypoint_name

        if entrypoint.is_file():
            return entrypoint

    return None


def copy_sdk_to_frontend(frontend_dir: Path) -> Path:
    """
    Copy the bundled Vesper JavaScript SDK into a frontend directory.
    """

    sdk_source = files("vesper").joinpath("sdk", "vesper.js")
    sdk_destination = frontend_dir / "vesper.js"

    with sdk_source.open("rb") as source_file:
        with sdk_destination.open("wb") as destination_file:
            shutil.copyfileobj(source_file, destination_file)

    return sdk_destination


def print_check(ok: bool, message: str, fix: str | None = None) -> None:
    """
    Print a formatted doctor check result.
    """

    icon = "[OK]" if ok else "[FAIL]"
    print(f"{icon} {message}")

    if not ok and fix:
        print(f"     Fix: {fix}")


def get_installed_version(package_name: str) -> str | None:
    """
    Return the installed package version, or None if the package is not installed.
    """

    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None
