from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


TARGET_TRIPLES = {
    "windows-x64": ("x86_64-pc-windows-msvc", ".exe"),
    "macos-x64": ("x86_64-apple-darwin", ""),
    "macos-arm64": ("aarch64-apple-darwin", ""),
    "linux-x64": ("x86_64-unknown-linux-gnu", ""),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the desktop API sidecar for Tauri.")
    parser.add_argument("--target", required=True, choices=sorted(TARGET_TRIPLES))
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    api_root = repo_root / "apps" / "api"
    spec = api_root / "packaging" / "self_learning_vision_api.spec"
    dist = api_root / "dist"
    build = api_root / "build"

    shutil.rmtree(dist, ignore_errors=True)
    shutil.rmtree(build, ignore_errors=True)

    subprocess.run(
        [args.python, "-m", "PyInstaller", "--clean", "--noconfirm", str(spec)],
        cwd=api_root,
        check=True,
    )

    triple, suffix = TARGET_TRIPLES[args.target]
    source = dist / f"slv-api-sidecar{'.exe' if args.target == 'windows-x64' else ''}"
    target = dist / f"slv-api-sidecar-{triple}{suffix}"
    if not source.exists():
        raise SystemExit(f"Expected PyInstaller output not found: {source}")
    shutil.copy2(source, target)
    print(f"Prepared Tauri sidecar: {target}")


if __name__ == "__main__":
    main()
