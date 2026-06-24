from __future__ import annotations

import argparse
import os
import re
import shutil
import tempfile
from pathlib import Path

from vesper.commands.utils import (
    FRAMEWORK_TEMPLATES,
    check_node_modules,
    get_pm_executable,
    get_project_package_manager,
    pm_dlx,
    pm_run,
    read_vesper_toml,
)


# ─── Framework build ─────────────────────────────────────────────────────────


def build_framework(project_dir: Path, pm: str = "npm") -> None:
    check_node_modules(project_dir, pm)

    print("Building frontend...")
    pm_run(pm, project_dir, "build")

    dist_dir = project_dir / "dist"
    print("")
    print(f"Build complete: {dist_dir}")
    print("")
    print("To run the app:")
    print("  vesper run")


# ─── Vanilla build ───────────────────────────────────────────────────────────


def find_user_js(frontend_dir: Path) -> list[Path]:
    return [
        f for f in sorted(frontend_dir.glob("*.js"))
        if f.name != "vesper.js"
    ]


def _run_esbuild(project_dir: Path, entry: str, outfile: Path, pm: str = "npm") -> bool:
    return pm_dlx(pm, project_dir, "esbuild", entry, "--bundle", "--minify", f"--outfile={outfile}")


def _bundle_user_js(project_dir: Path, user_js_files: list[Path], dist_dir: Path, pm: str = "npm") -> bool:
    tmp_entry: Path | None = None

    if len(user_js_files) == 1:
        entry = str(user_js_files[0])
    else:
        fd, tmp_path = tempfile.mkstemp(suffix=".js", dir=project_dir)
        tmp_entry = Path(tmp_path)

        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for js_file in user_js_files:
                rel = js_file.relative_to(project_dir)
                f.write(f'import "./{rel.as_posix()}";\n')

        entry = str(tmp_entry)

    outfile = dist_dir / "bundle.js"

    try:
        return _run_esbuild(project_dir, entry, outfile, pm)
    finally:
        if tmp_entry and tmp_entry.exists():
            tmp_entry.unlink()


def _update_html_for_bundle(dist_dir: Path, user_js_files: list[Path]) -> None:
    html_path = dist_dir / "index.html"
    html = html_path.read_text(encoding="utf-8")

    for js_file in user_js_files:
        name = re.escape(js_file.name)
        html = re.sub(
            rf'\s*<script[^>]+src=["\']\.?/?{name}["\'][^>]*></script>',
            "",
            html,
        )

    html = html.replace("</body>", '  <script src="./bundle.js"></script>\n</body>')
    html_path.write_text(html, encoding="utf-8")


def build_vanilla(project_dir: Path, pm: str = "npm") -> None:
    frontend_dir = project_dir / "frontend"
    dist_dir = project_dir / "dist"

    if not frontend_dir.is_dir():
        print("frontend/ directory not found.")
        print("")
        print("Run this command from the root of a Vesper project.")
        raise SystemExit(1)

    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    shutil.copytree(frontend_dir, dist_dir)

    user_js_files = find_user_js(frontend_dir)

    if user_js_files:
        if get_pm_executable(pm) is not None:
            print(f"Bundling {len(user_js_files)} JS file(s) with esbuild...")
            bundled = _bundle_user_js(project_dir, user_js_files, dist_dir, pm)

            if bundled:
                for js_file in user_js_files:
                    dist_copy = dist_dir / js_file.name
                    if dist_copy.exists():
                        dist_copy.unlink()

                _update_html_for_bundle(dist_dir, user_js_files)
                print("JS bundled and minified: dist/bundle.js")
            else:
                print("esbuild failed — JS files copied without bundling.")
        else:
            print(f"{pm} not found — JS files copied without bundling.")

    print("")
    print(f"Build complete: {dist_dir}")


# ─── Dispatcher ──────────────────────────────────────────────────────────────


def build() -> None:
    project_dir = Path.cwd()
    config = read_vesper_toml(project_dir)
    template = config.get("template", "vanilla")
    pm = get_project_package_manager(project_dir)

    if template in FRAMEWORK_TEMPLATES:
        build_framework(project_dir, pm)
    else:
        build_vanilla(project_dir, pm)


# ─── CLI ─────────────────────────────────────────────────────────────────────


def add_build_parser(subparsers: argparse._SubParsersAction) -> None:
    subparsers.add_parser(
        "build",
        help="Build the Vesper app for production.",
    )


def handle_build(args: argparse.Namespace) -> bool:
    if args.command == "build":
        build()
        return True

    return False
