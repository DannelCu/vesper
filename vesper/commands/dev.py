from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from vesper.commands.utils import (
    APP_ENTRYPOINTS,
    FRAMEWORK_TEMPLATES,
    check_node_modules,
    ensure_pm,
    find_entrypoint,
    get_project_package_manager,
    read_vesper_toml,
)

_WATCH_SKIP_DIRS = frozenset({
    "__pycache__", ".git", "node_modules", ".venv", "venv",
    "dist", ".pyinstaller", "build", "package",
})


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _get_py_mtimes(project_dir: Path) -> dict[Path, float]:
    mtimes: dict[Path, float] = {}
    for p in project_dir.rglob("*.py"):
        if _WATCH_SKIP_DIRS.intersection(p.parts):
            continue
        try:
            mtimes[p] = p.stat().st_mtime
        except OSError:
            pass
    return mtimes


def _start_app(entrypoint: Path, extra_env: dict[str, str] | None = None) -> subprocess.Popen:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    return subprocess.Popen([sys.executable, str(entrypoint)], env=env)


def _kill(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()


def _watch_and_restart(
    project_dir: Path,
    entrypoint: Path,
    extra_env: dict[str, str] | None = None,
) -> None:
    app_process = _start_app(entrypoint, extra_env)
    mtimes = _get_py_mtimes(project_dir)

    try:
        while True:
            if app_process.poll() is not None:
                break
            time.sleep(0.5)
            new_mtimes = _get_py_mtimes(project_dir)
            if new_mtimes != mtimes:
                mtimes = new_mtimes
                print("\nPython files changed, reloading...")
                _kill(app_process)
                app_process = _start_app(entrypoint, extra_env)
    except KeyboardInterrupt:
        pass
    finally:
        _kill(app_process)


def start_vite(project_dir: Path, pm: str = "npm") -> tuple[subprocess.Popen, int]:
    pm_path = ensure_pm(pm)
    check_node_modules(project_dir, pm)

    process = subprocess.Popen(
        [pm_path, "run", "dev"],
        cwd=project_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )

    found_port: int | None = None
    port_event = threading.Event()

    def stream_output() -> None:
        nonlocal found_port

        assert process.stdout is not None

        for line in process.stdout:
            try:
                sys.stdout.write(line)
                sys.stdout.flush()
            except Exception:
                pass

            if found_port is None:
                match = re.search(r"localhost:(\d+)", _strip_ansi(line))

                if match:
                    found_port = int(match.group(1))
                    port_event.set()

    threading.Thread(target=stream_output, daemon=True).start()

    if not port_event.wait(timeout=30):
        process.kill()
        print("Vite dev server did not start within 30 seconds.")
        raise SystemExit(1)

    assert found_port is not None
    return process, found_port


def wait_for_server(port: int, *, timeout: int = 15) -> None:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"http://localhost:{port}", timeout=1)
            return
        except Exception:
            time.sleep(0.2)

    print(f"Dev server at localhost:{port} did not respond.")
    raise SystemExit(1)


def _find_entrypoint_or_exit(project_dir: Path) -> Path:
    entrypoint = find_entrypoint(project_dir)

    if entrypoint is None:
        print("Could not find a Vesper app entrypoint.")
        print("")
        print("Expected one of:")

        for name in APP_ENTRYPOINTS:
            print(f"  - {name}")

        raise SystemExit(1)

    return entrypoint


def run_vanilla_dev(project_dir: Path) -> None:
    entrypoint = _find_entrypoint_or_exit(project_dir)
    print(f"Running Vesper app: {entrypoint.name}")
    _watch_and_restart(project_dir, entrypoint)


def run_framework_dev(project_dir: Path, pm: str = "npm") -> None:
    entrypoint = _find_entrypoint_or_exit(project_dir)

    vite_process, port = start_vite(project_dir, pm)

    print(f"Connecting to dev server at http://localhost:{port} ...")
    wait_for_server(port)
    print(f"Running Vesper app: {entrypoint.name}")

    extra_env = {"VESPER_DEV_URL": f"http://localhost:{port}"}

    try:
        _watch_and_restart(project_dir, entrypoint, extra_env)
    finally:
        _kill(vite_process)


def dev() -> None:
    project_dir = Path.cwd()
    config = read_vesper_toml(project_dir)
    template = config.get("template", "vanilla")
    pm = get_project_package_manager(project_dir)

    if template in FRAMEWORK_TEMPLATES:
        run_framework_dev(project_dir, pm)
    else:
        run_vanilla_dev(project_dir)


def add_dev_parser(subparsers: argparse._SubParsersAction) -> None:
    subparsers.add_parser(
        "dev",
        help="Start the Vesper app in development mode.",
    )


def handle_dev(args: argparse.Namespace) -> bool:
    if args.command == "dev":
        dev()
        return True

    return False
