from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4


SignalStatus = Literal["pending", "resolved", "dismissed"]

SENSITIVE_METADATA_KEYS = {
    "api_key",
    "authorization",
    "centroid",
    "centroid_embedding",
    "embedding",
    "embeddings",
    "file_path",
    "image",
    "image_path",
    "password",
    "private_key",
    "raw_image",
    "secret",
    "source_image_path",
    "token",
    "upload_path",
    "vector",
}


@dataclass
class LearningSignalRecord:
    signal_id: str
    signal_type: str
    source: str
    summary: str
    dedupe_key: str
    domain_type: str = "custom"
    entity_id: str | None = None
    question_id: str | None = None
    source_id: str | None = None
    status: SignalStatus = "pending"
    confidence: float = 0.0
    learning_value: float = 0.0
    risk_level: str = "medium"
    evidence: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    resolution: str | None = None
    created_at: str = ""
    updated_at: str = ""
    resolved_at: str | None = None


class LearningSignalRegistry:
    """Local, redacted queue of passive learning signals.

    Signals intentionally store metadata only. Raw images, embeddings, upload
    paths, and provider secrets are filtered out at the registry boundary.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def list_signals(
        self,
        *,
        status: str | None = None,
        entity_id: str | None = None,
        signal_type: str | None = None,
    ) -> list[LearningSignalRecord]:
        records = [self._record_from_payload(item) for item in self._load_payload()]
        clean = [record for record in records if record is not None]
        if status:
            normalized_status = self._normalize_status(status)
            clean = [record for record in clean if record.status == normalized_status]
        if entity_id:
            clean = [record for record in clean if record.entity_id == entity_id]
        if signal_type:
            normalized_type = self._normalize_type(signal_type)
            clean = [record for record in clean if record.signal_type == normalized_type]
        return sorted(
            clean,
            key=lambda item: (
                item.status != "pending",
                -item.learning_value,
                _sortable_time(item.created_at),
            ),
        )

    def pending_count(self) -> int:
        return len(self.list_signals(status="pending"))

    def find(self, signal_id: str) -> LearningSignalRecord | None:
        needle = signal_id.strip()
        if not needle:
            return None
        for record in self.list_signals():
            if record.signal_id == needle:
                return record
        return None

    def upsert_signal(
        self,
        *,
        signal_type: str,
        source: str,
        summary: str,
        dedupe_key: str,
        domain_type: str = "custom",
        entity_id: str | None = None,
        question_id: str | None = None,
        source_id: str | None = None,
        confidence: float = 0.0,
        learning_value: float = 0.0,
        risk_level: str = "medium",
        evidence: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LearningSignalRecord:
        clean_summary = summary.strip()
        clean_dedupe_key = dedupe_key.strip()
        if not clean_summary:
            raise ValueError("Learning signal summary is required")
        if not clean_dedupe_key:
            raise ValueError("Learning signal dedupe key is required")

        with self._lock:
            records = [self._record_from_payload(item) for item in self._load_payload()]
            records = [record for record in records if record is not None]
            now_iso = datetime.now(UTC).isoformat()
            for record in records:
                if record.dedupe_key != clean_dedupe_key:
                    continue
                if record.status == "pending":
                    record.summary = clean_summary
                    record.confidence = self._clamp(confidence)
                    record.learning_value = self._clamp(learning_value)
                    record.risk_level = self._normalize_risk(risk_level)
                    record.evidence = self._merge_lists(record.evidence, evidence)
                    record.metadata = {
                        **record.metadata,
                        **self._sanitize_mapping(metadata),
                    }
                    record.updated_at = now_iso
                    self._save_payload([asdict(item) for item in records])
                return record

            record = LearningSignalRecord(
                signal_id=str(uuid4()),
                signal_type=self._normalize_type(signal_type),
                source=self._normalize_type(source),
                summary=clean_summary,
                dedupe_key=clean_dedupe_key,
                domain_type=self._normalize_type(domain_type),
                entity_id=entity_id.strip() if entity_id else None,
                question_id=question_id.strip() if question_id else None,
                source_id=source_id.strip() if source_id else None,
                status="pending",
                confidence=self._clamp(confidence),
                learning_value=self._clamp(learning_value),
                risk_level=self._normalize_risk(risk_level),
                evidence=self._sanitize_list(evidence),
                metadata=self._sanitize_mapping(metadata),
                created_at=now_iso,
                updated_at=now_iso,
            )
            records.append(record)
            self._save_payload([asdict(item) for item in records])
            return record

    def resolve_signal(self, signal_id: str, *, resolution: str | None = None) -> LearningSignalRecord | None:
        return self._set_status(signal_id, status="resolved", resolution=resolution)

    def dismiss_signal(self, signal_id: str, *, resolution: str | None = None) -> LearningSignalRecord | None:
        return self._set_status(signal_id, status="dismissed", resolution=resolution or "Dismissed by user")

    def resolve_many(self, signal_ids: list[str], *, resolution: str | None = None) -> list[LearningSignalRecord]:
        resolved = []
        for signal_id in signal_ids:
            record = self.resolve_signal(signal_id, resolution=resolution)
            if record is not None:
                resolved.append(record)
        return resolved

    def snapshot(self) -> list[dict[str, Any]]:
        return [asdict(record) for record in self.list_signals()]

    def _set_status(
        self,
        signal_id: str,
        *,
        status: SignalStatus,
        resolution: str | None = None,
    ) -> LearningSignalRecord | None:
        needle = signal_id.strip()
        if not needle:
            return None
        with self._lock:
            records = [self._record_from_payload(item) for item in self._load_payload()]
            records = [record for record in records if record is not None]
            now_iso = datetime.now(UTC).isoformat()
            updated = None
            for record in records:
                if record.signal_id != needle:
                    continue
                record.status = status
                record.resolution = resolution.strip() if resolution else None
                record.resolved_at = now_iso
                record.updated_at = now_iso
                updated = record
                break
            if updated is None:
                return None
            self._save_payload([asdict(item) for item in records])
            return updated

    def _load_payload(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return payload if isinstance(payload, list) else []

    def _save_payload(self, payload: list[dict[str, Any]]) -> None:
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(self.path)

    def _record_from_payload(self, item: dict[str, Any]) -> LearningSignalRecord | None:
        if not isinstance(item, dict):
            return None
        summary = str(item.get("summary") or "").strip()
        dedupe_key = str(item.get("dedupe_key") or "").strip()
        if not summary or not dedupe_key:
            return None
        now_iso = datetime.now(UTC).isoformat()
        return LearningSignalRecord(
            signal_id=str(item.get("signal_id") or uuid4()),
            signal_type=self._normalize_type(str(item.get("signal_type") or "learning_signal")),
            source=self._normalize_type(str(item.get("source") or "system")),
            summary=summary,
            dedupe_key=dedupe_key,
            domain_type=self._normalize_type(str(item.get("domain_type") or "custom")),
            entity_id=str(item.get("entity_id") or "") or None,
            question_id=str(item.get("question_id") or "") or None,
            source_id=str(item.get("source_id") or "") or None,
            status=self._normalize_status(str(item.get("status") or "pending")),
            confidence=self._clamp(item.get("confidence") or 0.0),
            learning_value=self._clamp(item.get("learning_value") or 0.0),
            risk_level=self._normalize_risk(str(item.get("risk_level") or "medium")),
            evidence=self._sanitize_list(item.get("evidence")),
            metadata=self._sanitize_mapping(item.get("metadata")),
            resolution=str(item.get("resolution") or "") or None,
            created_at=str(item.get("created_at") or "") or now_iso,
            updated_at=str(item.get("updated_at") or "") or now_iso,
            resolved_at=str(item.get("resolved_at") or "") or None,
        )

    def _sanitize_mapping(self, value: object) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        clean: dict[str, Any] = {}
        for key, item in value.items():
            clean_key = str(key or "").strip()
            if not clean_key:
                continue
            if clean_key.lower() in SENSITIVE_METADATA_KEYS:
                continue
            clean[clean_key] = self._sanitize_value(item)
        return clean

    def _sanitize_value(self, value: object) -> Any:
        if isinstance(value, dict):
            return self._sanitize_mapping(value)
        if isinstance(value, list):
            return [self._sanitize_value(item) for item in value[:25]]
        if isinstance(value, (str, int, float, bool)) or value is None:
            if isinstance(value, str):
                return value[:500]
            return value
        return str(value)[:500]

    def _sanitize_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return self._merge_lists([], [str(item) for item in value])

    def _merge_lists(self, existing: list[str], incoming: list[str] | None) -> list[str]:
        seen: set[str] = set()
        clean: list[str] = []
        for item in [*existing, *(incoming or [])]:
            text = str(item or "").strip()
            if not text:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            clean.append(text[:500])
        return clean

    def _normalize_status(self, value: str) -> SignalStatus:
        normalized = value.strip().lower()
        return normalized if normalized in {"pending", "resolved", "dismissed"} else "pending"  # type: ignore[return-value]

    def _normalize_risk(self, value: str) -> str:
        normalized = value.strip().lower()
        return normalized if normalized in {"low", "medium", "high"} else "medium"

    def _normalize_type(self, value: str) -> str:
        normalized = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value.lower())
        normalized = normalized.strip("_-")
        return normalized or "custom"

    def _clamp(self, value: object) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.0
        return round(max(0.0, min(1.0, number)), 6)


def _sortable_time(value: str) -> str:
    return value or ""
