"""
Native installers on top of an existing `vesper package` bundle.

Only the two the OS can build with tools it already ships: `.dmg` via hdiutil on
macOS and `.deb` via dpkg-deb on Debian/Ubuntu. Windows installers need NSIS or
WiX — external, non-pip tooling — so the core does not drive them; the flag
explains what is missing and points at docs/recipes/windows-installer.md, and
`vesper doctor` reports whether NSIS is present as an optional capability.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from vesper.commands.utils import read_vesper_toml_section


# ─── Metadata ────────────────────────────────────────────────────────────────


def installer_metadata(project_dir: Path, app_name: str) -> dict[str, str]:
    """The [installer] section of vesper.toml, with sensible defaults."""
    cfg = read_vesper_toml_section(project_dir, "installer")
    return {
        "name": app_name,
        "version": cfg.get("version", "0.1.0"),
        "description": cfg.get("description", f"{app_name} (built with Vesper)"),
        "maintainer": cfg.get("maintainer", "Unknown <unknown@example.invalid>"),
        "category": cfg.get("category", "Utility"),
        "icon": cfg.get("icon", ""),
    }


def deb_package_name(app_name: str) -> str:
    """A Debian-legal package name: lowercase, dashes, no leading junk."""
    name = app_name.lower().replace(" ", "-").replace("_", "-")
    # Debian policy allows only ASCII [a-z0-9-+.]; Python's isalnum() would let
    # accented letters through.
    name = "".join(c for c in name if (c.isascii() and c.isalnum()) or c in "-+.")
    return name.strip("-.") or "vesper-app"


# ─── Pure generators (unit-testable without any packaging tool) ──────────────


def deb_control(meta: dict[str, str], arch: str) -> str:
    return (
        f"Package: {deb_package_name(meta['name'])}\n"
        f"Version: {meta['version']}\n"
        f"Architecture: {arch}\n"
        f"Maintainer: {meta['maintainer']}\n"
        f"Description: {meta['description']}\n"
    )


def desktop_entry(meta: dict[str, str]) -> str:
    pkg = deb_package_name(meta["name"])
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={meta['name']}",
        f"Exec=/usr/bin/{pkg}",
        f"Comment={meta['description']}",
        f"Categories={meta['category']};",
    ]
    if meta.get("icon"):
        lines.append(f"Icon={pkg}")
    return "\n".join(lines) + "\n"


def dmg_command(volname: str, staging: Path, output: Path) -> list[str]:
    return [
        "hdiutil", "create",
        "-volname", volname,
        "-srcfolder", str(staging),
        "-ov",
        "-format", "UDZO",
        str(output),
    ]


def deb_command(staging: Path, output: Path) -> list[str]:
    # --root-owner-group: the tree was built by a normal user, but installed
    # files must belong to root.
    return ["dpkg-deb", "--build", "--root-owner-group", str(staging), str(output)]


# ─── Builders ────────────────────────────────────────────────────────────────


def build_dmg(project_dir: Path, app_name: str, meta: dict[str, str]) -> None:
    package_dir = project_dir / "package"
    app_bundle = package_dir / f"{app_name}.app"

    if not app_bundle.is_dir():
        print(f"App bundle not found: {app_bundle}")
        print("")
        print("A .dmg is built from the .app bundle that PyInstaller's --windowed")
        print("mode produces. Run 'vesper package' with the pyinstaller bundler first.")
        raise SystemExit(1)

    if shutil.which("hdiutil") is None:
        print("hdiutil not found — it ships with macOS, so this install is damaged.")
        raise SystemExit(1)

    # Sign the .app before it goes into the image; a dmg of an unsigned app just
    # postpones the quarantine dialog to the user's machine.
    sign_cfg = read_vesper_toml_section(project_dir, "sign")
    if sign_cfg.get("identity"):
        from vesper.commands.sign import sign_macos

        sign_macos(app_bundle, sign_cfg)

    staging = package_dir / "dmg-staging"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)

    output = package_dir / f"{app_name}-{meta['version']}.dmg"
    try:
        shutil.copytree(app_bundle, staging / app_bundle.name, symlinks=True)
        # The drag-to-install convention: the volume shows the app next to a
        # link to /Applications.
        (staging / "Applications").symlink_to("/Applications")

        output.unlink(missing_ok=True)
        print(f"Creating {output.name} ...")
        result = subprocess.run(
            dmg_command(app_name, staging, output), capture_output=True, check=False
        )
        if result.returncode != 0:
            print("hdiutil failed:")
            print(result.stderr.decode(errors="replace"))
            raise SystemExit(result.returncode)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    print(f"Installer created: {output}")


def _deb_architecture() -> str:
    result = subprocess.run(
        ["dpkg", "--print-architecture"], capture_output=True, text=True, check=False
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return "amd64"


def build_deb(project_dir: Path, app_name: str, meta: dict[str, str]) -> None:
    package_dir = project_dir / "package"
    binary = package_dir / app_name

    if not binary.is_file():
        print(f"Packaged binary not found: {binary}")
        print("Run 'vesper package' first.")
        raise SystemExit(1)

    if shutil.which("dpkg-deb") is None:
        print("dpkg-deb not found.")
        print("")
        print(".deb installers can only be built where dpkg exists — Debian, Ubuntu,")
        print("and derivatives. On other distributions, distribute the raw binary from")
        print("package/, or build on a Debian machine or container.")
        raise SystemExit(1)

    pkg = deb_package_name(app_name)
    arch = _deb_architecture()
    staging = package_dir / "deb-staging" / f"{pkg}_{meta['version']}_{arch}"
    shutil.rmtree(staging.parent, ignore_errors=True)

    output = package_dir / f"{pkg}_{meta['version']}_{arch}.deb"
    try:
        (staging / "DEBIAN").mkdir(parents=True)
        (staging / "DEBIAN" / "control").write_text(deb_control(meta, arch), encoding="utf-8")

        bin_dir = staging / "usr" / "bin"
        bin_dir.mkdir(parents=True)
        shutil.copy2(binary, bin_dir / pkg)
        (bin_dir / pkg).chmod(0o755)

        apps_dir = staging / "usr" / "share" / "applications"
        apps_dir.mkdir(parents=True)
        (apps_dir / f"{pkg}.desktop").write_text(desktop_entry(meta), encoding="utf-8")

        icon = meta.get("icon", "")
        if icon and (project_dir / icon).is_file():
            icon_dir = staging / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"
            icon_dir.mkdir(parents=True)
            shutil.copy2(project_dir / icon, icon_dir / f"{pkg}.png")

        output.unlink(missing_ok=True)
        print(f"Creating {output.name} ...")
        result = subprocess.run(
            deb_command(staging, output), capture_output=True, check=False
        )
        if result.returncode != 0:
            print("dpkg-deb failed:")
            print(result.stderr.decode(errors="replace"))
            raise SystemExit(result.returncode)
    finally:
        shutil.rmtree(staging.parent, ignore_errors=True)

    print(f"Installer created: {output}")
    print(f"Install with:   sudo apt install ./{output.name}")
    print(f"Uninstall with: sudo apt remove {pkg}")


def explain_windows_installer() -> None:
    """Windows installers are out of the core — say why and where to go."""
    print("Vesper does not build Windows installers directly.")
    print("")
    print("An .exe installer needs NSIS (or WiX) — external tooling that pip cannot")
    print("install, which places it outside the zero-dependency core.")
    if shutil.which("makensis"):
        print("")
        print("NSIS is installed on this machine. A ready-to-adapt .nsi script for a")
        print("Vesper bundle lives in docs/recipes/windows-installer.md.")
    else:
        print("")
        print("Install NSIS from https://nsis.sourceforge.io (or: winget install NSIS),")
        print("then follow docs/recipes/windows-installer.md for a ready-to-adapt script.")
    raise SystemExit(1)


def build_installer(project_dir: Path, app_name: str) -> None:
    meta = installer_metadata(project_dir, app_name)

    if sys.platform == "darwin":
        build_dmg(project_dir, app_name, meta)
    elif sys.platform == "win32":
        explain_windows_installer()
    else:
        build_deb(project_dir, app_name, meta)
