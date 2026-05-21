from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import uvicorn


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def configure_desktop_environment(app_data_dir: str | Path, *, host: str) -> Path:
    host = host.strip()
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Desktop sidecar may only bind to 127.0.0.1/localhost")

    app_data = Path(app_data_dir).expanduser().resolve()
    uploads = app_data / "uploads"
    models = app_data / "models"
    for path in (app_data, uploads, models):
        path.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("APP_ENV", "desktop")
    os.environ["DESKTOP_MODE"] = "true"
    os.environ["DESKTOP_APP_DATA_DIR"] = str(app_data)
    os.environ["DATABASE_URL"] = _sqlite_url(app_data / "self_learning_vision.db")
    os.environ["STORAGE_DIR"] = str(uploads)
    os.environ["MODEL_CACHE_DIR"] = str(models)
    os.environ["VECTOR_STORE"] = "local_json"
    os.environ["JOB_BACKEND"] = "inline"
    os.environ["AUTH_ENABLED"] = "false"
    os.environ["PRIVACY_LOCAL_ONLY_MODE"] = "true"
    os.environ["PRIVACY_ALLOW_HOSTED_PROVIDERS"] = "false"
    os.environ["EMBEDDING_PROVIDER"] = "local"
    os.environ["CORS_ORIGINS"] = ",".join(
        [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "tauri://localhost",
            "https://tauri.localhost",
        ]
    )
    return app_data


def attach_desktop_streams(app_data: Path):
    logs = app_data / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stream = (logs / "sidecar.log").open("a", encoding="utf-8", buffering=1)
    if sys.stdout is None or getattr(sys.stdout, "closed", False):
        sys.stdout = stream
    if sys.stderr is None or getattr(sys.stderr, "closed", False):
        sys.stderr = stream
    return stream


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Self-Learning Vision as a local desktop sidecar.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--app-data-dir", required=True)
    args = parser.parse_args()

    try:
        app_data = configure_desktop_environment(args.app_data_dir, host=args.host)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    _stream = attach_desktop_streams(app_data)
    uvicorn.run("app.main:app", host=args.host.strip(), port=args.port, log_level="info")


if __name__ == "__main__":
    main()
