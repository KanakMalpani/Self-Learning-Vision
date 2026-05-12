from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


POLICY_PRESETS = {
    "conservative": {
        "auto_reinforcement_enabled": False,
        "high_confidence_threshold": 0.92,
        "min_reinforcement_signals": 3,
        "max_reinforcement_amount": 0.05,
        "review_budget_per_session": 3,
    },
    "balanced": {
        "auto_reinforcement_enabled": True,
        "high_confidence_threshold": 0.85,
        "min_reinforcement_signals": 2,
        "max_reinforcement_amount": 0.1,
        "review_budget_per_session": 6,
    },
    "experimental": {
        "auto_reinforcement_enabled": True,
        "high_confidence_threshold": 0.78,
        "min_reinforcement_signals": 2,
        "max_reinforcement_amount": 0.15,
        "review_budget_per_session": 10,
    },
}


@dataclass
class LearningPolicyRecord:
    preset: str = "balanced"
    auto_reinforcement_enabled: bool = True
    high_confidence_threshold: float = 0.85
    min_reinforcement_signals: int = 2
    max_reinforcement_amount: float = 0.1
    review_budget_per_session: int = 6
    updated_at: str = ""


class LearningPolicyRegistry:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def get(self) -> LearningPolicyRecord:
        if not self.path.exists():
            return self._record_for_preset("balanced")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return self._record_for_preset("balanced")
        return self._record_from_payload(payload)

    def set_preset(self, preset: str) -> LearningPolicyRecord:
        record = self._record_for_preset(preset)
        with self._lock:
            self._save_payload(asdict(record))
        return record

    def _record_for_preset(self, preset: str) -> LearningPolicyRecord:
        normalized = preset.strip().lower()
        if normalized not in POLICY_PRESETS:
            normalized = "balanced"
        values = POLICY_PRESETS[normalized]
        return LearningPolicyRecord(
            preset=normalized,
            auto_reinforcement_enabled=bool(values["auto_reinforcement_enabled"]),
            high_confidence_threshold=float(values["high_confidence_threshold"]),
            min_reinforcement_signals=int(values["min_reinforcement_signals"]),
            max_reinforcement_amount=float(values["max_reinforcement_amount"]),
            review_budget_per_session=int(values["review_budget_per_session"]),
            updated_at=datetime.now(UTC).isoformat(),
        )

    def _record_from_payload(self, payload: object) -> LearningPolicyRecord:
        if not isinstance(payload, dict):
            return self._record_for_preset("balanced")
        preset = str(payload.get("preset") or "balanced").strip().lower()
        base = self._record_for_preset(preset)
        return LearningPolicyRecord(
            preset=base.preset,
            auto_reinforcement_enabled=bool(payload.get("auto_reinforcement_enabled", base.auto_reinforcement_enabled)),
            high_confidence_threshold=_float(payload.get("high_confidence_threshold"), base.high_confidence_threshold),
            min_reinforcement_signals=max(1, int(payload.get("min_reinforcement_signals") or base.min_reinforcement_signals)),
            max_reinforcement_amount=max(0.0, min(1.0, _float(payload.get("max_reinforcement_amount"), base.max_reinforcement_amount))),
            review_budget_per_session=max(1, int(payload.get("review_budget_per_session") or base.review_budget_per_session)),
            updated_at=str(payload.get("updated_at") or "") or datetime.now(UTC).isoformat(),
        )

    def _save_payload(self, payload: dict[str, object]) -> None:
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(self.path)


def _float(value: object, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
