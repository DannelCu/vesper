from __future__ import annotations

import importlib.metadata
import re
import shutil
import subprocess
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


# ─── Doctor helpers ──────────────────────────────────────────────────────────


def print_check(
    ok: bool, message: str, fix: str | None = None, *, critical: bool = True
) -> None:
    """
    Print one diagnostic line, with its fix underneath when it failed.

    `critical=False` marks the line [WARN] instead of [FAIL]. Optional features are
    reported that way: a missing tray backend is not a broken install, and printing
    [FAIL] next to something the app may never use sends people chasing it.
    """
    if ok:
        icon = "[OK]"
    else:
        icon = "[FAIL]" if critical else "[WARN]"

    print(f"{icon} {message}")

    if not ok and fix:
        print(f"     Fix: {fix}")


def get_installed_version(package_name: str) -> str | None:
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None
