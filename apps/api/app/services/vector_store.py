from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from math import sqrt
from pathlib import Path
from typing import Any


class VectorStoreUnavailable(RuntimeError):
    pass


@dataclass
class VectorRecord:
    vector_id: str
    entity_id: str
    domain_type: str
    vector: list[float]
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(frozen=True)
class VectorSearchResult:
    record: VectorRecord
    score: float


class VectorStore(ABC):
    @abstractmethod
    def upsert(
        self,
        *,
        vector_id: str,
        entity_id: str,
        domain_type: str,
        vector: list[float],
        metadata: dict[str, object] | None = None,
    ) -> VectorRecord:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        *,
        vector: list[float],
        domain_type: str | None = None,
        limit: int = 5,
        min_score: float | None = None,
    ) -> list[VectorSearchResult]:
        raise NotImplementedError

    @abstractmethod
    def delete(self, *, vector_id: str | None = None, entity_id: str | None = None) -> int:
        raise NotImplementedError

    @abstractmethod
    def list_for_entity(self, entity_id: str) -> list[VectorRecord]:
        raise NotImplementedError


class LocalJsonVectorStore(VectorStore):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def upsert(
        self,
        *,
        vector_id: str,
        entity_id: str,
        domain_type: str,
        vector: list[float],
        metadata: dict[str, object] | None = None,
    ) -> VectorRecord:
        normalized = _normalize(vector)
        if not normalized:
            raise ValueError("vector is required")
        records = self._load()
        existing = records.get(vector_id)
        now = datetime.now(UTC).isoformat()
        record = VectorRecord(
            vector_id=vector_id,
            entity_id=entity_id,
            domain_type=_safe_label(domain_type, default="custom"),
            vector=normalized,
            metadata=_redact_metadata(metadata or {}),
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        records[vector_id] = record
        self._save(records)
        return record

    def search(
        self,
        *,
        vector: list[float],
        domain_type: str | None = None,
        limit: int = 5,
        min_score: float | None = None,
    ) -> list[VectorSearchResult]:
        query = _normalize(vector)
        if not query:
            return []
        results: list[VectorSearchResult] = []
        domain_filter = _safe_label(domain_type, default="") if domain_type else None
        for record in self._load().values():
            if domain_filter and record.domain_type != domain_filter:
                continue
            score = _cosine_similarity(query, record.vector)
            if min_score is not None and score < min_score:
                continue
            results.append(VectorSearchResult(record=record, score=round(score, 6)))
        results.sort(key=lambda item: item.score, reverse=True)
        return results[: max(1, int(limit))]

    def delete(self, *, vector_id: str | None = None, entity_id: str | None = None) -> int:
        records = self._load()
        remove_ids = [
            record_id
            for record_id, record in records.items()
            if (vector_id and record_id == vector_id) or (entity_id and record.entity_id == entity_id)
        ]
        for record_id in remove_ids:
            records.pop(record_id, None)
        if remove_ids:
            self._save(records)
        return len(remove_ids)

    def list_for_entity(self, entity_id: str) -> list[VectorRecord]:
        return [record for record in self._load().values() if record.entity_id == entity_id]

    def _load(self) -> dict[str, VectorRecord]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        records: dict[str, VectorRecord] = {}
        for item in payload if isinstance(payload, list) else []:
            if not isinstance(item, dict):
                continue
            vector_id = str(item.get("vector_id") or "").strip()
            entity_id = str(item.get("entity_id") or "").strip()
            vector = item.get("vector")
            if not vector_id or not entity_id or not isinstance(vector, list):
                continue
            records[vector_id] = VectorRecord(
                vector_id=vector_id,
                entity_id=entity_id,
                domain_type=_safe_label(item.get("domain_type"), default="custom"),
                vector=_normalize([float(value) for value in vector if isinstance(value, (int, float))]),
                metadata=_redact_metadata(item.get("metadata") if isinstance(item.get("metadata"), dict) else {}),
                created_at=str(item.get("created_at") or datetime.now(UTC).isoformat()),
                updated_at=str(item.get("updated_at") or datetime.now(UTC).isoformat()),
            )
        return records

    def _save(self, records: dict[str, VectorRecord]) -> None:
        payload = [asdict(record) for record in records.values()]
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(self.path)


class PgVectorStore(VectorStore):
    def __init__(self, database_url: str, table_name: str = "memory_vectors") -> None:
        try:
            import psycopg2
            from pgvector.psycopg2 import register_vector
        except Exception as exc:  # pragma: no cover - optional production dependency
            raise VectorStoreUnavailable("Install pgvector extras before using VECTOR_STORE=pgvector") from exc
        self.database_url = database_url
        self.table_name = table_name
        self._psycopg2 = psycopg2
        self._register_vector = register_vector
        self._ensure_schema()

    def upsert(
        self,
        *,
        vector_id: str,
        entity_id: str,
        domain_type: str,
        vector: list[float],
        metadata: dict[str, object] | None = None,
    ) -> VectorRecord:
        normalized = _normalize(vector)
        if not normalized:
            raise ValueError("vector is required")
        record = VectorRecord(
            vector_id=vector_id,
            entity_id=entity_id,
            domain_type=_safe_label(domain_type, default="custom"),
            vector=normalized,
            metadata=_redact_metadata(metadata or {}),
        )
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {self.table_name}
                    (vector_id, entity_id, domain_type, embedding, metadata, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s::jsonb, now(), now())
                ON CONFLICT (vector_id) DO UPDATE SET
                    entity_id = EXCLUDED.entity_id,
                    domain_type = EXCLUDED.domain_type,
                    embedding = EXCLUDED.embedding,
                    metadata = EXCLUDED.metadata,
                    updated_at = now()
                """,
                (
                    record.vector_id,
                    record.entity_id,
                    record.domain_type,
                    record.vector,
                    json.dumps(record.metadata),
                ),
            )
        return record

    def search(
        self,
        *,
        vector: list[float],
        domain_type: str | None = None,
        limit: int = 5,
        min_score: float | None = None,
    ) -> list[VectorSearchResult]:
        normalized = _normalize(vector)
        if not normalized:
            return []
        params: list[Any] = [normalized]
        where = ""
        if domain_type:
            where = "WHERE domain_type = %s"
            params.append(_safe_label(domain_type, default="custom"))
        params.append(max(1, int(limit)))
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT vector_id, entity_id, domain_type, embedding, metadata,
                       created_at::text, updated_at::text,
                       1 - (embedding <=> %s::vector) AS score
                FROM {self.table_name}
                {where}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                [normalized, *params[1:-1], normalized, params[-1]],
            )
            rows = cur.fetchall()
        results = []
        for row in rows:
            score = float(row[7] or 0.0)
            if min_score is not None and score < min_score:
                continue
            results.append(
                VectorSearchResult(
                    record=VectorRecord(
                        vector_id=str(row[0]),
                        entity_id=str(row[1]),
                        domain_type=str(row[2]),
                        vector=[float(value) for value in row[3]],
                        metadata=dict(row[4] or {}),
                        created_at=str(row[5]),
                        updated_at=str(row[6]),
                    ),
                    score=round(score, 6),
                )
            )
        return results

    def delete(self, *, vector_id: str | None = None, entity_id: str | None = None) -> int:
        if not vector_id and not entity_id:
            return 0
        clauses: list[str] = []
        params: list[str] = []
        if vector_id:
            clauses.append("vector_id = %s")
            params.append(vector_id)
        if entity_id:
            clauses.append("entity_id = %s")
            params.append(entity_id)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"DELETE FROM {self.table_name} WHERE {' OR '.join(clauses)}", params)
            return int(cur.rowcount or 0)

    def list_for_entity(self, entity_id: str) -> list[VectorRecord]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT vector_id, entity_id, domain_type, embedding, metadata, created_at::text, updated_at::text
                FROM {self.table_name}
                WHERE entity_id = %s
                ORDER BY updated_at DESC
                """,
                (entity_id,),
            )
            rows = cur.fetchall()
        return [
            VectorRecord(
                vector_id=str(row[0]),
                entity_id=str(row[1]),
                domain_type=str(row[2]),
                vector=[float(value) for value in row[3]],
                metadata=dict(row[4] or {}),
                created_at=str(row[5]),
                updated_at=str(row[6]),
            )
            for row in rows
        ]

    def _connect(self):
        conn = self._psycopg2.connect(self.database_url)
        self._register_vector(conn)
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    vector_id TEXT PRIMARY KEY,
                    entity_id TEXT NOT NULL,
                    domain_type TEXT NOT NULL,
                    embedding vector NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS {self.table_name}_entity_idx ON {self.table_name} (entity_id)"
            )


def build_vector_store(
    *,
    store_kind: str,
    storage_dir: str,
    user_id: str = "default",
    database_url: str = "",
) -> VectorStore:
    kind = (store_kind or "local_json").strip().lower()
    if kind == "pgvector":
        return PgVectorStore(database_url)
    path = Path(storage_dir) / "vector-store" / str(user_id) / "vectors.json"
    return LocalJsonVectorStore(path)


def _normalize(vector: list[float]) -> list[float]:
    values = [float(value) for value in vector if isinstance(value, (int, float))]
    norm = sqrt(sum(value * value for value in values))
    if norm <= 0:
        return []
    return [float(value / norm) for value in values]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dim = min(len(a), len(b))
    if dim <= 0:
        return 0.0
    return max(-1.0, min(1.0, sum(a[index] * b[index] for index in range(dim))))


def _safe_label(value: object, *, default: str) -> str:
    label = str(value or default).strip().lower().replace("-", "_")
    return label[:80] or default


def _redact_metadata(metadata: dict[str, object]) -> dict[str, object]:
    blocked = {"path", "file_path", "source_image_path", "upload_path", "raw_image", "embedding", "vector"}
    return {str(key): value for key, value in metadata.items() if str(key).lower() not in blocked}

