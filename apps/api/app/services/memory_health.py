from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.services.correction_log_registry import CorrectionLogRecord
from app.services.learning_signal_registry import LearningSignalRecord
from app.services.memory_entity_registry import MemoryEntityRecord


def build_memory_health(
    *,
    entity: MemoryEntityRecord,
    corrections: list[CorrectionLogRecord],
    active_learning_questions: list[object],
    learning_signals: list[LearningSignalRecord],
) -> dict[str, Any]:
    related_corrections = [item for item in corrections if item.target_entity_id == entity.entity_id and not item.undone]
    related_questions = [
        item
        for item in active_learning_questions
        if getattr(item, "context", {}).get("entity_id") == entity.entity_id
        and getattr(item, "status", "pending") == "pending"
    ]
    related_signals = [
        item
        for item in learning_signals
        if item.entity_id == entity.entity_id and item.status == "pending"
    ]
    contradiction_count = _contradiction_count(entity, related_corrections, related_signals)
    evidence_count = len(entity.observations) + len(entity.lifecycle_events) + len(related_signals)

    score = float(entity.confidence or 0.0) * 0.58
    score += min(0.18, len(entity.observations) * 0.03)
    score += min(0.12, len(entity.lifecycle_events) * 0.025)
    score += min(0.08, len([signal for signal in related_signals if signal.signal_type != "contradiction"]) * 0.02)

    if entity.lifecycle_state == "confirmed":
        score += 0.12
    elif entity.lifecycle_state == "candidate":
        score -= 0.08
    elif entity.lifecycle_state == "uncertain":
        score -= 0.18
    elif entity.lifecycle_state == "stale":
        score -= 0.12
    elif entity.lifecycle_state in {"archived", "forgotten"}:
        score -= 0.35

    score -= min(0.32, contradiction_count * 0.12)
    score -= min(0.18, len(related_questions) * 0.04)
    score -= _freshness_penalty(entity.updated_at)
    score = round(max(0.0, min(1.0, score)), 6)

    state = "stable"
    if score < 0.45 or contradiction_count > 0 or entity.lifecycle_state == "uncertain":
        state = "needs_review"
    elif score < 0.72 or entity.lifecycle_state in {"candidate", "stale"} or related_questions:
        state = "watch"

    reasons = _health_reasons(
        entity=entity,
        contradiction_count=contradiction_count,
        pending_questions=len(related_questions),
        evidence_count=evidence_count,
        stale_penalty=_freshness_penalty(entity.updated_at),
    )

    return {
        "entity_id": entity.entity_id,
        "score": score,
        "state": state,
        "reasons": reasons,
        "confidence": entity.confidence,
        "observation_count": len(entity.observations),
        "evidence_count": evidence_count,
        "contradiction_count": contradiction_count,
        "correction_count": len(related_corrections),
        "pending_question_count": len(related_questions),
        "last_updated_at": entity.updated_at,
    }


def build_memory_health_distribution(
    *,
    entities: list[MemoryEntityRecord],
    corrections: list[CorrectionLogRecord],
    active_learning_questions: list[object],
    learning_signals: list[LearningSignalRecord],
) -> dict[str, int]:
    distribution = {"stable": 0, "watch": 0, "needs_review": 0}
    for entity in entities:
        health = build_memory_health(
            entity=entity,
            corrections=corrections,
            active_learning_questions=active_learning_questions,
            learning_signals=learning_signals,
        )
        distribution[health["state"]] = distribution.get(health["state"], 0) + 1
    return distribution


def _contradiction_count(
    entity: MemoryEntityRecord,
    corrections: list[CorrectionLogRecord],
    signals: list[LearningSignalRecord],
) -> int:
    contradictions = entity.attributes.get("contradictions")
    count = len(contradictions) if isinstance(contradictions, list) else 0
    count += len([item for item in corrections if item.operation_type in {"not_this", "split"}])
    count += len([item for item in signals if item.signal_type == "contradiction"])
    return count


def _health_reasons(
    *,
    entity: MemoryEntityRecord,
    contradiction_count: int,
    pending_questions: int,
    evidence_count: int,
    stale_penalty: float,
) -> list[str]:
    reasons = []
    if entity.lifecycle_state in {"candidate", "uncertain", "stale"}:
        reasons.append(f"lifecycle state is {entity.lifecycle_state}")
    if contradiction_count:
        reasons.append(f"{contradiction_count} contradiction signal(s)")
    if pending_questions:
        reasons.append(f"{pending_questions} pending review question(s)")
    if evidence_count <= 1:
        reasons.append("limited evidence")
    if stale_penalty:
        reasons.append("memory has not been refreshed recently")
    if not reasons:
        reasons.append("evidence is consistent")
    return reasons


def _freshness_penalty(updated_at: str) -> float:
    try:
        updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return 0.04
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    age_days = (datetime.now(UTC) - updated).days
    if age_days >= 90:
        return 0.12
    if age_days >= 30:
        return 0.06
    return 0.0
