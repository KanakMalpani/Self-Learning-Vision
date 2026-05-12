from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.active_learning_priority import ActiveLearningPriorityScorer
from app.services.active_learning_registry import ActiveLearningRegistry
from app.services.contradiction_detector import detect_memory_contradictions, record_conflict_signals
from app.services.correction_log_registry import CorrectionLogRecord
from app.services.learning_signal_registry import LearningSignalRecord, LearningSignalRegistry
from app.services.memory_entity_registry import MemoryEntityRecord, MemoryEntityRegistry
from app.services.memory_health import build_memory_health


@dataclass(frozen=True)
class LearningReplayResult:
    applied: bool
    entity: MemoryEntityRecord | None
    affected_signal_ids: list[str] = field(default_factory=list)
    queued_question_ids: list[str] = field(default_factory=list)
    suggestions: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


def build_replay_suggestions(
    *,
    entity: MemoryEntityRecord,
    conflicts: list[dict[str, Any]],
    health: dict[str, Any],
    learning_signals: list[LearningSignalRecord],
) -> list[dict[str, Any]]:
    suggestions = []
    conflict_signal_ids = [
        signal.signal_id
        for signal in learning_signals
        if signal.entity_id == entity.entity_id and signal.signal_type == "contradiction" and signal.status == "pending"
    ]
    if conflicts or conflict_signal_ids:
        suggestions.append(
            {
                "suggestion_id": f"resolve_conflicts:{entity.entity_id}",
                "title": "Resolve Conflicting Evidence",
                "summary": "Apply a small confidence penalty, mark conflict signals resolved, and queue review.",
                "action": "resolve_conflicts",
                "risk_level": "high",
                "source_signal_ids": conflict_signal_ids,
            }
        )

    pending_signal_ids = [
        signal.signal_id
        for signal in learning_signals
        if signal.entity_id == entity.entity_id and signal.status == "pending"
    ]
    if health.get("state") in {"watch", "needs_review"} and pending_signal_ids:
        suggestions.append(
            {
                "suggestion_id": f"review_health:{entity.entity_id}",
                "title": "Queue Memory Review",
                "summary": "Turn related passive signals into one focused review question.",
                "action": "queue_review",
                "risk_level": health.get("state") == "needs_review" and "high" or "medium",
                "source_signal_ids": pending_signal_ids[:8],
            }
        )

    if entity.lifecycle_state == "candidate" and health.get("score", 0.0) >= 0.7:
        suggestions.append(
            {
                "suggestion_id": f"promote_candidate:{entity.entity_id}",
                "title": "Review Candidate Promotion",
                "summary": "The candidate has enough evidence for a human trust check.",
                "action": "queue_review",
                "risk_level": "medium",
                "source_signal_ids": pending_signal_ids[:8],
            }
        )

    return suggestions


def apply_learning_replay(
    *,
    entity_id: str,
    entity_registry: MemoryEntityRegistry,
    active_learning_registry: ActiveLearningRegistry,
    signal_registry: LearningSignalRegistry,
    corrections: list[CorrectionLogRecord],
    active_learning_questions: list[object],
) -> LearningReplayResult:
    entity = entity_registry.find(entity_id)
    if entity is None:
        return LearningReplayResult(applied=False, entity=None, summary={"reason": "memory not found"})

    learning_signals = signal_registry.list_signals()
    conflicts = detect_memory_contradictions(
        entity=entity,
        all_entities=entity_registry.list_entities(),
        corrections=corrections,
        active_learning_questions=active_learning_questions,
        learning_signals=learning_signals,
    )
    conflict_signals = record_conflict_signals(
        registry=signal_registry,
        entity=entity,
        conflicts=conflicts,
    )
    learning_signals = signal_registry.list_signals()
    health = build_memory_health(
        entity=entity,
        corrections=corrections,
        active_learning_questions=active_learning_questions,
        learning_signals=learning_signals,
    )
    suggestions = build_replay_suggestions(
        entity=entity,
        conflicts=conflicts,
        health=health,
        learning_signals=learning_signals,
    )

    affected_signal_ids: list[str] = []
    queued_question_ids: list[str] = []
    updated = entity

    if conflicts and entity.lifecycle_state not in {"archived", "forgotten"}:
        updated = entity_registry.record_contradiction(
            entity_id=entity.entity_id,
            rejected_label=None,
            amount=0.05,
            reason="Learning replay applied conflict evidence",
        ) or entity

    pending_related = [
        signal
        for signal in signal_registry.list_signals(status="pending", entity_id=entity.entity_id)
        if signal.signal_type in {"contradiction", "candidate_review", "low_health", "passive_observation"}
    ]
    for signal in pending_related:
        resolved = signal_registry.resolve_signal(signal.signal_id, resolution="Learning replay applied")
        if resolved:
            affected_signal_ids.append(resolved.signal_id)

    if health.get("state") in {"watch", "needs_review"} or conflicts:
        context = {
            "entity_id": entity.entity_id,
            "label": entity.label,
            "lifecycle_state": updated.lifecycle_state,
        }
        score = ActiveLearningPriorityScorer().score(
            question_type="review_memory",
            confidence=updated.confidence,
            domain_type=updated.domain_type,
            suggested_action="confirm_or_correct_memory",
            context=context,
            signals=signal_registry.list_signals(),
        )
        question = active_learning_registry.upsert_question(
            question_type="review_memory",
            prompt=f"Review '{entity.label}' because learning replay found memory-quality signals.",
            dedupe_key=f"learning_replay_review:{entity.entity_id}",
            domain_type=entity.domain_type,
            priority=score.priority,
            confidence=updated.confidence,
            suggested_action="confirm_or_correct_memory",
            context=context,
            priority_reason=score.priority_reason,
            source_signal_ids=score.source_signal_ids,
            learning_value=score.learning_value,
            risk_level=score.risk_level,
            cooldown_until=score.cooldown_until,
        )
        queued_question_ids.append(question.question_id)

    signal_registry.upsert_signal(
        signal_type="learning_replay",
        source="learning_replay",
        source_id=entity.entity_id,
        entity_id=entity.entity_id,
        domain_type=entity.domain_type,
        summary="Learning replay applied related corrections and passive signals",
        dedupe_key=f"learning_replay:{entity.entity_id}:{updated.updated_at}",
        confidence=updated.confidence,
        learning_value=0.8,
        risk_level="medium" if conflicts else "low",
        evidence=[*affected_signal_ids, *(signal.signal_id for signal in conflict_signals)],
        metadata={
            "queued_question_count": len(queued_question_ids),
            "conflict_count": len(conflicts),
        },
    )

    return LearningReplayResult(
        applied=bool(affected_signal_ids or queued_question_ids or conflicts),
        entity=updated,
        affected_signal_ids=affected_signal_ids,
        queued_question_ids=queued_question_ids,
        suggestions=suggestions,
        summary={
            "affected_signal_count": len(affected_signal_ids),
            "queued_question_count": len(queued_question_ids),
            "conflict_count": len(conflicts),
        },
    )
