from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.correction_log_registry import CorrectionLogRecord
from app.services.memory_entity_registry import MemoryEntityRecord


@dataclass(frozen=True)
class ConfidenceLedgerEntry:
    entry_id: str
    source: str
    event_type: str
    confidence_before: float | None
    confidence_after: float | None
    delta: float
    reason: str
    created_at: str


def build_confidence_ledger(
    *,
    entity: MemoryEntityRecord,
    corrections: list[CorrectionLogRecord],
) -> dict[str, Any]:
    entries: list[ConfidenceLedgerEntry] = [
        ConfidenceLedgerEntry(
            entry_id=f"created:{entity.entity_id}",
            source="memory_entity",
            event_type="created",
            confidence_before=None,
            confidence_after=entity.confidence,
            delta=entity.confidence,
            reason="Memory entity was created",
            created_at=entity.created_at,
        )
    ]

    for observation in entity.observations:
        if observation.confidence is None:
            continue
        entries.append(
            ConfidenceLedgerEntry(
                entry_id=f"observation:{observation.observation_id}",
                source=observation.source,
                event_type="observation",
                confidence_before=None,
                confidence_after=observation.confidence,
                delta=observation.confidence,
                reason=observation.notes or "Observation added evidence for this memory",
                created_at=observation.observed_at,
            )
        )

    for event in entity.lifecycle_events:
        entries.append(
            ConfidenceLedgerEntry(
                entry_id=f"lifecycle:{event.event_id}",
                source="lifecycle",
                event_type=event.event_type,
                confidence_before=event.confidence_before,
                confidence_after=event.confidence_after,
                delta=round(event.confidence_after - event.confidence_before, 6),
                reason=event.reason or f"Lifecycle event: {event.event_type}",
                created_at=event.created_at,
            )
        )

    for correction in corrections:
        if correction.target_entity_id != entity.entity_id:
            continue
        delta = _correction_delta(correction.operation_type)
        entries.append(
            ConfidenceLedgerEntry(
                entry_id=f"correction:{correction.correction_id}",
                source="correction",
                event_type=correction.operation_type,
                confidence_before=None,
                confidence_after=None,
                delta=delta,
                reason=correction.summary,
                created_at=correction.created_at,
            )
        )

    entries = sorted(entries, key=lambda item: item.created_at)
    return {
        "entity_id": entity.entity_id,
        "label": entity.label,
        "current_confidence": entity.confidence,
        "entries": [entry.__dict__ for entry in entries],
        "summary": {
            "positive_events": len([entry for entry in entries if entry.delta > 0]),
            "negative_events": len([entry for entry in entries if entry.delta < 0]),
            "neutral_events": len([entry for entry in entries if entry.delta == 0]),
        },
    }


def _correction_delta(operation_type: str) -> float:
    operation = operation_type.strip().lower()
    if operation in {"not_this", "split"}:
        return -0.1
    if operation in {"merge", "rename"}:
        return 0.02
    if operation in {"forget"}:
        return -0.2
    return 0.0
