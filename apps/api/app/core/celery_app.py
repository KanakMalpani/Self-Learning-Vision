from __future__ import annotations

from app.core.config import settings

try:
    from celery import Celery
except Exception:  # pragma: no cover - optional production dependency
    Celery = None


if Celery is not None:
    celery_app = Celery(
        "self_learning_vision",
        broker=settings.redis_url,
        backend=settings.redis_url,
    )
    celery_app.conf.task_default_queue = "self_learning_vision"
    celery_app.conf.task_serializer = "json"
    celery_app.conf.result_serializer = "json"
    celery_app.conf.accept_content = ["json"]
else:  # pragma: no cover - exercised through optional dependency checks
    celery_app = None

