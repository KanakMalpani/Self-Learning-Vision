from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
import threading
from pathlib import Path
from typing import Callable, TextIO

import uvicorn
from fastapi import FastAPI, Header, HTTPException

MAX_LOG_BYTES = 1_000_000
MAX_LOG_BACKUPS = 2


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


class DesktopLogStream:
    def __init__(
        self,
        log_path: Path,
        *,
        app_data: Path,
        max_bytes: int = MAX_LOG_BYTES,
        backups: int = MAX_LOG_BACKUPS,
    ) -> None:
        self.log_path = log_path
        self.app_data = str(app_data)
        self.max_bytes = max_bytes
        self.backups = backups
        self._stream: TextIO = self.log_path.open("a", encoding="utf-8", buffering=1)

    def _sanitize(self, message: str) -> str:
        sanitized = message.replace(self.app_data, "<app-data>")
        sanitized = re.sub(
            r"(?i)(authorization:\s*bearer\s+)\S+",
            r"\1[redacted]",
            sanitized,
        )
        return re.sub(
            r"(?i)(token|api[_-]?key|secret)=([^&\s]+)",
            r"\1=[redacted]",
            sanitized,
        )

    def _rotate(self) -> None:
        self._stream.close()
        if self.backups:
            oldest = self.log_path.with_name(f"{self.log_path.name}.{self.backups}")
            oldest.unlink(missing_ok=True)
            for number in range(self.backups - 1, 0, -1):
                source = self.log_path.with_name(f"{self.log_path.name}.{number}")
                if source.exists():
                    source.replace(self.log_path.with_name(f"{self.log_path.name}.{number + 1}"))
            if self.log_path.exists():
                self.log_path.replace(self.log_path.with_name(f"{self.log_path.name}.1"))
        else:
            self.log_path.unlink(missing_ok=True)
        self._stream = self.log_path.open("a", encoding="utf-8", buffering=1)

    def write(self, message: str) -> int:
        sanitized = self._sanitize(message)
        encoded = sanitized.encode("utf-8")
        if len(encoded) > self.max_bytes:
            sanitized = encoded[-self.max_bytes :].decode("utf-8", errors="replace")
            encoded = sanitized.encode("utf-8")
        if self.log_path.exists() and self.log_path.stat().st_size + len(encoded) > self.max_bytes:
            self._rotate()
        return self._stream.write(sanitized)

    def flush(self) -> None:
        self._stream.flush()

    def close(self) -> None:
        self._stream.close()

    @property
    def closed(self) -> bool:
        return self._stream.closed

    def isatty(self) -> bool:
        return False


def attach_desktop_streams(
    app_data: Path,
    *,
    max_bytes: int = MAX_LOG_BYTES,
    backups: int = MAX_LOG_BACKUPS,
) -> DesktopLogStream:
    logs = app_data / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stream = DesktopLogStream(
        logs / "sidecar.log",
        app_data=app_data,
        max_bytes=max_bytes,
        backups=backups,
    )
    if sys.stdout is None or getattr(sys.stdout, "closed", False):
        sys.stdout = stream
    if sys.stderr is None or getattr(sys.stderr, "closed", False):
        sys.stderr = stream
    return stream


def add_desktop_shutdown_route(
    app: FastAPI,
    shutdown_token: str,
    *,
    shutdown_callback: Callable[[], None] | None = None,
) -> FastAPI:
    stop_process = shutdown_callback or (lambda: os._exit(0))

    @app.post("/desktop/shutdown", include_in_schema=False)
    def desktop_shutdown(
        x_desktop_shutdown_token: str | None = Header(default=None),
    ) -> dict[str, str]:
        if not x_desktop_shutdown_token or not secrets.compare_digest(
            x_desktop_shutdown_token, shutdown_token
        ):
            raise HTTPException(status_code=403, detail="Invalid desktop shutdown token.")
        threading.Timer(0.1, stop_process).start()
        return {"status": "stopping"}

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Self-Learning Vision as a local desktop sidecar.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--app-data-dir", required=True)
    parser.add_argument("--shutdown-token", required=True)
    args = parser.parse_args()

    try:
        app_data = configure_desktop_environment(args.app_data_dir, host=args.host)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    _stream = attach_desktop_streams(app_data)
    from app.main import app

    uvicorn.run(
        add_desktop_shutdown_route(app, args.shutdown_token),
        host=args.host.strip(),
        port=args.port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
