from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "smoke_desktop_sidecar.py"
SPEC = importlib.util.spec_from_file_location("smoke_desktop_sidecar", SCRIPT)
assert SPEC and SPEC.loader
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def safe_readiness(app_data: Path) -> dict[str, object]:
    return {
        "status": "ok",
        "dependencies": dict(smoke.EXPECTED_DEPENDENCIES),
        "optional_features": {
            "embedding_provider": "local",
            "vector_store": "local_json",
            "job_backend": "inline",
        },
        "diagnostics": {
            "desktop_mode": True,
            "desktop_app_data_dir": str(app_data),
            "database_url": "sqlite",
            "privacy_allow_hosted_providers": False,
        },
    }


class DesktopSidecarSmokeTests(unittest.TestCase):
    def test_sidecar_path_uses_native_tauri_suffix(self) -> None:
        root = Path("repo")
        self.assertEqual(
            smoke.sidecar_path(root, "windows-x64").name,
            "slv-api-sidecar-x86_64-pc-windows-msvc.exe",
        )
        self.assertEqual(
            smoke.sidecar_path(root, "macos-arm64").name,
            "slv-api-sidecar-aarch64-apple-darwin",
        )

    def test_safe_desktop_readiness_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app_data = Path(temp)
            smoke.validate_readiness(safe_readiness(app_data), app_data)

    def test_hosted_provider_or_non_local_mode_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app_data = Path(temp)
            payload = safe_readiness(app_data)
            payload["diagnostics"]["privacy_allow_hosted_providers"] = True
            with self.assertRaises(smoke.SmokeValidationError):
                smoke.validate_readiness(payload, app_data)

            payload = safe_readiness(app_data)
            payload["optional_features"]["job_backend"] = "celery"
            with self.assertRaises(smoke.SmokeValidationError):
                smoke.validate_readiness(payload, app_data)

    def test_diagnostic_tail_redacts_temp_paths_and_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app_data = Path(temp)
            output = app_data / "output.log"
            output.write_text(
                f"open {app_data / 'private.db'} token=abc123", encoding="utf-8"
            )

            tail = smoke.diagnostic_tail(output, app_data)

            self.assertNotIn(str(app_data), tail)
            self.assertNotIn("abc123", tail)
            self.assertIn("<smoke-app-data>", tail)


if __name__ == "__main__":
    unittest.main()
