from __future__ import annotations

import argparse
import http.server
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

from vesper.core.static_server import make_static_handler

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

_RELOAD_SCRIPT = b"""\
<script>
(function(){var v=null;setInterval(function(){fetch('/__vesper_dev')\
.then(function(r){return r.json();})\
.then(function(d){if(v===null){v=d.version;return;}if(d.version!==v){location.reload();}})\
.catch(function(){});},500);})();
</script>"""


# ─── File watchers ────────────────────────────────────────────────────────────


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


def _get_frontend_mtimes(frontend_dir: Path) -> dict[Path, float]:
    mtimes: dict[Path, float] = {}
    for p in frontend_dir.rglob("*"):
        if p.suffix in {".html", ".css", ".js"} and p.is_file():
            try:
                mtimes[p] = p.stat().st_mtime
            except OSError:
                pass
    return mtimes


# ─── Vanilla dev server ───────────────────────────────────────────────────────


def _make_dev_handler(frontend_dir: Path, version: list[int]) -> type:
    # The serving/confinement logic lives in core.static_server, shared with the
    # production localhost mode; this only adds what is dev-specific — the version
    # endpoint the reload poller hits and the script injection itself.
    def _inject_reload(content: bytes) -> bytes:
        return content.replace(b"</body>", _RELOAD_SCRIPT + b"</body>", 1)

    return make_static_handler(
        frontend_dir,
        html_postprocess=_inject_reload,
        routes={"/__vesper_dev": lambda: {"version": version[0]}},
    )


def _start_dev_server(frontend_dir: Path) -> tuple[http.server.HTTPServer, list[int]]:
    version: list[int] = [0]
    # Threaded for the same reason as the production server (see
    # core.static_server.start): one idle connection — which WebKit opens as a
    # matter of course — parks a single-threaded server inside readline() forever,
    # so serve_forever never sees the shutdown request and `vesper dev` hangs on
    # exit instead of returning to the shell.
    server = http.server.ThreadingHTTPServer(
        ("localhost", 0), _make_dev_handler(frontend_dir, version)
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, version


# ─── Process helpers ──────────────────────────────────────────────────────────


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
    *,
    frontend_dir: Path | None = None,
    on_frontend_change: Callable[[], None] | None = None,
) -> None:
    app_process = _start_app(entrypoint, extra_env)
    py_mtimes = _get_py_mtimes(project_dir)
    fe_mtimes = _get_frontend_mtimes(frontend_dir) if frontend_dir else {}

    try:
        while True:
            if app_process.poll() is not None:
                break
            time.sleep(0.5)

            new_py_mtimes = _get_py_mtimes(project_dir)
            if new_py_mtimes != py_mtimes:
                py_mtimes = new_py_mtimes
                print("\nPython files changed, reloading...")
                _kill(app_process)
                app_process = _start_app(entrypoint, extra_env)

            if frontend_dir is not None and on_frontend_change is not None:
                new_fe_mtimes = _get_frontend_mtimes(frontend_dir)
                if new_fe_mtimes != fe_mtimes:
                    fe_mtimes = new_fe_mtimes
                    print("\nFrontend files changed, reloading...")
                    on_frontend_change()
    except KeyboardInterrupt:
        pass
    finally:
        _kill(app_process)


# ─── Vite helpers ─────────────────────────────────────────────────────────────


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


# ─── Dev modes ────────────────────────────────────────────────────────────────


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


def run_vanilla_dev(project_dir: Path, *, devtools: bool = True) -> None:
    entrypoint = _find_entrypoint_or_exit(project_dir)
    frontend_dir = project_dir / "frontend"

    server, version = _start_dev_server(frontend_dir)
    port = server.server_address[1]

    print(f"Running Vesper app: {entrypoint.name}")

    extra_env = {"VESPER_DEV_URL": f"http://localhost:{port}"}
    if devtools:
        extra_env["VESPER_DEVTOOLS"] = "1"

    try:
        _watch_and_restart(
            project_dir,
            entrypoint,
            extra_env,
            frontend_dir=frontend_dir,
            on_frontend_change=lambda: version.__setitem__(0, version[0] + 1),
        )
    finally:
        server.shutdown()


def run_framework_dev(project_dir: Path, pm: str = "npm", *, devtools: bool = True) -> None:
    entrypoint = _find_entrypoint_or_exit(project_dir)

    vite_process, port = start_vite(project_dir, pm)

    print(f"Connecting to dev server at http://localhost:{port} ...")
    wait_for_server(port)
    print(f"Running Vesper app: {entrypoint.name}")

    extra_env = {"VESPER_DEV_URL": f"http://localhost:{port}"}
    if devtools:
        extra_env["VESPER_DEVTOOLS"] = "1"

    try:
        _watch_and_restart(project_dir, entrypoint, extra_env)
    finally:
        _kill(vite_process)


# ─── CLI ──────────────────────────────────────────────────────────────────────


def dev(*, devtools: bool = True) -> None:
    project_dir = Path.cwd()
    config = read_vesper_toml(project_dir)
    template = config.get("template", "vanilla")
    pm = get_project_package_manager(project_dir)

    if template in FRAMEWORK_TEMPLATES:
        run_framework_dev(project_dir, pm, devtools=devtools)
    else:
        run_vanilla_dev(project_dir, devtools=devtools)


def add_dev_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "dev",
        help="Start the Vesper app in development mode.",
    )
    parser.add_argument(
        "--no-devtools",
        action="store_true",
        help="Do not open the WebView inspector for this session.",
    )


def handle_dev(args: argparse.Namespace) -> bool:
    if args.command == "dev":
        dev(devtools=not args.no_devtools)
        return True

    return False