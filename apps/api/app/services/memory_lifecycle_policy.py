from __future__ import annotations

from dataclasses import dataclass, field

from app.services.learning_signal_registry import LearningSignalRecord, LearningSignalRegistry
from app.services.memory_entity_registry import MemoryEntityRecord, MemoryEntityRegistry


@dataclass(frozen=True)
class LifecyclePolicyResult:
    applied: bool
    entity: MemoryEntityRecord | None = None
    signal_ids: list[str] = field(default_factory=list)
    reason: str = ""


class MemoryLifecyclePolicy:
    """Balanced-auto policy for turning passive evidence into memory updates."""

    def __init__(
        self,
        *,
        high_confidence_threshold: float = 0.85,
        min_reinforcement_signals: int = 2,
        max_reinforcement_amount: float = 0.1,
    ) -> None:
        self.high_confidence_threshold = high_confidence_threshold
        self.min_reinforcement_signals = min_reinforcement_signals
        self.max_reinforcement_amount = max_reinforcement_amount

    def apply_balanced_auto_reinforcement(
        self,
        *,
        entity: MemoryEntityRecord,
        entity_registry: MemoryEntityRegistry,
        signal_registry: LearningSignalRegistry,
    ) -> LifecyclePolicyResult:
        if entity.lifecycle_state in {"archived", "forgotten", "uncertain"}:
            return LifecyclePolicyResult(applied=False, entity=entity, reason="state is not eligible")
        if entity.lifecycle_state == "candidate" and entity.domain_type == "person":
            return LifecyclePolicyResult(applied=False, entity=entity, reason="person candidates require review")

        signals = [
            signal
            for signal in signal_registry.list_signals(status="pending", entity_id=entity.entity_id)
            if signal.signal_type in {"memory_run_match", "positive_observation", "active_learning_confirmation"}
            and signal.confidence >= self.high_confidence_threshold
        ]
        if len(signals) < self.min_reinforcement_signals:
            return LifecyclePolicyResult(applied=False, entity=entity, reason="not enough evidence")

        amount = min(self.max_reinforcement_amount, 0.03 * len(signals))
        updated = entity_registry.reinforce_entity(
            entity_id=entity.entity_id,
            amount=amount,
            reason="Auto reinforcement from repeated high-confidence passive evidence",
            source_id="learning-policy",
        )
        if updated is None:
            return LifecyclePolicyResult(applied=False, reason="memory not found")

        resolved = signal_registry.resolve_many(
            [signal.signal_id for signal in signals],
            resolution="Used for balanced-auto reinforcement",
        )
        signal_registry.upsert_signal(
            signal_type="auto_reinforcement",
            source="memory_lifecycle_policy",
            source_id=updated.entity_id,
            entity_id=updated.entity_id,
            domain_type=updated.domain_type,
            summary="Balanced-auto policy reinforced this existing memory",
            dedupe_key=f"auto_reinforcement:{updated.entity_id}:{updated.updated_at}",
            confidence=updated.confidence,
            learning_value=0.75,
            risk_level="low",
            evidence=[signal.signal_id for signal in signals],
            metadata={"reinforcement_amount": amount, "source_signal_count": len(signals)},
        )
        return LifecyclePolicyResult(
            applied=True,
            entity=updated,
            signal_ids=[signal.signal_id for signal in resolved],
            reason="balanced-auto reinforcement applied",
        )
