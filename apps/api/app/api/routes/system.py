"""HTTP routes for system."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.schemas import (
    HealthResponse,
    ReadinessResponse,
)
from app.services.model_assets import provider_health
from app.services.recognition import select_embedding_provider

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
def readiness(db: Session = Depends(get_db)) -> ReadinessResponse | Response:
    storage_root = Path(settings.storage_dir)
    model_cache_root = Path(settings.model_cache_dir)
    dependencies = {
        "database": False,
        "storage_dir_writable": False,
        "model_cache_dir_writable": False,
        "local_provider_available": False,
        "privacy_local_only": settings.privacy_local_only_mode
        and not settings.privacy_allow_hosted_providers,
    }
    try:
        db.execute(text("SELECT 1"))
        dependencies["database"] = True
    except Exception:
        pass
    for key, path in (
        ("storage_dir_writable", storage_root),
        ("model_cache_dir_writable", model_cache_root),
    ):
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            dependencies[key] = True
        except Exception:
            dependencies[key] = False
    try:
        provider = select_embedding_provider("local")
        dependencies["local_provider_available"] = bool(getattr(provider, "is_ready", True))
    except Exception:
        dependencies["local_provider_available"] = False

    status = "ok" if all(dependencies.values()) else "not ready"
    health_items = provider_health(settings.model_cache_dir)
    payload = ReadinessResponse(
        status=status,
        dependencies=dependencies,
        optional_features={
            "embedding_provider": settings.embedding_provider,
            "vector_store": settings.vector_store,
            "job_backend": settings.job_backend,
            "providers": [
                {
                    "provider_id": item.provider_id,
                    "ready": item.ready,
                    "status": item.status,
                }
                for item in health_items
            ],
        },
        diagnostics={
            "desktop_mode": settings.desktop_mode,
            "desktop_app_data_dir": settings.desktop_app_data_dir,
            "database_url": (
                "sqlite" if settings.database_url.startswith("sqlite") else "configured"
            ),
            "storage_dir": str(storage_root),
            "model_cache_dir": str(model_cache_root),
            "privacy_local_only_mode": settings.privacy_local_only_mode,
            "privacy_allow_hosted_providers": settings.privacy_allow_hosted_providers,
        },
    )
    if status != "ok":
        return Response(
            content=payload.model_dump_json(), media_type="application/json", status_code=503
        )
    return payload
