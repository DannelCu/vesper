from __future__ import annotations

import argparse
import shutil
from pathlib import Path


DIRECTORY_PATTERNS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
}

FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
}


def find_clean_targets(root: Path) -> list[Path]:
    """
    Find files and directories that can be safely removed.
    """

    targets: list[Path] = []

    for path in root.rglob("*"):
        if path.is_dir() and path.name in DIRECTORY_PATTERNS:
            targets.append(path)
            continue

        if path.is_file() and path.suffix in FILE_SUFFIXES:
            targets.append(path)

    return sorted(targets, key=lambda item: len(item.parts), reverse=True)


def remove_target(path: Path) -> None:
    """
    Remove a clean target from disk.
    """

    if path.is_dir():
        shutil.rmtree(path)
        return

    path.unlink()


def clean_project(*, yes: bool = False, dry_run: bool = False) -> None:
    """
    Clean temporary files from the current project.
    """

    current_directory = Path.cwd()
    targets = find_clean_targets(current_directory)

    if not targets:
        print("Nothing to clean.")
        return

    print("Clean targets:")
    print("")

    for target in targets:
        print(f"  - {target.relative_to(current_directory)}")

    print("")

    if dry_run:
        print("Dry run enabled. No files were removed.")
        return

    if not yes:
        answer = input("Remove these files and directories? [y/N]: ").strip().lower()

        if answer not in {"y", "yes"}:
            print("Clean cancelled.")
            return

    for target in targets:
        remove_target(target)

    print("Project cleaned.")


def add_clean_parser(subparsers: argparse._SubParsersAction) -> None:
    clean_parser = subparsers.add_parser(
        "clean",
        help="Remove temporary files from the current project."
    )

    clean_parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Remove files without asking for confirmation."
    )

    clean_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without deleting anything."
    )


def handle_clean(args: argparse.Namespace) -> bool:
    if args.command == "clean":
        clean_project(
            yes=args.yes,
            dry_run=args.dry_run,
        )
        return True

    return False
