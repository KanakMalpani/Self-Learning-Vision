from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.core.async_db import async_database_url
from app.services.job_backend import InlineJobBackend, build_job_backend
from app.services.model_assets import insightface_health
from app.services.vector_store import (
    LocalJsonVectorStore,
    PgVectorStore,
    VectorStoreUnavailable,
    build_vector_store,
)


def test_async_database_url_uses_async_driver_for_postgres() -> None:
    assert (
        async_database_url("postgresql://postgres:postgres@db:5432/self_learning_vision")
        == "postgresql+asyncpg://postgres:postgres@db:5432/self_learning_vision"
    )
    assert async_database_url("postgresql+asyncpg://db/app") == "postgresql+asyncpg://db/app"


def test_insightface_health_reports_missing_optional_dependencies(tmp_path: Path) -> None:
    health = insightface_health(str(tmp_path))

    assert health.provider_id == "insightface"
    if not all(health.optional_dependencies.values()):
        assert health.ready is False
        assert health.status == "optional_dependency_missing"


def test_local_vector_store_upsert_search_delete_and_redaction(tmp_path: Path) -> None:
    store = LocalJsonVectorStore(tmp_path / "vectors.json")

    store.upsert(
        vector_id="v1",
        entity_id="person-1",
        domain_type="person",
        vector=[1, 0, 0],
        metadata={"source": "test", "file_path": "/private/photo.jpg"},
    )
    store.upsert(
        vector_id="v2",
        entity_id="person-2",
        domain_type="person",
        vector=[0.9, 0.1, 0],
        metadata={"source": "test"},
    )
    store.upsert(vector_id="v3", entity_id="object-1", domain_type="object", vector=[0, 1, 0])

    results = store.search(vector=[1, 0, 0], domain_type="person", limit=2)

    assert [item.record.vector_id for item in results] == ["v1", "v2"]
    assert "file_path" not in results[0].record.metadata
    assert len(store.list_for_entity("person-1")) == 1
    assert store.delete(entity_id="person-1") == 1
    assert store.list_for_entity("person-1") == []


def test_vector_store_factory_defaults_to_local_json(tmp_path: Path) -> None:
    store = build_vector_store(store_kind="local_json", storage_dir=str(tmp_path), user_id="u1")

    record = store.upsert(vector_id="v1", entity_id="e1", domain_type="custom", vector=[1, 2, 3])

    assert record.entity_id == "e1"
    assert (tmp_path / "vector-store" / "u1" / "vectors.json").exists()


def test_pgvector_store_is_optional_when_dependency_missing() -> None:
    if importlib.util.find_spec("pgvector") is not None:
        pytest.skip("pgvector is installed in this environment")

    with pytest.raises(VectorStoreUnavailable):
        PgVectorStore("postgresql://postgres:postgres@localhost:5432/self_learning_vision")


def test_inline_job_backend_runs_handlers_and_redacts_payload() -> None:
    backend = InlineJobBackend({"learning.replay": lambda payload: {"entity_id": payload["entity_id"]}})

    job = backend.enqueue(
        "learning.replay",
        {"entity_id": "entity-1", "upload_path": "/private/upload.jpg", "embedding": [1, 2, 3]},
    )

    assert job.status == "succeeded"
    assert job.result == {"entity_id": "entity-1"}
    assert "upload_path" not in job.payload
    assert "embedding" not in job.payload
    assert backend.get_status(job.job_id) == job


def test_job_backend_factory_defaults_to_inline() -> None:
    backend = build_job_backend("inline")

    job = backend.run_inline("unknown.task", {"safe": True})

    assert job.status == "succeeded"
    assert job.result == {"queued_inline": True}

