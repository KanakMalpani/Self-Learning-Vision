from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class BenchmarkRunRecord:
    run_id: str
    label: str
    notes: str | None = None
    benchmark_case_ids: list[str] = field(default_factory=list)
    provider_selections: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""


class BenchmarkRunRegistry:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def list_runs(self) -> list[BenchmarkRunRecord]:
        records = [self._record_from_payload(item) for item in self._load_payload()]
        return sorted(
            [record for record in records if record is not None],
            key=lambda item: item.created_at,
            reverse=True,
        )

    def add_run(
        self,
        *,
        label: str,
        notes: str | None,
        benchmark_case_ids: list[str],
        provider_selections: dict[str, str],
        metrics: dict[str, Any],
    ) -> BenchmarkRunRecord:
        clean_label = label.strip() or f"Benchmark {datetime.now(UTC).date().isoformat()}"
        with self._lock:
            records = self.list_runs()
            record = BenchmarkRunRecord(
                run_id=str(uuid4()),
                label=clean_label,
                notes=notes.strip() if notes else None,
                benchmark_case_ids=_string_list(benchmark_case_ids),
                provider_selections=dict(provider_selections),
                metrics=_sanitize_metrics(metrics),
                created_at=datetime.now(UTC).isoformat(),
            )
            records.append(record)
            self._save_payload([asdict(item) for item in records])
            return record

    def _load_payload(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return payload if isinstance(payload, list) else []

    def _save_payload(self, payload: list[dict[str, Any]]) -> None:
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(self.path)

    def _record_from_payload(self, item: dict[str, Any]) -> BenchmarkRunRecord | None:
        if not isinstance(item, dict):
            return None
        run_id = str(item.get("run_id") or "").strip()
        label = str(item.get("label") or "").strip()
        if not run_id or not label:
            return None
        provider_selections = item.get("provider_selections")
        metrics = item.get("metrics")
        return BenchmarkRunRecord(
            run_id=run_id,
            label=label,
            notes=str(item.get("notes") or "") or None,
            benchmark_case_ids=_string_list(item.get("benchmark_case_ids")),
            provider_selections=provider_selections if isinstance(provider_selections, dict) else {},
            metrics=metrics if isinstance(metrics, dict) else {},
            created_at=str(item.get("created_at") or "") or datetime.now(UTC).isoformat(),
        )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _sanitize_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "memory_runs",
        "recognition_decisions",
        "uncertainty_rate",
        "correction_rate",
        "active_learning_completion_rate",
        "estimated_precision",
        "estimated_recall",
        "false_match_signals",
        "missed_match_signals",
        "passive_signal_count",
        "auto_reinforcement_count",
        "review_inbox_pending_count",
        "contradiction_rate",
        "memory_health_distribution",
        "replay_applied_count",
    }
    return {key: value for key, value in metrics.items() if key in allowed}
