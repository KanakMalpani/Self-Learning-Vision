from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


TARGET_TRIPLES = {
    "windows-x64": ("x86_64-pc-windows-msvc", ".exe"),
    "macos-x64": ("x86_64-apple-darwin", ""),
    "macos-arm64": ("aarch64-apple-darwin", ""),
    "linux-x64": ("x86_64-unknown-linux-gnu", ""),
}
EXPECTED_DEPENDENCIES = {
    "database": True,
    "storage_dir_writable": True,
    "model_cache_dir_writable": True,
    "local_provider_available": True,
    "privacy_local_only": True,
}


class SmokeValidationError(RuntimeError):
    pass


def sidecar_path(repo_root: Path, target: str) -> Path:
    triple, suffix = TARGET_TRIPLES[target]
    return repo_root / "apps" / "api" / "dist" / f"slv-api-sidecar-{triple}{suffix}"


def free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def validate_readiness(payload: dict[str, Any], app_data: Path) -> None:
    if payload.get("status") != "ok":
        raise SmokeValidationError(f"Sidecar readiness status was {payload.get('status')!r}.")
    dependencies = payload.get("dependencies", {})
    for key, expected in EXPECTED_DEPENDENCIES.items():
        if dependencies.get(key) is not expected:
            raise SmokeValidationError(f"Readiness dependency {key!r} is not safely enabled.")
    optional = payload.get("optional_features", {})
    expected_modes = {
        "embedding_provider": "local",
        "vector_store": "local_json",
        "job_backend": "inline",
    }
    for key, expected in expected_modes.items():
        if optional.get(key) != expected:
            raise SmokeValidationError(f"Desktop {key!r} must be {expected!r}.")
    diagnostics = payload.get("diagnostics", {})
    if diagnostics.get("desktop_mode") is not True:
        raise SmokeValidationError("Sidecar did not report desktop mode.")
    if diagnostics.get("privacy_allow_hosted_providers") is not False:
        raise SmokeValidationError("Desktop sidecar enabled hosted providers.")
    if diagnostics.get("database_url") != "sqlite":
        raise SmokeValidationError("Desktop sidecar is not using SQLite.")
    reported_dir = Path(str(diagnostics.get("desktop_app_data_dir", ""))).resolve()
    if reported_dir != app_data.resolve():
        raise SmokeValidationError("Sidecar did not use its disposable app-data directory.")


def http_json(url: str, *, token: str | None = None) -> tuple[int, dict[str, Any]]:
    headers = {"x-desktop-shutdown-token": token} if token else {}
    method = "POST" if token is not None else "GET"
    request = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def wait_for_readiness(base_url: str, app_data: Path, timeout_seconds: float) -> None:
    expires = time.monotonic() + timeout_seconds
    last_error = "sidecar did not answer"
    while time.monotonic() < expires:
        try:
            status, payload = http_json(f"{base_url}/ready")
            if status == 200:
                validate_readiness(payload, app_data)
                return
            last_error = f"/ready returned HTTP {status}"
        except (OSError, ValueError, SmokeValidationError) as exc:
            last_error = str(exc)
        time.sleep(0.25)
    raise SmokeValidationError(f"Sidecar readiness failed: {last_error}.")


def terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass


def diagnostic_tail(path: Path, app_data: Path) -> str:
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8", errors="replace")[-2000:]
    content = content.replace(str(app_data), "<smoke-app-data>")
    content = re.sub(
        r"(?i)(token|api[_-]?key|secret)=([^&\s]+)",
        r"\1=[redacted]",
        content,
    )
    return content.strip()


def run_smoke(binary: Path, *, timeout_seconds: float = 20.0) -> None:
    if not binary.is_file():
        raise SmokeValidationError(f"Frozen sidecar binary not found: {binary}")
    port = free_loopback_port()
    token = secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory(prefix="slv-desktop-sidecar-smoke-") as temp:
        app_data = Path(temp)
        output_path = app_data / "sidecar-output.log"
        command = [
            str(binary),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--app-data-dir",
            str(app_data),
            "--shutdown-token",
            token,
        ]
        with output_path.open("wb") as output:
            kwargs: dict[str, Any] = {"stdout": output, "stderr": subprocess.STDOUT}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            else:
                kwargs["start_new_session"] = True
            process = subprocess.Popen(command, **kwargs)
            base_url = f"http://127.0.0.1:{port}"
            try:
                wait_for_readiness(base_url, app_data, timeout_seconds)
                status, _ = http_json(f"{base_url}/desktop/shutdown", token="wrong-token")
                if status != 403:
                    raise SmokeValidationError("Desktop shutdown accepted an invalid token.")
                status, payload = http_json(f"{base_url}/desktop/shutdown", token=token)
                if status != 200 or payload.get("status") != "stopping":
                    raise SmokeValidationError("Desktop shutdown did not accept its native token.")
                try:
                    process.wait(timeout=timeout_seconds)
                except subprocess.TimeoutExpired as exc:
                    raise SmokeValidationError("Frozen sidecar did not stop cleanly.") from exc
                try:
                    urllib.request.urlopen(f"{base_url}/ready", timeout=1)
                except OSError:
                    pass
                else:
                    raise SmokeValidationError("Sidecar was still listening after shutdown.")
            except SmokeValidationError as exc:
                output.flush()
                tail = diagnostic_tail(output_path, app_data)
                detail = f" Sidecar output tail: {tail}" if tail else ""
                raise SmokeValidationError(f"{exc}{detail}") from exc
            finally:
                terminate_process_tree(process)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smoke-test the frozen desktop API sidecar on the native runner."
    )
    parser.add_argument("--target", required=True, choices=sorted(TARGET_TRIPLES))
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    args = parser.parse_args()

    binary = args.binary or sidecar_path(Path(__file__).resolve().parents[1], args.target)
    try:
        run_smoke(binary, timeout_seconds=args.timeout_seconds)
    except SmokeValidationError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Native frozen-sidecar smoke test passed for {args.target}.")


if __name__ == "__main__":
    main()
