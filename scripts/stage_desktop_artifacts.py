from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path


PLATFORMS = ("windows-x64", "macos-x64", "macos-arm64", "linux-x64")


def require_single(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern))
    if len(matches) != 1:
        raise SystemExit(
            f"Expected one artifact matching {directory / pattern}, found {len(matches)}."
        )
    return matches[0]


def copy_artifact(source: Path, target: Path) -> None:
    if not source.is_file():
        raise SystemExit(f"Expected artifact not found: {source}")
    shutil.copy2(source, target)
    print(f"Staged release artifact: {target}")


def stage_windows(
    repo_root: Path, release_dir: Path, output_dir: Path, version: str
) -> None:
    installer = require_single(release_dir / "bundle" / "nsis", "*.exe")
    setup_target = (
        output_dir / f"Self-Learning-Vision-v{version}-windows-x64-setup.exe"
    )
    copy_artifact(installer, setup_target)

    application = release_dir / "self-learning-vision.exe"
    sidecar = (
        repo_root
        / "apps"
        / "api"
        / "dist"
        / "slv-api-sidecar-x86_64-pc-windows-msvc.exe"
    )
    notice = repo_root / "apps" / "desktop" / "packaging" / "WINDOWS_PORTABLE_README.txt"
    for required in (application, sidecar, notice):
        if not required.is_file():
            raise SystemExit(f"Expected portable component not found: {required}")

    archive_target = (
        output_dir / f"Self-Learning-Vision-v{version}-windows-x64-portable.zip"
    )
    folder = f"Self-Learning-Vision-v{version}-windows-x64-portable"
    with zipfile.ZipFile(archive_target, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(application, f"{folder}/Self-Learning Vision.exe")
        archive.write(sidecar, f"{folder}/{sidecar.name}")
        archive.write(notice, f"{folder}/README.txt")
    print(f"Staged release artifact: {archive_target}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage public desktop release artifacts with stable filenames."
    )
    parser.add_argument("--platform", required=True, choices=PLATFORMS)
    parser.add_argument("--version")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    desktop_root = repo_root / "apps" / "desktop"
    release_dir = desktop_root / "src-tauri" / "target" / "release"
    config = json.loads((desktop_root / "src-tauri" / "tauri.conf.json").read_text())
    version = args.version or config["version"]
    output_dir = args.output_dir or repo_root / "artifacts" / "desktop"
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.platform == "windows-x64":
        stage_windows(repo_root, release_dir, output_dir, version)
    elif args.platform in ("macos-x64", "macos-arm64"):
        source = require_single(release_dir / "bundle" / "dmg", "*.dmg")
        copy_artifact(
            source,
            output_dir / f"Self-Learning-Vision-v{version}-{args.platform}.dmg",
        )
    else:
        appimage = require_single(release_dir / "bundle" / "appimage", "*.AppImage")
        deb = require_single(release_dir / "bundle" / "deb", "*.deb")
        copy_artifact(
            appimage,
            output_dir / f"Self-Learning-Vision-v{version}-linux-x64.AppImage",
        )
        copy_artifact(
            deb,
            output_dir / f"Self-Learning-Vision-v{version}-linux-x64.deb",
        )


if __name__ == "__main__":
    main()
