from __future__ import annotations

from typing import Any

from app.services.learning_policy_registry import LearningPolicyRecord
from app.services.learning_signal_registry import LearningSignalRecord
from app.services.memory_entity_registry import MemoryEntityRecord
from app.services.memory_health import build_memory_health


def simulate_learning_policy(
    *,
    policy: LearningPolicyRecord,
    entities: list[MemoryEntityRecord],
    learning_signals: list[LearningSignalRecord],
    corrections: list[object],
    active_learning_questions: list[object],
) -> dict[str, Any]:
    auto_reinforce = []
    needs_review = []
    blocked = []

    for entity in entities:
        matching_signals = [
            signal
            for signal in learning_signals
            if signal.status == "pending"
            and signal.entity_id == entity.entity_id
            and signal.signal_type in {"memory_run_match", "positive_observation", "active_learning_confirmation"}
            and signal.confidence >= policy.high_confidence_threshold
        ]
        health = build_memory_health(
            entity=entity,
            corrections=corrections,  # type: ignore[arg-type]
            active_learning_questions=active_learning_questions,
            learning_signals=learning_signals,
        )
        if entity.lifecycle_state in {"archived", "forgotten", "uncertain"}:
            blocked.append({"entity_id": entity.entity_id, "label": entity.label, "reason": entity.lifecycle_state})
            continue
        if entity.lifecycle_state == "candidate" and entity.domain_type == "person":
            needs_review.append({"entity_id": entity.entity_id, "label": entity.label, "reason": "person identity review required"})
            continue
        if policy.auto_reinforcement_enabled and len(matching_signals) >= policy.min_reinforcement_signals:
            auto_reinforce.append(
                {
                    "entity_id": entity.entity_id,
                    "label": entity.label,
                    "signal_count": len(matching_signals),
                    "estimated_amount": min(policy.max_reinforcement_amount, 0.03 * len(matching_signals)),
                }
            )
        elif health["state"] in {"watch", "needs_review"}:
            needs_review.append({"entity_id": entity.entity_id, "label": entity.label, "reason": health["state"]})

    return {
        "preset": policy.preset,
        "auto_reinforcement_enabled": policy.auto_reinforcement_enabled,
        "auto_reinforce_count": len(auto_reinforce),
        "needs_review_count": len(needs_review),
        "blocked_count": len(blocked),
        "review_budget_per_session": policy.review_budget_per_session,
        "auto_reinforce": auto_reinforce[:20],
        "needs_review": needs_review[:20],
        "blocked": blocked[:20],
    }
