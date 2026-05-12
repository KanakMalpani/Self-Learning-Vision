from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class CorrectionLogRecord:
    correction_id: str
    operation_type: str
    target_entity_id: str
    summary: str
    before_entities: list[dict[str, Any]] = field(default_factory=list)
    after_entities: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    undone: bool = False
    undone_at: str | None = None
    created_at: str = ""


class CorrectionLogRegistry:
    """Append-only-ish local audit log for user corrections and undo snapshots."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def list_records(self) -> list[CorrectionLogRecord]:
        records = [self._record_from_payload(item) for item in self._load_payload()]
        return [record for record in records if record is not None]

    def find(self, correction_id: str) -> CorrectionLogRecord | None:
        needle = correction_id.strip()
        if not needle:
            return None
        for record in self.list_records():
            if record.correction_id == needle:
                return record
        return None

    def add_record(
        self,
        *,
        operation_type: str,
        target_entity_id: str,
        summary: str,
        before_entities: list[dict[str, Any]],
        after_entities: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> CorrectionLogRecord:
        clean_operation = operation_type.strip()
        clean_target = target_entity_id.strip()
        clean_summary = summary.strip()
        if not clean_operation or not clean_target or not clean_summary:
            raise ValueError("Correction operation, target, and summary are required")
        with self._lock:
            records = self.list_records()
            record = CorrectionLogRecord(
                correction_id=str(uuid4()),
                operation_type=clean_operation,
                target_entity_id=clean_target,
                summary=clean_summary,
                before_entities=before_entities,
                after_entities=after_entities,
                metadata=metadata or {},
                created_at=datetime.now(UTC).isoformat(),
            )
            records.append(record)
            self._save_payload([asdict(item) for item in records])
            return record

    def mark_undone(self, correction_id: str) -> CorrectionLogRecord | None:
        with self._lock:
            records = self.list_records()
            for record in records:
                if record.correction_id != correction_id:
                    continue
                record.undone = True
                record.undone_at = datetime.now(UTC).isoformat()
                self._save_payload([asdict(item) for item in records])
                return record
        return None

    def count(self) -> int:
        return len(self.list_records())

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

    def _record_from_payload(self, item: dict[str, Any]) -> CorrectionLogRecord | None:
        if not isinstance(item, dict):
            return None
        correction_id = str(item.get("correction_id") or "").strip()
        operation_type = str(item.get("operation_type") or "").strip()
        target_entity_id = str(item.get("target_entity_id") or "").strip()
        summary = str(item.get("summary") or "").strip()
        if not correction_id or not operation_type or not target_entity_id or not summary:
            return None
        before = item.get("before_entities")
        after = item.get("after_entities")
        metadata = item.get("metadata")
        return CorrectionLogRecord(
            correction_id=correction_id,
            operation_type=operation_type,
            target_entity_id=target_entity_id,
            summary=summary,
            before_entities=before if isinstance(before, list) else [],
            after_entities=after if isinstance(after, list) else [],
            metadata=metadata if isinstance(metadata, dict) else {},
            undone=bool(item.get("undone") or False),
            undone_at=str(item.get("undone_at") or "") or None,
            created_at=str(item.get("created_at") or "") or datetime.now(UTC).isoformat(),
        )
