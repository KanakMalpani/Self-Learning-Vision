from __future__ import annotations

from typing import Any

from app.services.contradiction_detector import detect_memory_contradictions, record_conflict_signals
from app.services.correction_log_registry import CorrectionLogRecord
from app.services.learning_replay import build_replay_suggestions
from app.services.learning_signal_registry import LearningSignalRecord, LearningSignalRegistry
from app.services.memory_entity_registry import MemoryEntityRecord
from app.services.memory_health import build_memory_health


def build_learning_review_inbox(
    *,
    questions: list[object],
    entities: list[MemoryEntityRecord],
    corrections: list[CorrectionLogRecord],
    signal_registry: LearningSignalRegistry,
) -> dict[str, Any]:
    signals = signal_registry.list_signals()
    pending_signals = [signal for signal in signals if signal.status == "pending"]
    pending_questions = [question for question in questions if getattr(question, "status", "") == "pending"]

    contradictions: list[LearningSignalRecord] = []
    memory_health_rows = []
    candidate_rows = []
    replay_suggestions = []

    for entity in entities:
        conflicts = detect_memory_contradictions(
            entity=entity,
            all_entities=entities,
            corrections=corrections,
            active_learning_questions=questions,
            learning_signals=signals,
        )
        conflict_records = record_conflict_signals(
            registry=signal_registry,
            entity=entity,
            conflicts=conflicts,
        )
        contradictions.extend([record for record in conflict_records if record.status == "pending"])
        refreshed_signals = signal_registry.list_signals()
        health = build_memory_health(
            entity=entity,
            corrections=corrections,
            active_learning_questions=questions,
            learning_signals=refreshed_signals,
        )
        health_row = {"entity": entity, "health": health}
        if entity.lifecycle_state == "candidate":
            candidate_rows.append(health_row)
        if health["state"] in {"watch", "needs_review"}:
            memory_health_rows.append(health_row)
        replay_suggestions.extend(
            build_replay_suggestions(
                entity=entity,
                conflicts=conflicts,
                health=health,
                learning_signals=refreshed_signals,
            )
        )

    signals = signal_registry.list_signals()
    pending_signals = [signal for signal in signals if signal.status == "pending"]
    contradictions.extend(
        signal
        for signal in signal_registry.list_signals(status="pending", signal_type="contradiction")
        if signal.signal_id not in {item.signal_id for item in contradictions}
    )

    pending_questions = sorted(
        pending_questions,
        key=lambda item: (getattr(item, "priority", 0), getattr(item, "learning_value", 0.0)),
        reverse=True,
    )
    contradictions = sorted(contradictions, key=lambda item: item.learning_value, reverse=True)
    memory_health_rows = sorted(memory_health_rows, key=lambda row: row["health"]["score"])
    candidate_rows = sorted(candidate_rows, key=lambda row: row["health"]["score"], reverse=True)
    replay_suggestions = _dedupe_suggestions(replay_suggestions)

    return {
        "questions": pending_questions[:20],
        "contradictions": contradictions[:20],
        "candidate_memories": candidate_rows[:20],
        "low_health_memories": memory_health_rows[:20],
        "replay_suggestions": replay_suggestions[:20],
        "signals": pending_signals[:50],
        "summary": {
            "pending_question_count": len(pending_questions),
            "pending_signal_count": len(pending_signals),
            "contradiction_count": len(contradictions),
            "candidate_memory_count": len(candidate_rows),
            "low_health_memory_count": len(memory_health_rows),
            "replay_suggestion_count": len(replay_suggestions),
        },
    }


def _dedupe_suggestions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    clean = []
    for item in items:
        suggestion_id = str(item.get("suggestion_id") or "").strip()
        if not suggestion_id or suggestion_id in seen:
            continue
        seen.add(suggestion_id)
        clean.append(item)
    return sorted(clean, key=lambda item: item.get("risk_level") == "high", reverse=True)
