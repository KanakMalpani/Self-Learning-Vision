from __future__ import annotations

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "release_artifacts.py"
SPEC = importlib.util.spec_from_file_location("release_artifacts", SCRIPT)
assert SPEC and SPEC.loader
release_artifacts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_artifacts)

VERSION = "0.3.0-alpha.1"


def write_portable_zip(directory: Path, *, extra: str | None = None) -> None:
    folder = f"Self-Learning-Vision-v{VERSION}-windows-x64-portable"
    target = directory / f"Self-Learning-Vision-v{VERSION}-windows-x64-portable.zip"
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr(f"{folder}/Self-Learning Vision.exe", b"desktop")
        archive.writestr(
            f"{folder}/slv-api-sidecar-x86_64-pc-windows-msvc.exe", b"sidecar"
        )
        archive.writestr(f"{folder}/README.txt", "Unsigned local-only alpha.")
        if extra:
            archive.writestr(f"{folder}/{extra}", b"blocked")


def create_complete_release(directory: Path) -> None:
    for name in release_artifacts.expected_release_artifacts(VERSION):
        if not name.endswith(".zip"):
            (directory / name).write_bytes(b"artifact")
    write_portable_zip(directory)


class ReleaseArtifactTests(unittest.TestCase):
    def test_windows_platform_requires_exact_allowlisted_portable_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / f"Self-Learning-Vision-v{VERSION}-windows-x64-setup.exe").write_bytes(
                b"setup"
            )
            write_portable_zip(directory)
            release_artifacts.validate_platform(directory, "windows-x64", VERSION)

            write_portable_zip(directory, extra="private.sqlite")
            with self.assertRaises(release_artifacts.ArtifactValidationError):
                release_artifacts.validate_platform(directory, "windows-x64", VERSION)

    def test_complete_release_generates_flat_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            create_complete_release(directory)

            checksum_path = release_artifacts.write_checksums(directory, VERSION)
            release_artifacts.write_checksums(directory, VERSION)
            lines = checksum_path.read_text(encoding="ascii").splitlines()

            self.assertEqual(len(lines), 6)
            self.assertTrue(all("/" not in line.split("  ", 1)[1] for line in lines))
            self.assertTrue(
                any(line.endswith(f"Self-Learning-Vision-v{VERSION}-macos-arm64.dmg") for line in lines)
            )

    def test_release_tag_must_match_packaged_version(self) -> None:
        release_artifacts.verify_tag(f"v{VERSION}", VERSION)
        with self.assertRaises(release_artifacts.ArtifactValidationError):
            release_artifacts.verify_tag("v0.3.0-alpha.2", VERSION)

    def test_desktop_metadata_versions_must_agree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            desktop = root / "apps" / "desktop"
            tauri = desktop / "src-tauri"
            tauri.mkdir(parents=True)
            (tauri / "tauri.conf.json").write_text(
                '{"version": "0.3.0-alpha.1"}', encoding="utf-8"
            )
            (desktop / "package.json").write_text(
                '{"version": "0.3.0-alpha.1"}', encoding="utf-8"
            )
            (tauri / "Cargo.toml").write_text(
                '[package]\nversion = "0.3.0-alpha.2"\n', encoding="utf-8"
            )

            with self.assertRaises(release_artifacts.ArtifactValidationError):
                release_artifacts.configured_version(root)


if __name__ == "__main__":
    unittest.main()
