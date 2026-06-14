from __future__ import annotations

import argparse

from vesper.commands.utils import get_installed_version


def version() -> None:
    """
    Print the installed Vesper version.
    """

    vesper_version = get_installed_version("vesper") or "unknown"
    print(f"Vesper {vesper_version}")


def add_version_parser(subparsers: argparse._SubParsersAction) -> None:
    subparsers.add_parser(
        "version",
        help="Show the installed Vesper version."
    )


def handle_version(args: argparse.Namespace) -> bool:
    if args.command == "version":
        version()
        return True

    return False
