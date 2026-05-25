from __future__ import annotations

import argparse
import hashlib
import json
import re
import tomllib
import zipfile
from pathlib import Path, PurePosixPath


PLATFORMS = ("windows-x64", "macos-x64", "macos-arm64", "linux-x64")
BLOCKED_SUFFIXES = {".db", ".env", ".log", ".npy", ".pyc", ".sqlite", ".sqlite3"}
BLOCKED_COMPONENTS = {"logs", "models", "uploads"}
PRIVATE_TEXT_PATTERNS = (
    re.compile(r"(?i)jarvis-v1-private"),
    re.compile(r"(?i)[a-z]:\\users\\[^\\]+\\"),
    re.compile(r"(?i)(api[_-]?key|jwt[_-]?secret|password)\s*[=:]\s*[\"'][^\"']+"),
)


class ArtifactValidationError(ValueError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def configured_version(root: Path | None = None) -> str:
    root = root or repo_root()
    desktop = root / "apps" / "desktop"
    config_version = json.loads(
        (root / "apps" / "desktop" / "src-tauri" / "tauri.conf.json").read_text(
            encoding="utf-8"
        )
    )["version"]
    package_version = json.loads(
        (desktop / "package.json").read_text(encoding="utf-8")
    )["version"]
    cargo_version = tomllib.loads(
        (desktop / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8")
    )["package"]["version"]
    versions = {config_version, package_version, cargo_version}
    if len(versions) != 1:
        raise ArtifactValidationError(
            "Desktop package versions disagree: "
            f"tauri={config_version}, npm={package_version}, cargo={cargo_version}."
        )
    return config_version


def expected_for_platform(platform: str, version: str) -> set[str]:
    artifacts = {
        "windows-x64": {
            f"Self-Learning-Vision-v{version}-windows-x64-setup.exe",
            f"Self-Learning-Vision-v{version}-windows-x64-portable.zip",
        },
        "macos-x64": {f"Self-Learning-Vision-v{version}-macos-x64.dmg"},
        "macos-arm64": {f"Self-Learning-Vision-v{version}-macos-arm64.dmg"},
        "linux-x64": {
            f"Self-Learning-Vision-v{version}-linux-x64.AppImage",
            f"Self-Learning-Vision-v{version}-linux-x64.deb",
        },
    }
    return artifacts[platform]


def expected_release_artifacts(version: str) -> set[str]:
    expected: set[str] = set()
    for platform in PLATFORMS:
        expected.update(expected_for_platform(platform, version))
    return expected


def _validate_safe_name(name: str) -> None:
    relative = PurePosixPath(name.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ArtifactValidationError(f"Unsafe archive path: {name}")
    lowered = tuple(part.lower() for part in relative.parts)
    if any(part in BLOCKED_COMPONENTS for part in lowered):
        raise ArtifactValidationError(f"Private data directory in artifact: {name}")
    if relative.suffix.lower() in BLOCKED_SUFFIXES:
        raise ArtifactValidationError(f"Private/generated file in artifact: {name}")


def _validate_safe_text(text: str, source: str) -> None:
    for pattern in PRIVATE_TEXT_PATTERNS:
        if pattern.search(text):
            raise ArtifactValidationError(f"Potential private data in {source}")


def validate_portable_zip(path: Path, version: str) -> None:
    folder = f"Self-Learning-Vision-v{version}-windows-x64-portable"
    expected_entries = {
        f"{folder}/Self-Learning Vision.exe",
        f"{folder}/slv-api-sidecar-x86_64-pc-windows-msvc.exe",
        f"{folder}/README.txt",
    }
    with zipfile.ZipFile(path) as archive:
        entries = {entry.filename for entry in archive.infolist() if not entry.is_dir()}
        if entries != expected_entries:
            raise ArtifactValidationError(
                f"Portable ZIP contents differ from its allowlist: {sorted(entries)}"
            )
        for entry in entries:
            _validate_safe_name(entry)
        readme = archive.read(f"{folder}/README.txt").decode("utf-8", errors="replace")
        _validate_safe_text(readme, path.name)


def _directory_files(directory: Path) -> set[str]:
    if not directory.is_dir():
        raise ArtifactValidationError(f"Artifact directory does not exist: {directory}")
    return {entry.name for entry in directory.iterdir() if entry.is_file()}


def validate_platform(directory: Path, platform: str, version: str) -> None:
    expected = expected_for_platform(platform, version)
    present = _directory_files(directory)
    if present != expected:
        raise ArtifactValidationError(
            f"{platform} artifacts do not match expected names. "
            f"Expected {sorted(expected)}; found {sorted(present)}."
        )
    for name in present:
        path = directory / name
        _validate_safe_name(name)
        if path.stat().st_size == 0:
            raise ArtifactValidationError(f"Empty artifact: {name}")
        if path.suffix.lower() == ".zip":
            validate_portable_zip(path, version)


def validate_release(
    directory: Path, version: str, *, allow_checksum_file: bool = False
) -> None:
    expected = expected_release_artifacts(version)
    present = _directory_files(directory)
    allowed = expected | ({"SHA256SUMS.txt"} if allow_checksum_file else set())
    if present != expected and present != allowed:
        raise ArtifactValidationError(
            "Release artifacts are incomplete or contain unexpected files. "
            f"Expected {sorted(expected)}; found {sorted(present)}."
        )
    for platform in PLATFORMS:
        for name in expected_for_platform(platform, version):
            path = directory / name
            _validate_safe_name(name)
            if path.stat().st_size == 0:
                raise ArtifactValidationError(f"Empty artifact: {name}")
            if path.suffix.lower() == ".zip":
                validate_portable_zip(path, version)


def write_checksums(directory: Path, version: str) -> Path:
    validate_release(directory, version, allow_checksum_file=True)
    checksum_path = directory / "SHA256SUMS.txt"
    lines = []
    for name in sorted(expected_release_artifacts(version)):
        digest = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}\n")
    checksum_path.write_text("".join(lines), encoding="ascii")
    return checksum_path


def verify_tag(tag: str, version: str) -> None:
    expected = f"v{version}"
    if tag != expected:
        raise ArtifactValidationError(
            f"Release tag {tag!r} must match desktop version {expected!r}."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate desktop release artifacts.")
    parser.add_argument("--version")
    subparsers = parser.add_subparsers(dest="command", required=True)

    platform_parser = subparsers.add_parser("validate-platform")
    platform_parser.add_argument("--platform", required=True, choices=PLATFORMS)
    platform_parser.add_argument("--directory", type=Path, required=True)

    release_parser = subparsers.add_parser("validate-release")
    release_parser.add_argument("--directory", type=Path, required=True)

    checksum_parser = subparsers.add_parser("checksums")
    checksum_parser.add_argument("--directory", type=Path, required=True)

    tag_parser = subparsers.add_parser("verify-tag")
    tag_parser.add_argument("--tag", required=True)

    args = parser.parse_args()
    try:
        version = args.version or configured_version()
        if args.command == "validate-platform":
            validate_platform(args.directory, args.platform, version)
            print(f"Validated {args.platform} release artifacts.")
        elif args.command == "validate-release":
            validate_release(args.directory, version)
            print("Validated complete desktop release artifact set.")
        elif args.command == "checksums":
            target = write_checksums(args.directory, version)
            print(f"Generated checksums: {target}")
        else:
            verify_tag(args.tag, version)
            print(f"Validated release tag {args.tag}.")
    except ArtifactValidationError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
