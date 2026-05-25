from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from desktop_launcher import (
    add_desktop_shutdown_route,
    attach_desktop_streams,
    configure_desktop_environment,
)


def test_desktop_launcher_sets_local_only_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "DESKTOP_MODE",
        "DESKTOP_APP_DATA_DIR",
        "DATABASE_URL",
        "STORAGE_DIR",
        "MODEL_CACHE_DIR",
        "VECTOR_STORE",
        "JOB_BACKEND",
        "AUTH_ENABLED",
        "PRIVACY_LOCAL_ONLY_MODE",
        "PRIVACY_ALLOW_HOSTED_PROVIDERS",
        "EMBEDDING_PROVIDER",
    ):
        monkeypatch.delenv(key, raising=False)

    app_data = configure_desktop_environment(tmp_path / "Self-Learning Vision", host="127.0.0.1")

    assert app_data.exists()
    assert (app_data / "uploads").exists()
    assert (app_data / "models").exists()
    assert os.environ["DESKTOP_MODE"] == "true"
    assert os.environ["DATABASE_URL"].startswith("sqlite:///")
    assert os.environ["DATABASE_URL"].endswith("self_learning_vision.db")
    assert os.environ["STORAGE_DIR"] == str(app_data / "uploads")
    assert os.environ["MODEL_CACHE_DIR"] == str(app_data / "models")
    assert os.environ["VECTOR_STORE"] == "local_json"
    assert os.environ["JOB_BACKEND"] == "inline"
    assert os.environ["AUTH_ENABLED"] == "false"
    assert os.environ["PRIVACY_LOCAL_ONLY_MODE"] == "true"
    assert os.environ["PRIVACY_ALLOW_HOSTED_PROVIDERS"] == "false"
    assert os.environ["EMBEDDING_PROVIDER"] == "local"


def test_desktop_launcher_rejects_lan_binding(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        configure_desktop_environment(tmp_path, host="0.0.0.0")


def test_desktop_logs_rotate_and_redact_local_sensitive_values(tmp_path: Path) -> None:
    app_data = tmp_path / "Self-Learning Vision"
    stream = attach_desktop_streams(app_data, max_bytes=72, backups=2)
    try:
        stream.write(f"upload={app_data / 'uploads' / 'private-face.png'} token=abc123\n")
        stream.write("second diagnostic line that causes bounded rotation safely\n")
        stream.flush()
    finally:
        stream.close()

    logs = sorted((app_data / "logs").glob("sidecar.log*"))
    content = "".join(path.read_text(encoding="utf-8") for path in logs)
    assert len(logs) <= 3
    assert all(path.stat().st_size <= 72 for path in logs)
    assert str(app_data) not in content
    assert "abc123" not in content
    assert "<app-data>" in content
    assert "token=[redacted]" in content


def test_desktop_shutdown_requires_native_token() -> None:
    stopped: list[bool] = []
    app = add_desktop_shutdown_route(
        FastAPI(),
        "native-token",
        shutdown_callback=lambda: stopped.append(True),
    )
    client = TestClient(app)

    assert client.post("/desktop/shutdown").status_code == 403
    response = client.post(
        "/desktop/shutdown",
        headers={"x-desktop-shutdown-token": "native-token"},
    )

    assert response.json() == {"status": "stopping"}
    for _ in range(10):
        if stopped:
            break
        time.sleep(0.02)
    assert stopped == [True]
