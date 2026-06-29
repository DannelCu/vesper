from __future__ import annotations

import argparse
import importlib
import shutil
from pathlib import Path

from vesper.commands.utils import (
    FRAMEWORK_TEMPLATES,
    copy_sdk_to_frontend,
    read_vesper_toml,
    read_vesper_toml_section,
)


def _sdk_dir(project_dir: Path) -> Path:
    config = read_vesper_toml(project_dir)
    template = config.get("template", "vanilla")
    d = project_dir / ("public" if template in FRAMEWORK_TEMPLATES else "frontend")

    if not d.is_dir():
        print(f"SDK directory not found: {d.name}/")
        print("")
        print("Run this command from the root of a Vesper app.")
        raise SystemExit(1)

    return d


def _sync_plugin_sdk(project_dir: Path, sdk_dir: Path) -> None:
    plugins = read_vesper_toml_section(project_dir, "plugins")
    if not plugins:
        return

    for _alias, package_name in plugins.items():
        module_name = package_name.replace("-", "_")
        try:
            mod = importlib.import_module(module_name)
        except ImportError:
            print(f"[WARN] Plugin {package_name} not installed — skipping JS sync.")
            continue

        plugin_cls = getattr(mod, "Plugin", None)
        if plugin_cls is None or not callable(getattr(plugin_cls, "sdk_path", None)):
            continue

        js = plugin_cls.sdk_path()
        if js is None:
            continue

        dest = sdk_dir / Path(js).name
        shutil.copy2(js, dest)
        print(f"Updated {dest.relative_to(project_dir)} (from {package_name})")


def sync_sdk() -> None:
    project_dir = Path.cwd()
    sdk_dir = _sdk_dir(project_dir)

    dest = copy_sdk_to_frontend(sdk_dir)
    print(f"Updated {dest.relative_to(project_dir)} from Vesper SDK.")

    _sync_plugin_sdk(project_dir, sdk_dir)


def add_sync_sdk_parser(subparsers: argparse._SubParsersAction) -> None:
    subparsers.add_parser(
        "sync-sdk",
        help="Update vesper.js and plugin SDK files in the frontend directory."
    )


def handle_sync_sdk(args: argparse.Namespace) -> bool:
    if args.command == "sync-sdk":
        sync_sdk()
        return True

    return False
