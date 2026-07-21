from __future__ import annotations

import importlib.metadata
import os
import re
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path


APP_ENTRYPOINTS = (
    "app.py",
    "main.py",
    "vesper_app.py",
)

FRAMEWORK_TEMPLATES = {"react", "vue", "svelte"}


# ─── Project config ──────────────────────────────────────────────────────────


def read_vesper_toml(project_dir: Path) -> dict[str, str]:
    toml_path = project_dir / "vesper.toml"

    if not toml_path.is_file():
        return {}

    result: dict[str, str] = {}

    for line in toml_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("[") or line.startswith("#"):
            continue

        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip().strip('"')

    return result


def read_vesper_toml_section(project_dir: Path, section: str) -> dict[str, str]:
    """Return key-value pairs from a specific TOML section."""
    toml_path = project_dir / "vesper.toml"

    if not toml_path.is_file():
        return {}

    result: dict[str, str] = {}
    target = f"[{section}]"
    in_section = False

    for line in toml_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        if stripped.startswith("["):
            in_section = stripped == target
            continue

        if in_section and not stripped.startswith("#") and "=" in stripped:
            key, _, value = stripped.partition("=")
            result[key.strip()] = value.strip().strip('"')

    return result


# ─── Entrypoint ──────────────────────────────────────────────────────────────


def find_entrypoint(directory: Path) -> Path | None:
    for entrypoint_name in APP_ENTRYPOINTS:
        entrypoint = directory / entrypoint_name

        if entrypoint.is_file():
            return entrypoint

    return None


# ─── SDK ─────────────────────────────────────────────────────────────────────


def copy_sdk_to_frontend(frontend_dir: Path) -> Path:
    sdk_source = files("vesper").joinpath("sdk", "vesper.js")
    sdk_destination = frontend_dir / "vesper.js"

    with sdk_source.open("rb") as source_file:
        with sdk_destination.open("wb") as destination_file:
            shutil.copyfileobj(source_file, destination_file)

    return sdk_destination


# ─── npm ─────────────────────────────────────────────────────────────────────


def ensure_npm_available() -> str:
    npm_path = shutil.which("npm")

    if npm_path is None:
        print("npm is required.")
        print("")
        print("Install Node.js and npm, then run this command again.")
        raise SystemExit(1)

    return npm_path


def find_npx(npm_path: str) -> str | None:
    npm_dir = Path(npm_path).parent

    for name in ("npx", "npx.cmd", "npx.exe"):
        candidate = npm_dir / name
        if candidate.is_file():
            return str(candidate)

    return shutil.which("npx")


def run_npm_command(project_dir: Path, *args: str) -> None:
    npm_path = ensure_npm_available()
    command = (npm_path, *args)

    try:
        subprocess.run(command, cwd=project_dir, check=True)
    except FileNotFoundError as error:
        print("Could not execute npm.")
        print("")
        print("Make sure Node.js and npm are installed and available in your PATH.")
        raise SystemExit(1) from error
    except subprocess.CalledProcessError as error:
        print(f"npm command failed: {' '.join(str(a) for a in command)}")
        raise SystemExit(error.returncode) from error


def check_node_modules(project_dir: Path, pm: str = "npm") -> None:
    if not (project_dir / "node_modules").is_dir():
        print("node_modules not found.")
        print("")
        print("Run the following first:")
        print(f"  cd {project_dir.name}")
        print(f"  {pm} install")
        raise SystemExit(1)


# ─── Package managers ────────────────────────────────────────────────────────


SUPPORTED_PACKAGE_MANAGERS = {"npm", "yarn", "pnpm"}


def validate_package_manager(pm: str) -> str:
    normalized = pm.strip().lower()

    if normalized not in SUPPORTED_PACKAGE_MANAGERS:
        print(f"Unsupported package manager: {pm}")
        print("")
        print("Available package managers:")

        for p in sorted(SUPPORTED_PACKAGE_MANAGERS):
            print(f"  - {p}")

        raise SystemExit(1)

    return normalized


def get_pm_executable(pm: str) -> str | None:
    return shutil.which(pm) or shutil.which(f"{pm}.cmd")


def ensure_pm(pm: str) -> str:
    path = get_pm_executable(pm)

    if path is None:
        print(f"{pm} not found.")
        print("")
        print(f"Install {pm} and try again.")
        raise SystemExit(1)

    return path


def pm_add(pm: str, project_dir: Path, *packages: str) -> None:
    path = ensure_pm(pm)
    cmd = [path, "install" if pm == "npm" else "add"] + list(packages)

    try:
        subprocess.run(cmd, cwd=project_dir, check=True)
    except subprocess.CalledProcessError as error:
        print(f"{pm} failed.")
        raise SystemExit(error.returncode) from error


def pm_add_dev(pm: str, project_dir: Path, *packages: str) -> None:
    path = ensure_pm(pm)
    subcmd = "install" if pm == "npm" else "add"
    flag = "-D" if pm in {"npm", "pnpm"} else "--dev"
    cmd = [path, subcmd, flag] + list(packages)

    try:
        subprocess.run(cmd, cwd=project_dir, check=True)
    except subprocess.CalledProcessError as error:
        print(f"{pm} failed.")
        raise SystemExit(error.returncode) from error


def pm_run(pm: str, project_dir: Path, script: str) -> None:
    path = ensure_pm(pm)

    try:
        subprocess.run([path, "run", script], cwd=project_dir, check=True)
    except subprocess.CalledProcessError as error:
        print(f"{pm} run {script} failed.")
        raise SystemExit(error.returncode) from error


def pm_dlx(pm: str, project_dir: Path, tool: str, *args: str) -> bool:
    path = get_pm_executable(pm)

    if path is None:
        return False

    if pm == "npm":
        npx = find_npx(path)
        cmd = ([npx, "--yes", tool] + list(args)) if npx else ([path, "exec", "--", tool] + list(args))
    else:
        cmd = [path, "dlx", tool] + list(args)

    try:
        subprocess.run(cmd, cwd=project_dir, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def detect_package_manager(project_dir: Path) -> str:
    if (project_dir / "pnpm-lock.yaml").is_file():
        return "pnpm"
    if (project_dir / "yarn.lock").is_file():
        return "yarn"
    return "npm"


def get_project_package_manager(project_dir: Path) -> str:
    config = read_vesper_toml(project_dir)
    pm = config.get("package_manager", "")

    if pm in SUPPORTED_PACKAGE_MANAGERS:
        return pm

    return detect_package_manager(project_dir)


# ─── Colour ──────────────────────────────────────────────────────────────────
#
# Raw ANSI, no dependency. Colour is decoration: every code path here must be able
# to produce the same text without it, because the output is piped into files and
# CI logs at least as often as it is read on a terminal.

_RESET = "\x1b[0m"
_GREEN = "\x1b[32m"
_YELLOW = "\x1b[33m"
_RED = "\x1b[31m"
_DIM = "\x1b[2m"

# Check states. FAIL is reserved for what actually breaks the app; an optional
# backend that is merely absent is WARN, and something the platform cannot do at all
# is NA — there is nothing to install, so telling the user to fix it is noise.
OK = "ok"
WARN = "warn"
FAIL = "fail"
NA = "na"

_STATUS_STYLE = {
    OK: ("[OK]", _GREEN),
    WARN: ("[WARN]", _YELLOW),
    FAIL: ("[FAIL]", _RED),
    NA: ("[N/A]", _DIM),
}


def _enable_windows_vt() -> bool:
    """
    Ask the Windows console to interpret ANSI escapes.

    Windows 10 understands them but does not enable it by default for every console
    host. Without this the codes would be printed literally, which is worse than no
    colour at all — hence the caller treats a failure here as "no colour".
    """
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-11)          # STD_OUTPUT_HANDLE
    if handle in (0, -1):
        return False

    mode = ctypes.c_uint32()
    if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        return False

    # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))


def supports_color() -> bool:
    """
    Whether it is safe to emit ANSI escapes on stdout right now.

    Not cached: tests redirect stdout, and the cost is an isatty() call.
    """
    # NO_COLOR is honoured by presence, not value — https://no-color.org
    if "NO_COLOR" in os.environ:
        return False

    try:
        if not sys.stdout.isatty():
            return False
    except (AttributeError, ValueError):
        # A replaced or closed stdout. Assume the worst and stay plain.
        return False

    if sys.platform == "win32":
        try:
            return _enable_windows_vt()
        except Exception:
            return False

    return True


def colorize(text: str, color: str) -> str:
    """Wrap text in an ANSI colour, or return it unchanged when colour is off."""
    if not color or not supports_color():
        return text
    return f"{color}{text}{_RESET}"


# ─── Doctor helpers ──────────────────────────────────────────────────────────


def print_check(
    ok: bool,
    message: str,
    fix: str | None = None,
    *,
    critical: bool = True,
    status: str | None = None,
) -> None:
    """
    Print one diagnostic line, with its fix underneath when there is one.

    The state is derived from `ok` and `critical` unless `status` names it outright:

        ok=True                      → [OK]    green
        ok=False, critical=True      → [FAIL]  red     (breaks the app)
        ok=False, critical=False     → [WARN]  yellow  (optional, installable)
        status=NA                    → [N/A]   dim     (platform cannot do it)

    NA never prints a fix. It means there is nothing to install — printing "Fix:"
    beside it would send someone looking for a package that does not exist.
    """
    if status is None:
        status = OK if ok else (FAIL if critical else WARN)

    icon, color = _STATUS_STYLE.get(status, _STATUS_STYLE[FAIL])
    print(f"{colorize(icon, color)} {message}")

    if fix and status in (FAIL, WARN):
        print(f"     Fix: {fix}")


def get_installed_version(package_name: str) -> str | None:
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None
