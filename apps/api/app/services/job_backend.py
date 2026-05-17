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


class CeleryJobBackend(JobBackend):
    def __init__(self, celery_app) -> None:
        if celery_app is None:
            raise RuntimeError("Install celery extras before using JOB_BACKEND=celery")
        self.celery_app = celery_app

    def enqueue(
        self,
        task_name: str,
        payload: dict[str, object] | None = None,
        *,
        queue: str = "default",
    ) -> JobRecord:
        task = self.celery_app.send_task(task_name, args=[_redact_payload(payload or {})], queue=queue)
        return JobRecord(
            job_id=str(task.id),
            task_name=task_name,
            queue=queue,
            status="queued",
            payload=_redact_payload(payload or {}),
        )

    def run_inline(self, task_name: str, payload: dict[str, object] | None = None) -> JobRecord:
        return self.enqueue(task_name, payload or {}, queue="inline")

    def get_status(self, job_id: str) -> JobRecord | None:
        result = self.celery_app.AsyncResult(job_id)
        return JobRecord(
            job_id=job_id,
            task_name="unknown",
            status=str(result.status).lower(),
            result=result.result if isinstance(result.result, dict) else None,
            error=str(result.result) if result.failed() else None,
        )


def build_job_backend(kind: str, *, handlers: dict[str, JobHandler] | None = None) -> JobBackend:
    if (kind or "inline").strip().lower() == "celery":
        from app.core.celery_app import celery_app

        return CeleryJobBackend(celery_app)
    return InlineJobBackend(handlers)


def _redact_payload(payload: dict[str, object]) -> dict[str, object]:
    blocked = {"path", "file_path", "source_image_path", "upload_path", "raw_image", "embedding", "vector"}
    return {str(key): value for key, value in payload.items() if str(key).lower() not in blocked}

