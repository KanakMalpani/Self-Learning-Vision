from __future__ import annotations

from typing import Any

from app.services.active_learning_registry import ActiveLearningQuestion
from app.services.correction_log_registry import CorrectionLogRecord
from app.services.learning_signal_registry import LearningSignalRecord
from app.services.memory_entity_registry import MemoryEntityRecord


def build_learning_timeline(
    *,
    entity: MemoryEntityRecord,
    corrections: list[CorrectionLogRecord],
    active_learning_questions: list[ActiveLearningQuestion],
    learning_signals: list[LearningSignalRecord],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = [
        {
            "timeline_id": f"created:{entity.entity_id}",
            "event_type": "created",
            "title": "Memory Created",
            "summary": f"{entity.label} started as a {entity.lifecycle_state} memory",
            "source": "memory_entity",
            "confidence": entity.confidence,
            "created_at": entity.created_at,
        }
    ]

    for observation in entity.observations:
        items.append(
            {
                "timeline_id": f"observation:{observation.observation_id}",
                "event_type": "observation",
                "title": "Observation Added",
                "summary": observation.notes or f"Observed from {observation.source}",
                "source": observation.source,
                "confidence": observation.confidence,
                "created_at": observation.observed_at,
            }
        )

    for event in entity.lifecycle_events:
        items.append(
            {
                "timeline_id": f"lifecycle:{event.event_id}",
                "event_type": event.event_type,
                "title": event.event_type.replace("_", " ").title(),
                "summary": event.reason or f"{event.from_state} to {event.to_state}",
                "source": "lifecycle",
                "confidence": event.confidence_after,
                "created_at": event.created_at,
            }
        )

    for correction in corrections:
        if correction.target_entity_id != entity.entity_id:
            continue
        items.append(
            {
                "timeline_id": f"correction:{correction.correction_id}",
                "event_type": correction.operation_type,
                "title": "Correction",
                "summary": correction.summary,
                "source": "correction",
                "confidence": None,
                "created_at": correction.created_at,
            }
        )

    for question in active_learning_questions:
        context = getattr(question, "context", {}) or {}
        if context.get("entity_id") != entity.entity_id:
            continue
        question_id = getattr(question, "question_id", "unknown")
        items.append(
            {
                "timeline_id": f"question:{question_id}",
                "event_type": getattr(question, "question_type", "review_memory"),
                "title": "Review Question",
                "summary": getattr(question, "prompt", "Review question"),
                "source": "active_learning",
                "confidence": getattr(question, "confidence", None),
                "created_at": getattr(question, "updated_at", ""),
            }
        )

    for signal in learning_signals:
        if signal.entity_id != entity.entity_id:
            continue
        items.append(
            {
                "timeline_id": f"signal:{signal.signal_id}",
                "event_type": signal.signal_type,
                "title": signal.signal_type.replace("_", " ").title(),
                "summary": signal.summary,
                "source": "learning_signal",
                "confidence": signal.confidence,
                "created_at": signal.updated_at,
            }
        )

    return sorted(items, key=lambda item: str(item.get("created_at") or ""), reverse=True)[:50]
