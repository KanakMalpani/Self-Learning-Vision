from __future__ import annotations

from statistics import mean
from typing import Any

from app.services.correction_log_registry import CorrectionLogRecord
from app.services.learning_signal_registry import LearningSignalRecord
from app.services.memory_entity_registry import MemoryEntityRecord


def build_evidence_bundles(
    *,
    entity: MemoryEntityRecord,
    corrections: list[CorrectionLogRecord],
    active_learning_questions: list[object],
    learning_signals: list[LearningSignalRecord],
) -> list[dict[str, Any]]:
    bundles: list[dict[str, Any]] = []
    if entity.observations:
        confidences = [item.confidence for item in entity.observations if item.confidence is not None]
        bundles.append(
            {
                "bundle_id": f"observations:{entity.entity_id}",
                "title": "Observation Evidence",
                "summary": f"{len(entity.observations)} observation(s) support this memory",
                "source": "memory_observations",
                "event_count": len(entity.observations),
                "confidence_delta": round(mean(confidences), 6) if confidences else 0.0,
                "risk_level": "low",
                "created_at": _latest([item.observed_at for item in entity.observations]),
                "items": [
                    {
                        "label": item.source,
                        "detail": item.notes or item.modality,
                        "confidence": item.confidence,
                        "created_at": item.observed_at,
                    }
                    for item in entity.observations[-8:]
                ],
            }
        )

    if entity.lifecycle_events:
        bundles.append(
            {
                "bundle_id": f"lifecycle:{entity.entity_id}",
                "title": "Lifecycle Evidence",
                "summary": f"{len(entity.lifecycle_events)} lifecycle event(s) changed confidence or state",
                "source": "memory_lifecycle",
                "event_count": len(entity.lifecycle_events),
                "confidence_delta": round(
                    sum(item.confidence_after - item.confidence_before for item in entity.lifecycle_events),
                    6,
                ),
                "risk_level": "medium"
                if any(item.event_type in {"contradiction", "not_this"} for item in entity.lifecycle_events)
                else "low",
                "created_at": _latest([item.created_at for item in entity.lifecycle_events]),
                "items": [
                    {
                        "label": item.event_type,
                        "detail": item.reason or f"{item.from_state} to {item.to_state}",
                        "confidence": item.confidence_after,
                        "created_at": item.created_at,
                    }
                    for item in entity.lifecycle_events[-8:]
                ],
            }
        )

    related_corrections = [item for item in corrections if item.target_entity_id == entity.entity_id and not item.undone]
    if related_corrections:
        bundles.append(
            {
                "bundle_id": f"corrections:{entity.entity_id}",
                "title": "Correction Evidence",
                "summary": f"{len(related_corrections)} correction(s) changed this memory",
                "source": "corrections",
                "event_count": len(related_corrections),
                "confidence_delta": 0.0,
                "risk_level": "high"
                if any(item.operation_type in {"not_this", "split"} for item in related_corrections)
                else "medium",
                "created_at": _latest([item.created_at for item in related_corrections]),
                "items": [
                    {
                        "label": item.operation_type,
                        "detail": item.summary,
                        "confidence": None,
                        "created_at": item.created_at,
                    }
                    for item in related_corrections[-8:]
                ],
            }
        )

    related_questions = [
        item
        for item in active_learning_questions
        if getattr(item, "context", {}).get("entity_id") == entity.entity_id
        or str(getattr(item, "candidate_label", "") or "").strip().lower() == entity.label.strip().lower()
    ]
    answered = [item for item in related_questions if getattr(item, "status", "") in {"answered", "dismissed"}]
    if answered:
        bundles.append(
            {
                "bundle_id": f"feedback:{entity.entity_id}",
                "title": "User Feedback Evidence",
                "summary": f"{len(answered)} active-learning response(s) are linked to this memory",
                "source": "active_learning",
                "event_count": len(answered),
                "confidence_delta": 0.0,
                "risk_level": "medium"
                if any(getattr(getattr(item, "response", None), "action", "") == "reject" for item in answered)
                else "low",
                "created_at": _latest([getattr(item, "updated_at", "") for item in answered]),
                "items": [
                    {
                        "label": getattr(item, "question_type", "question"),
                        "detail": getattr(item, "prompt", ""),
                        "confidence": getattr(item, "confidence", None),
                        "created_at": getattr(item, "updated_at", ""),
                    }
                    for item in answered[-8:]
                ],
            }
        )

    related_signals = [item for item in learning_signals if item.entity_id == entity.entity_id]
    if related_signals:
        bundles.append(
            {
                "bundle_id": f"signals:{entity.entity_id}",
                "title": "Passive Learning Signals",
                "summary": f"{len(related_signals)} passive signal(s) are attached to this memory",
                "source": "learning_signals",
                "event_count": len(related_signals),
                "confidence_delta": round(sum(item.learning_value for item in related_signals), 6),
                "risk_level": "high"
                if any(item.risk_level == "high" for item in related_signals)
                else "medium",
                "created_at": _latest([item.created_at for item in related_signals]),
                "items": [
                    {
                        "label": item.signal_type,
                        "detail": item.summary,
                        "confidence": item.confidence,
                        "created_at": item.created_at,
                    }
                    for item in related_signals[-8:]
                ],
            }
        )

    return bundles


def _latest(values: list[str]) -> str:
    clean = [item for item in values if item]
    return max(clean) if clean else ""
