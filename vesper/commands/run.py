from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

from vesper.commands.utils import (
    APP_ENTRYPOINTS,
    FRAMEWORK_TEMPLATES,
    find_entrypoint,
    read_vesper_toml,
)


def run_app() -> None:
    current_directory = Path.cwd()

    config = read_vesper_toml(current_directory)
    template = config.get("template", "vanilla")

    if template in FRAMEWORK_TEMPLATES and not (current_directory / "dist").exists():
        print("dist/ not found. Run `vesper build` first.")
        raise SystemExit(1)

    entrypoint = find_entrypoint(current_directory)

    if entrypoint is None:
        print("Could not find a Vesper app entrypoint.")
        print("")
        print("Expected one of:")

        for entrypoint_name in APP_ENTRYPOINTS:
            print(f"  - {entrypoint_name}")

        raise SystemExit(1)

    print(f"Running Vesper app: {entrypoint.name}")

    sys.path.insert(0, str(current_directory))
    runpy.run_path(str(entrypoint), run_name="__main__")


def add_run_parser(subparsers: argparse._SubParsersAction) -> None:
    subparsers.add_parser(
        "run",
        help="Run the Vesper app in the current directory."
    )


def handle_run(args: argparse.Namespace) -> bool:
    if args.command == "run":
        run_app()
        return True

    return False
