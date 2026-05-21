from __future__ import annotations

import os
from pathlib import Path

import pytest

from desktop_launcher import configure_desktop_environment


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
