from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.services.learning_signal_registry import LearningSignalRecord


@dataclass(frozen=True)
class QuestionPriorityScore:
    priority: int
    priority_reason: str
    learning_value: float
    risk_level: str
    source_signal_ids: list[str] = field(default_factory=list)
    cooldown_until: str | None = None


class ActiveLearningPriorityScorer:
    """Ranks questions by expected learning value instead of static UI order."""

    def score(
        self,
        *,
        question_type: str,
        confidence: float = 0.0,
        domain_type: str = "custom",
        suggested_action: str = "",
        context: dict[str, Any] | None = None,
        signals: list[LearningSignalRecord] | None = None,
        created_at: str | None = None,
    ) -> QuestionPriorityScore:
        context = context or {}
        related_signals = self._related_signals(context=context, signals=signals or [])
        reasons: list[str] = []
        score = 25
        risk_level = "low"

        question = question_type.strip().lower()
        action = suggested_action.strip().lower()
        lifecycle_state = str(context.get("lifecycle_state") or "").strip().lower()
        domain = domain_type.strip().lower()
        signal_types = {signal.signal_type for signal in related_signals}

        if question == "confirm_match":
            score += 28
            risk_level = "medium"
            reasons.append("tentative match can prevent a false memory")
        elif question == "label_unknown_cluster":
            score += 24
            risk_level = "medium"
            reasons.append("repeated unknown can become useful after review")
        elif question == "review_memory":
            score += 16
            reasons.append("memory review can improve structured recall")

        confidence = self._clamp(confidence)
        uncertainty = 1.0 - abs(confidence - 0.5) * 2.0
        if uncertainty >= 0.55:
            score += 18
            reasons.append("confidence is uncertain")
        elif confidence >= 0.85:
            score += 8
            reasons.append("high-confidence signal is ready to verify")
        elif confidence <= 0.25:
            score += 6
            reasons.append("low-confidence signal may need cleanup")

        if lifecycle_state == "uncertain":
            score += 22
            risk_level = "high"
            reasons.append("memory is already marked uncertain")
        elif lifecycle_state == "candidate":
            score += 12
            reasons.append("candidate memory needs promotion or dismissal")
        elif lifecycle_state == "stale":
            score += 8
            reasons.append("stale memory may need refresh")

        if "contradiction" in signal_types or action in {"resolve_conflict", "confirm_or_correct_memory"}:
            score += 24
            risk_level = "high"
            reasons.append("conflicting evidence exists")

        repeated_value = min(18, len(related_signals) * 4)
        if repeated_value:
            score += repeated_value
            reasons.append("related passive signals are waiting")

        if action == "fill_missing_memory_fields":
            score += 8
            reasons.append("missing fields reduce usefulness")

        if domain == "person":
            score += 5
            risk_level = "medium" if risk_level == "low" else risk_level

        age_bonus = self._age_bonus(created_at)
        if age_bonus:
            score += age_bonus
            reasons.append("older pending work should not be buried")

        priority = max(0, min(100, score))
        return QuestionPriorityScore(
            priority=priority,
            priority_reason=", ".join(reasons[:4]) or "useful memory review",
            learning_value=round(priority / 100.0, 6),
            risk_level=risk_level,
            source_signal_ids=[signal.signal_id for signal in related_signals[:6]],
            cooldown_until=None,
        )

    def _related_signals(
        self,
        *,
        context: dict[str, Any],
        signals: list[LearningSignalRecord],
    ) -> list[LearningSignalRecord]:
        entity_id = str(context.get("entity_id") or "").strip()
        unknown_cluster_id = str(context.get("unknown_cluster_id") or "").strip()
        memory_run_id = str(context.get("memory_run_id") or "").strip()
        related = []
        for signal in signals:
            if signal.status != "pending":
                continue
            if entity_id and signal.entity_id == entity_id:
                related.append(signal)
                continue
            if unknown_cluster_id and (
                signal.source_id == unknown_cluster_id
                or signal.metadata.get("unknown_cluster_id") == unknown_cluster_id
            ):
                related.append(signal)
                continue
            if memory_run_id and signal.source_id == memory_run_id:
                related.append(signal)
        return sorted(related, key=lambda item: item.learning_value, reverse=True)

    def _age_bonus(self, created_at: str | None) -> int:
        if not created_at:
            return 0
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            return 0
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        age_days = (datetime.now(UTC) - created).days
        if age_days >= 14:
            return 8
        if age_days >= 3:
            return 4
        return 0

    def _clamp(self, value: object) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.0
        return max(0.0, min(1.0, number))
