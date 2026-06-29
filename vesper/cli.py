from __future__ import annotations

import argparse

from vesper.commands.build import add_build_parser, handle_build
from vesper.commands.clean import add_clean_parser, handle_clean
from vesper.commands.generate import add_generate_parser, handle_generate
from vesper.commands.package import add_package_parser, handle_package
from vesper.commands.dev import add_dev_parser, handle_dev
from vesper.commands.doctor import add_doctor_parser, handle_doctor
from vesper.commands.info import add_info_parser, handle_info
from vesper.commands.init import add_init_parser, handle_init
from vesper.commands.run import add_run_parser, handle_run
from vesper.commands.sign import add_sign_parser, handle_sign
from vesper.commands.sync_sdk import add_sync_sdk_parser, handle_sync_sdk
from vesper.commands.sync_types import add_sync_types_parser, handle_sync_types
from vesper.commands.utils import get_installed_version
from vesper.commands.version import add_version_parser, handle_version


def build_parser() -> argparse.ArgumentParser:
    vesper_version = get_installed_version("vesper") or "unknown"

    parser = argparse.ArgumentParser(
        prog="vesper",
        description="Vesper command line interface."
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"Vesper {vesper_version}",
    )

    subparsers = parser.add_subparsers(dest="command")

    add_init_parser(subparsers)
    add_run_parser(subparsers)
    add_dev_parser(subparsers)
    add_build_parser(subparsers)
    add_package_parser(subparsers)
    add_sign_parser(subparsers)
    add_sync_sdk_parser(subparsers)
    add_sync_types_parser(subparsers)
    add_generate_parser(subparsers)
    add_doctor_parser(subparsers)
    add_info_parser(subparsers)
    add_version_parser(subparsers)
    add_clean_parser(subparsers)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    handlers = (
        handle_init,
        handle_run,
        handle_dev,
        handle_build,
        handle_package,
        handle_sign,
        handle_sync_sdk,
        handle_sync_types,
        handle_generate,
        handle_doctor,
        handle_info,
        handle_version,
        handle_clean,
    )

    for handler in handlers:
        if handler(args):
            return

    parser.print_help()


if __name__ == "__main__":
    main()
