from __future__ import annotations

from typing import Any

from app.services.correction_log_registry import CorrectionLogRecord
from app.services.learning_signal_registry import LearningSignalRecord, LearningSignalRegistry
from app.services.memory_entity_registry import MemoryEntityRecord


def detect_memory_contradictions(
    *,
    entity: MemoryEntityRecord,
    all_entities: list[MemoryEntityRecord],
    corrections: list[CorrectionLogRecord],
    active_learning_questions: list[object],
    learning_signals: list[LearningSignalRecord],
) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []

    existing = entity.attributes.get("contradictions")
    if isinstance(existing, list):
        for index, item in enumerate(existing):
            if isinstance(item, dict):
                conflicts.append(
                    {
                        "conflict_id": f"stored:{entity.entity_id}:{index}",
                        "conflict_type": "stored_contradiction",
                        "summary": str(item.get("reason") or "Stored contradiction"),
                        "risk_level": "high",
                        "related_entity_id": entity.entity_id,
                    }
                )

    for correction in corrections:
        if correction.target_entity_id != entity.entity_id or correction.undone:
            continue
        if correction.operation_type in {"not_this", "split"}:
            conflicts.append(
                {
                    "conflict_id": f"correction:{correction.correction_id}",
                    "conflict_type": correction.operation_type,
                    "summary": correction.summary,
                    "risk_level": "high",
                    "related_entity_id": entity.entity_id,
                    "source_id": correction.correction_id,
                }
            )

    label_set = {entity.label.strip().lower(), *(alias.strip().lower() for alias in entity.aliases)}
    label_set = {item for item in label_set if item}
    for other in all_entities:
        if other.entity_id == entity.entity_id or other.domain_type != entity.domain_type:
            continue
        other_labels = {other.label.strip().lower(), *(alias.strip().lower() for alias in other.aliases)}
        if label_set.intersection({item for item in other_labels if item}):
            conflicts.append(
                {
                    "conflict_id": f"duplicate_label:{entity.entity_id}:{other.entity_id}",
                    "conflict_type": "duplicate_label",
                    "summary": f"'{entity.label}' overlaps with another {entity.domain_type} memory",
                    "risk_level": "medium",
                    "related_entity_id": other.entity_id,
                }
            )

    for question in active_learning_questions:
        response = getattr(question, "response", None)
        if not response or getattr(response, "action", "") != "reject":
            continue
        candidate = str(getattr(question, "candidate_label", "") or "").strip().lower()
        if candidate and candidate == entity.label.strip().lower():
            conflicts.append(
                {
                    "conflict_id": f"question_reject:{getattr(question, 'question_id', '')}",
                    "conflict_type": "rejected_candidate",
                    "summary": f"User rejected an active-learning match for {entity.label}",
                    "risk_level": "high",
                    "related_entity_id": entity.entity_id,
                    "source_id": getattr(question, "question_id", ""),
                }
            )

    for signal in learning_signals:
        if signal.entity_id == entity.entity_id and signal.signal_type == "contradiction" and signal.status == "pending":
            conflicts.append(
                {
                    "conflict_id": f"signal:{signal.signal_id}",
                    "conflict_type": "learning_signal",
                    "summary": signal.summary,
                    "risk_level": signal.risk_level,
                    "related_entity_id": entity.entity_id,
                    "source_id": signal.signal_id,
                }
            )

    return _dedupe_conflicts(conflicts)


def record_conflict_signals(
    *,
    registry: LearningSignalRegistry,
    entity: MemoryEntityRecord,
    conflicts: list[dict[str, Any]],
) -> list[LearningSignalRecord]:
    records = []
    for conflict in conflicts:
        conflict_id = str(conflict.get("conflict_id") or "").strip()
        if not conflict_id:
            continue
        records.append(
            registry.upsert_signal(
                signal_type="contradiction",
                source="contradiction_detector",
                source_id=conflict_id,
                entity_id=entity.entity_id,
                domain_type=entity.domain_type,
                summary=str(conflict.get("summary") or "Contradiction needs review"),
                dedupe_key=f"contradiction:{entity.entity_id}:{conflict_id}",
                confidence=entity.confidence,
                learning_value=0.9 if conflict.get("risk_level") == "high" else 0.7,
                risk_level=str(conflict.get("risk_level") or "medium"),
                evidence=[str(conflict.get("conflict_type") or "conflict")],
                metadata={
                    "conflict_type": conflict.get("conflict_type"),
                    "related_entity_id": conflict.get("related_entity_id"),
                },
            )
        )
    return records


def _dedupe_conflicts(conflicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    clean = []
    for conflict in conflicts:
        conflict_id = str(conflict.get("conflict_id") or "").strip()
        if not conflict_id or conflict_id in seen:
            continue
        seen.add(conflict_id)
        clean.append(conflict)
    return clean
