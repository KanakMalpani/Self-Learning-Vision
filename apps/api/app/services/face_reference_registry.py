from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class FaceReferenceRecord:
    reference_id: str
    name_or_alias: str
    embedding: list[float]
    provider: str
    source_image_path: str | None = None
    face_index: int = 0
    notes: str | None = None
    tags: list[str] | None = None
    seen_count: int = 0
    last_seen_at: str | None = None
    created_at: str = ""


class FaceReferenceRegistry:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def list_records(self) -> list[FaceReferenceRecord]:
        payload = self._load_payload()
        records: list[FaceReferenceRecord] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            embedding = item.get("embedding")
            name = str(item.get("name_or_alias") or "").strip()
            provider = str(item.get("provider") or "local-face-embedding").strip() or "local-face-embedding"
            if not name or not isinstance(embedding, list) or not embedding:
                continue
            try:
                vector = [float(value) for value in embedding if isinstance(value, (int, float))]
            except (TypeError, ValueError):
                continue
            if not vector:
                continue
            records.append(
                FaceReferenceRecord(
                    reference_id=str(item.get("reference_id") or uuid4()),
                    name_or_alias=name,
                    embedding=vector,
                    provider=provider,
                    source_image_path=str(item.get("source_image_path") or "") or None,
                    face_index=int(item.get("face_index") or 0),
                    notes=str(item.get("notes") or "") or None,
                    tags=self._sanitize_tags(item.get("tags")),
                    seen_count=max(0, int(item.get("seen_count") or 0)),
                    last_seen_at=str(item.get("last_seen_at") or "") or None,
                    created_at=str(item.get("created_at") or "") or datetime.now(UTC).isoformat(),
                )
            )
        return records

    def add_reference(
        self,
        *,
        name_or_alias: str,
        embedding: list[float],
        provider: str,
        source_image_path: str | None = None,
        face_index: int = 0,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> FaceReferenceRecord:
        with self._lock:
            record = FaceReferenceRecord(
                reference_id=str(uuid4()),
                name_or_alias=name_or_alias.strip(),
                embedding=[float(value) for value in embedding],
                provider=provider,
                source_image_path=source_image_path,
                face_index=max(0, int(face_index)),
                notes=notes.strip() if notes else None,
                tags=self._sanitize_tags(tags),
                seen_count=0,
                last_seen_at=None,
                created_at=datetime.now(UTC).isoformat(),
            )
            records = self.list_records()
            records.append(record)
            self._save_payload([asdict(item) for item in records])
            return record

    def mark_seen(self, *, name_or_alias: str) -> FaceReferenceRecord | None:
        with self._lock:
            payload = self._load_payload()
            needle = name_or_alias.strip().lower()
            if not needle:
                return None

            now_iso = datetime.now(UTC).isoformat()
            changed = False
            for item in payload:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name_or_alias") or "").strip().lower()
                if name != needle:
                    continue
                item["seen_count"] = max(0, int(item.get("seen_count") or 0)) + 1
                item["last_seen_at"] = now_iso
                changed = True
                break

            if not changed:
                return None

            self._save_payload(payload)
            for record in self.list_records():
                if record.name_or_alias.strip().lower() == needle:
                    return record
            return None

    def find_by_name(self, *, name_or_alias: str) -> FaceReferenceRecord | None:
        needle = name_or_alias.strip().lower()
        if not needle:
            return None
        for record in self.list_records():
            if record.name_or_alias.strip().lower() == needle:
                return record
        return None

    def reference_embeddings_json(self) -> str:
        records = self.list_records()
        payload = [
            {
                "name_or_alias": record.name_or_alias,
                "embedding": record.embedding,
            }
            for record in records
        ]
        return json.dumps(payload)

    def provider_name(self) -> str | None:
        records = self.list_records()
        if not records:
            return None
        return records[0].provider

    def reference_count(self) -> int:
        return len(self.list_records())

    def has_references(self) -> bool:
        return self.reference_count() > 0

    def _load_payload(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if isinstance(payload, list):
            return payload
        return []

    def _save_payload(self, payload: list[dict[str, Any]]) -> None:
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(self.path)

    def _sanitize_tags(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        seen: set[str] = set()
        tags: list[str] = []
        for item in value:
            tag = str(item or "").strip()
            if not tag:
                continue
            lowered = tag.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            tags.append(tag)
        return tags

