from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

JobHandler = Callable[[dict[str, object]], dict[str, object]]


@dataclass
class JobRecord:
    job_id: str
    task_name: str
    queue: str = "default"
    status: str = "queued"
    payload: dict[str, object] = field(default_factory=dict)
    result: dict[str, object] | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class JobBackend(ABC):
    @abstractmethod
    def enqueue(
        self,
        task_name: str,
        payload: dict[str, object] | None = None,
        *,
        queue: str = "default",
    ) -> JobRecord:
        raise NotImplementedError

    @abstractmethod
    def run_inline(self, task_name: str, payload: dict[str, object] | None = None) -> JobRecord:
        raise NotImplementedError

    @abstractmethod
    def get_status(self, job_id: str) -> JobRecord | None:
        raise NotImplementedError


class InlineJobBackend(JobBackend):
    def __init__(self, handlers: dict[str, JobHandler] | None = None) -> None:
        self.handlers = handlers or {}
        self.jobs: dict[str, JobRecord] = {}

    def enqueue(
        self,
        task_name: str,
        payload: dict[str, object] | None = None,
        *,
        queue: str = "default",
    ) -> JobRecord:
        return self.run_inline(task_name, payload or {})

    def run_inline(self, task_name: str, payload: dict[str, object] | None = None) -> JobRecord:
        job = JobRecord(
            job_id=str(uuid4()),
            task_name=task_name,
            queue="inline",
            status="running",
            payload=_redact_payload(payload or {}),
        )
        self.jobs[job.job_id] = job
        try:
            handler = self.handlers.get(task_name)
            job.result = handler(payload or {}) if handler else {"queued_inline": True}
            job.status = "succeeded"
        except Exception as exc:
            job.error = str(exc)
            job.status = "failed"
        job.updated_at = datetime.now(UTC).isoformat()
        return job

    def get_status(self, job_id: str) -> JobRecord | None:
        return self.jobs.get(job_id)


def build_job_backend(kind: str, *, handlers: dict[str, JobHandler] | None = None) -> JobBackend:
    requested = (kind or "inline").strip().lower()
    if requested not in {"", "inline"}:
        raise ValueError(f"Unsupported job backend: {requested}. This app runs jobs inline.")
    return InlineJobBackend(handlers)


def _redact_payload(payload: dict[str, object]) -> dict[str, object]:
    blocked = {
        "path",
        "file_path",
        "source_image_path",
        "upload_path",
        "raw_image",
        "embedding",
        "vector",
    }
    return {str(key): value for key, value in payload.items() if str(key).lower() not in blocked}
