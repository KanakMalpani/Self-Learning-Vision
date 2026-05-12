from __future__ import annotations

from typing import Any

from app.services.active_learning_registry import ActiveLearningQuestion
from app.services.confidence_ledger import build_confidence_ledger
from app.services.contradiction_detector import detect_memory_contradictions
from app.services.correction_log_registry import CorrectionLogRecord
from app.services.evidence_bundles import build_evidence_bundles
from app.services.learning_replay import build_replay_suggestions
from app.services.learning_signal_registry import LearningSignalRecord
from app.services.learning_timeline import build_learning_timeline
from app.services.memory_entity_registry import MemoryEntityRecord
from app.services.memory_health import build_memory_health


def build_memory_entity_detail(
    *,
    entity: MemoryEntityRecord,
    corrections: list[CorrectionLogRecord],
    active_learning_questions: list[ActiveLearningQuestion],
    learning_signals: list[LearningSignalRecord] | None = None,
    all_entities: list[MemoryEntityRecord] | None = None,
) -> dict[str, Any]:
    learning_signals = learning_signals or []
    all_entities = all_entities or [entity]
    related_corrections = [
        correction
        for correction in corrections
        if correction.target_entity_id == entity.entity_id
    ]
    related_questions = [
        question
        for question in active_learning_questions
        if question.context.get("entity_id") == entity.entity_id
    ]
    pending_questions = [question for question in related_questions if question.status == "pending"]
    conflicts = detect_memory_contradictions(
        entity=entity,
        all_entities=all_entities,
        corrections=corrections,
        active_learning_questions=active_learning_questions,
        learning_signals=learning_signals,
    )
    health = build_memory_health(
        entity=entity,
        corrections=corrections,
        active_learning_questions=active_learning_questions,
        learning_signals=learning_signals,
    )
    evidence_bundles = build_evidence_bundles(
        entity=entity,
        corrections=corrections,
        active_learning_questions=active_learning_questions,
        learning_signals=learning_signals,
    )
    return {
        "entity_id": entity.entity_id,
        "confidence_ledger": build_confidence_ledger(entity=entity, corrections=corrections),
        "evidence_bundles": evidence_bundles,
        "health": health,
        "related_conflicts": conflicts,
        "replay_suggestions": build_replay_suggestions(
            entity=entity,
            conflicts=conflicts,
            health=health,
            learning_signals=learning_signals,
        ),
        "learning_timeline": build_learning_timeline(
            entity=entity,
            corrections=corrections,
            active_learning_questions=active_learning_questions,
            learning_signals=learning_signals,
        ),
        "summary": {
            "observation_count": len(entity.observations),
            "lifecycle_event_count": len(entity.lifecycle_events),
            "correction_count": len(related_corrections),
            "active_learning_question_count": len(related_questions),
            "pending_question_count": len(pending_questions),
            "evidence_bundle_count": len(evidence_bundles),
            "related_conflict_count": len(conflicts),
        },
    }
