from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from vesper.commands.utils import read_vesper_toml, read_vesper_toml_section


# ─── Tool discovery ───────────────────────────────────────────────────────────


def find_signtool() -> str | None:
    """Find signtool.exe in PATH or common Windows SDK locations."""
    found = shutil.which("signtool") or shutil.which("signtool.exe")
    if found:
        return found

    for base in (
        Path("C:/Program Files (x86)/Windows Kits/10/bin"),
        Path("C:/Program Files/Windows Kits/10/bin"),
    ):
        if base.is_dir():
            for version_dir in sorted(base.iterdir(), reverse=True):
                candidate = version_dir / "x64" / "signtool.exe"
                if candidate.is_file():
                    return str(candidate)

    return None


# ─── macOS ────────────────────────────────────────────────────────────────────


def sign_macos(binary: Path, config: dict[str, str]) -> None:
    identity = config.get("identity", "")
    if not identity:
        print("Error: [sign] identity is required for macOS code signing.")
        raise SystemExit(1)

    cmd = ["codesign", "--sign", identity, "--deep", "--force", "--options", "runtime"]

    entitlements = config.get("entitlements", "")
    if entitlements:
        if not Path(entitlements).is_file():
            print(f"Error: entitlements file not found: {entitlements}")
            raise SystemExit(1)
        cmd += ["--entitlements", entitlements]

    cmd.append(str(binary))

    print(f"Signing: {binary.name}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print("codesign failed.")
        raise SystemExit(e.returncode)

    print(f"Signed:  {binary}")

    if config.get("notarize", "").lower() == "true":
        notarize_macos(binary, config)


def notarize_macos(binary: Path, config: dict[str, str]) -> None:
    apple_id = config.get("apple_id", "")
    team_id = config.get("team_id", "")
    password = os.environ.get("VESPER_NOTARIZE_PASSWORD", "")

    if not apple_id or not team_id:
        print("Error: [sign] apple_id and team_id are required for notarization.")
        raise SystemExit(1)

    if not password:
        print("Error: VESPER_NOTARIZE_PASSWORD environment variable is not set.")
        raise SystemExit(1)

    zip_path = binary.with_suffix(".zip")
    print(f"Creating archive for notarization: {zip_path.name}")
    try:
        subprocess.run(
            ["ditto", "-c", "-k", "--keepParent", str(binary), str(zip_path)],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print("ditto failed.")
        raise SystemExit(e.returncode)

    print("Submitting for notarization (this may take a few minutes)...")
    try:
        subprocess.run(
            [
                "xcrun", "notarytool", "submit", str(zip_path),
                "--apple-id", apple_id,
                "--team-id", team_id,
                "--password", password,
                "--wait",
            ],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print("Notarization failed.")
        raise SystemExit(e.returncode)
    finally:
        zip_path.unlink(missing_ok=True)

    print("Stapling notarization ticket...")
    try:
        subprocess.run(["xcrun", "stapler", "staple", str(binary)], check=True)
    except subprocess.CalledProcessError as e:
        print("stapler failed.")
        raise SystemExit(e.returncode)

    print(f"Notarized and stapled: {binary}")


# ─── Windows ──────────────────────────────────────────────────────────────────


def sign_windows(binary: Path, config: dict[str, str]) -> None:
    certificate = config.get("certificate", "")
    if not certificate:
        print("Error: [sign] certificate is required for Windows code signing.")
        raise SystemExit(1)

    cert_path = Path(certificate)
    if not cert_path.is_file():
        print(f"Error: certificate file not found: {certificate}")
        raise SystemExit(1)

    password = os.environ.get("VESPER_SIGN_PASSWORD", "")
    timestamp_url = config.get("timestamp_url", "")

    signtool = find_signtool()
    if signtool:
        sign_windows_signtool(binary, cert_path, password, timestamp_url, signtool)
        return

    osslsigncode = shutil.which("osslsigncode")
    if osslsigncode:
        sign_windows_osslsigncode(binary, cert_path, password, timestamp_url, osslsigncode)
        return

    print("Error: neither signtool nor osslsigncode found.")
    print("")
    print("Install one of the following:")
    print("  Windows SDK (includes signtool.exe): https://developer.microsoft.com/windows/downloads/windows-sdk/")
    print("  osslsigncode (cross-platform):       https://github.com/mtrojnar/osslsigncode")
    raise SystemExit(1)


def sign_windows_signtool(
    binary: Path,
    cert: Path,
    password: str,
    timestamp_url: str,
    signtool: str,
) -> None:
    cmd = [signtool, "sign", "/f", str(cert)]
    if password:
        cmd += ["/p", password]
    if timestamp_url:
        cmd += ["/t", timestamp_url]
    cmd += ["/fd", "sha256", str(binary)]

    print(f"Signing with signtool: {binary.name}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print("signtool failed.")
        raise SystemExit(e.returncode)

    print(f"Signed:  {binary}")


def sign_windows_osslsigncode(
    binary: Path,
    cert: Path,
    password: str,
    timestamp_url: str,
    osslsigncode: str,
) -> None:
    signed = binary.with_stem(binary.stem + "_signed")
    cmd = [osslsigncode, "sign", "-pkcs12", str(cert)]
    if password:
        cmd += ["-pass", password]
    if timestamp_url:
        cmd += ["-t", timestamp_url]
    cmd += ["-in", str(binary), "-out", str(signed)]

    print(f"Signing with osslsigncode: {binary.name}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print("osslsigncode failed.")
        raise SystemExit(e.returncode)

    binary.unlink()
    signed.rename(binary)
    print(f"Signed:  {binary}")


# ─── Binary resolution ────────────────────────────────────────────────────────


def find_packaged_binary(project_dir: Path, project_config: dict[str, str]) -> Path:
    app_name = project_config.get("name", project_dir.name)
    package_dir = project_dir / "package"

    if not package_dir.is_dir():
        print("package/ directory not found. Run 'vesper package' first.")
        raise SystemExit(1)

    suffix = ".exe" if sys.platform == "win32" else ""
    binary = package_dir / f"{app_name}{suffix}"

    if not binary.is_file():
        print(f"Packaged binary not found: {binary}")
        print("Run 'vesper package' first.")
        raise SystemExit(1)

    return binary


# ─── Command ──────────────────────────────────────────────────────────────────


def sign(binary_path: str | None = None) -> None:
    project_dir = Path.cwd()
    project_config = read_vesper_toml(project_dir)
    sign_config = read_vesper_toml_section(project_dir, "sign")

    if not sign_config:
        print("No [sign] section found in vesper.toml.")
        print("")
        print("Add a [sign] section to configure code signing.")
        print("See the Vesper docs for the required keys per platform.")
        raise SystemExit(1)

    if binary_path:
        binary = Path(binary_path)
        if not binary.is_file():
            print(f"Binary not found: {binary_path}")
            raise SystemExit(1)
    else:
        binary = find_packaged_binary(project_dir, project_config)

    system = platform.system()

    if system == "Darwin":
        sign_macos(binary, sign_config)
    elif system == "Windows":
        sign_windows(binary, sign_config)
    else:
        print(f"Code signing is not supported on {system}.")
        print("")
        print("Supported platforms: macOS (codesign), Windows (signtool / osslsigncode).")
        raise SystemExit(1)


# ─── CLI ─────────────────────────────────────────────────────────────────────


def add_sign_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "sign",
        help="Sign the packaged app binary for distribution.",
    )
    parser.add_argument(
        "--path",
        metavar="BINARY",
        default=None,
        help="Path to the binary to sign. Defaults to package/<name>[.exe].",
    )


def handle_sign(args: argparse.Namespace) -> bool:
    if args.command == "sign":
        sign(binary_path=getattr(args, "path", None))
        return True

    return False
