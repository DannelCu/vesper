from __future__ import annotations

import argparse
from pathlib import Path

from vesper.commands.utils import copy_sdk_to_frontend


def sync_sdk() -> None:
    """
    Sync the bundled Vesper JavaScript SDK into the current project.
    """

    current_directory = Path.cwd()
    frontend_dir = current_directory / "frontend"

    if not frontend_dir.is_dir():
        print("Could not find frontend directory.")
        print("")
        print("Expected:")
        print("  frontend")
        print("")
        print("Run this command from the root of a Vesper app.")
        raise SystemExit(1)

    sdk_destination = copy_sdk_to_frontend(frontend_dir)

    print(f"Updated {sdk_destination.relative_to(current_directory)} from Vesper SDK.")


def add_sync_sdk_parser(subparsers: argparse._SubParsersAction) -> None:
    subparsers.add_parser(
        "sync-sdk",
        help="Update frontend/vesper.js from the bundled Vesper SDK."
    )


def handle_sync_sdk(args: argparse.Namespace) -> bool:
    if args.command == "sync-sdk":
        sync_sdk()
        return True

    return False
