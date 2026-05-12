from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from typing import Any, Iterable


RECOGNITION_DECISIONS = ("matched", "tentative", "unknown")


def build_evaluation_metrics(
    *,
    memory_runs: Iterable[object],
    active_learning_questions: Iterable[object],
    corrections: Iterable[object],
    memory_entities: Iterable[object],
    learning_signals: Iterable[object] = (),
    memory_health_distribution: dict[str, int] | None = None,
    review_inbox_pending_count: int = 0,
    lifecycle_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runs = list(memory_runs)
    questions = list(active_learning_questions)
    correction_records = list(corrections)
    entities = list(memory_entities)
    signals = list(learning_signals)
    lifecycle = lifecycle_summary or {}

    decisions = Counter(_recognition_decision(run) for run in runs)
    decisions = Counter({key: decisions.get(key, 0) for key in RECOGNITION_DECISIONS})
    confidences = [_recognition_confidence(run) for run in runs]
    confidences = [item for item in confidences if item is not None]

    answered_questions = [
        question
        for question in questions
        if _question_status(question) in {"answered", "dismissed"} and _question_response(question)
    ]
    pending_questions = [question for question in questions if _question_status(question) == "pending"]
    actions = Counter(_response_action(_question_response(question)) for question in answered_questions)
    correction_types = Counter(_correction_operation(record) for record in correction_records)

    contradictions = _int_value(lifecycle.get("contradictions"))
    signal_contradictions = len([signal for signal in signals if _signal_type(signal) == "contradiction"])
    false_match_signals = correction_types.get("not_this", 0) + actions.get("reject", 0) + contradictions
    missed_match_signals = actions.get("label", 0) + correction_types.get("merge", 0)
    reviewed_positive = actions.get("confirm", 0)
    reviewed_learned = reviewed_positive + actions.get("label", 0)

    precision_denominator = reviewed_positive + false_match_signals
    recall_denominator = reviewed_learned + missed_match_signals

    total_runs = len(runs)
    total_questions = len(questions)
    review_needed = decisions.get("tentative", 0) + decisions.get("unknown", 0)
    active_answered = len(answered_questions)

    return {
        "memory_runs": total_runs,
        "recognition_decisions": dict(decisions),
        "average_recognition_confidence": _rate(sum(confidences), len(confidences)),
        "active_learning_questions": total_questions,
        "active_learning_pending": len(pending_questions),
        "active_learning_answered": active_answered,
        "active_learning_actions": dict(actions),
        "corrections": len(correction_records),
        "corrections_by_type": dict(correction_types),
        "memory_entities": len(entities),
        "memory_lifecycle": lifecycle,
        "passive_signal_count": len(signals),
        "auto_reinforcement_count": len(
            [signal for signal in signals if _signal_type(signal) == "auto_reinforcement"]
        ),
        "review_inbox_pending_count": review_inbox_pending_count,
        "contradiction_rate": _rate(contradictions + signal_contradictions, len(entities)),
        "memory_health_distribution": memory_health_distribution or {},
        "replay_applied_count": len([signal for signal in signals if _signal_type(signal) == "learning_replay"]),
        "false_match_signals": false_match_signals,
        "missed_match_signals": missed_match_signals,
        "uncertainty_rate": _rate(review_needed, total_runs),
        "correction_rate": _rate(len(correction_records), total_runs),
        "active_learning_completion_rate": _rate(active_answered, total_questions),
        "estimated_precision": _rate(reviewed_positive, precision_denominator)
        if precision_denominator
        else None,
        "estimated_recall": _rate(reviewed_learned, recall_denominator)
        if recall_denominator
        else None,
        "memory_growth_per_run": _rate(len(entities), total_runs),
        "notes": [
            "Precision and recall are estimates from user feedback and correction signals.",
            "Evaluation output excludes raw images, upload paths, biometric embeddings, and provider secrets.",
        ],
    }


def build_evaluation_dataset(
    *,
    active_learning_questions: Iterable[object],
    corrections: Iterable[object],
    memory_entities: Iterable[object],
) -> dict[str, Any]:
    examples: list[dict[str, Any]] = []

    for question in active_learning_questions:
        response = _question_response(question)
        if not response:
            continue
        examples.append(
            {
                "example_id": f"active-learning:{_attr(question, 'question_id')}",
                "source": "active_learning",
                "task": _attr(question, "question_type"),
                "domain_type": _attr(question, "domain_type", "person"),
                "status": _attr(question, "status"),
                "action": _response_action(response),
                "label": _response_label(response) or _attr(question, "candidate_label"),
                "candidate_label": _attr(question, "candidate_label"),
                "memory_run_id": _attr(question, "memory_run_id"),
                "upload_id": _attr(question, "upload_id"),
                "selected_face_index": _attr(question, "selected_face_index"),
                "unknown_cluster_id": _attr(question, "unknown_cluster_id"),
                "confidence": _float_value(_attr(question, "confidence")),
                "created_at": _attr(question, "created_at"),
                "answered_at": _attr(response, "answered_at"),
            }
        )

    for correction in corrections:
        examples.append(
            {
                "example_id": f"correction:{_attr(correction, 'correction_id')}",
                "source": "correction",
                "task": _attr(correction, "operation_type"),
                "target_entity_id": _attr(correction, "target_entity_id"),
                "summary": _attr(correction, "summary"),
                "undone": bool(_attr(correction, "undone", False)),
                "created_at": _attr(correction, "created_at"),
            }
        )

    for entity in memory_entities:
        observations = list(_attr(entity, "observations", []) or [])
        lifecycle_events = list(_attr(entity, "lifecycle_events", []) or [])
        examples.append(
            {
                "example_id": f"memory-entity:{_attr(entity, 'entity_id')}",
                "source": "memory_entity",
                "task": "memory_state",
                "domain_type": _attr(entity, "domain_type"),
                "label": _attr(entity, "label"),
                "lifecycle_state": _attr(entity, "lifecycle_state"),
                "confidence": _float_value(_attr(entity, "confidence")),
                "observation_count": len(observations),
                "lifecycle_event_count": len(lifecycle_events),
                "created_at": _attr(entity, "created_at"),
                "updated_at": _attr(entity, "updated_at"),
            }
        )

    return {
        "schema_version": "evaluation-dataset.v1",
        "examples": examples,
        "example_count": len(examples),
        "redaction": {
            "raw_images": "excluded",
            "upload_paths": "excluded",
            "biometric_embeddings": "excluded",
            "provider_secrets": "excluded",
            "free_text_notes": "excluded except correction summaries",
        },
    }


def build_provider_scorecard(
    *,
    provider_cards: Iterable[object],
    provider_selections: dict[str, str],
    evaluation_metrics: dict[str, Any],
) -> dict[str, Any]:
    cards = list(provider_cards)
    selected_ids = set(provider_selections.values())
    if not selected_ids:
        selected_ids.add("local-face-embedding")

    provider_rows = []
    for card in cards:
        provider_id = str(_attr(card, "provider_id", ""))
        if provider_id not in selected_ids:
            continue
        provider_rows.append(
            {
                "provider_id": provider_id,
                "display_name": _attr(card, "display_name"),
                "mode": _attr(card, "mode"),
                "status": _attr(card, "status"),
                "capabilities": list(_attr(card, "capabilities", []) or []),
                "cost_model": _attr(card, "cost_model"),
                "images_leave_device": bool(_attr(card, "images_leave_device", False)),
                "privacy_notes": _attr(card, "privacy_notes"),
                "selected_for": [
                    capability
                    for capability, selected_provider in provider_selections.items()
                    if selected_provider == provider_id
                ],
            }
        )

    return {
        "schema_version": "provider-scorecard.v1",
        "provider_selections": dict(provider_selections),
        "providers": provider_rows,
        "metrics": {
            "memory_runs": evaluation_metrics.get("memory_runs", 0),
            "recognition_decisions": evaluation_metrics.get("recognition_decisions", {}),
            "uncertainty_rate": evaluation_metrics.get("uncertainty_rate"),
            "correction_rate": evaluation_metrics.get("correction_rate"),
            "estimated_precision": evaluation_metrics.get("estimated_precision"),
            "estimated_recall": evaluation_metrics.get("estimated_recall"),
        },
        "benchmark_guidance": [
            "Run the same consent-safe fixture set before and after changing providers.",
            "Compare estimated precision, estimated recall, uncertainty rate, and correction rate.",
            "Do not export raw images or embeddings when sharing scorecards publicly.",
        ],
    }


def _recognition_decision(run: object) -> str:
    report = _attr(run, "memory_report", {}) or {}
    if not isinstance(report, dict):
        return "unknown"
    summary = report.get("recognition_summary")
    if not isinstance(summary, dict):
        return "unknown"
    decision = str(summary.get("recognition_decision") or summary.get("final_verdict_decision") or "")
    decision = decision.strip().lower()
    return decision if decision in RECOGNITION_DECISIONS else "unknown"


def _recognition_confidence(run: object) -> float | None:
    report = _attr(run, "memory_report", {}) or {}
    if not isinstance(report, dict):
        return None
    summary = report.get("recognition_summary")
    if isinstance(summary, dict) and summary.get("confidence") is not None:
        return _float_value(summary.get("confidence"))
    confidence = report.get("confidence")
    if isinstance(confidence, dict):
        return _float_value(confidence.get("overall"))
    return None


def _question_status(question: object) -> str:
    return str(_attr(question, "status", "pending")).strip().lower()


def _question_response(question: object) -> object | None:
    return _attr(question, "response")


def _response_action(response: object | None) -> str:
    return str(_attr(response, "action", "")).strip().lower()


def _response_label(response: object | None) -> str | None:
    label = str(_attr(response, "label", "") or "").strip()
    return label or None


def _correction_operation(record: object) -> str:
    return str(_attr(record, "operation_type", "unknown")).strip().lower() or "unknown"


def _signal_type(record: object) -> str:
    return str(_attr(record, "signal_type", "unknown")).strip().lower() or "unknown"


def _attr(item: object, name: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    if hasattr(item, name):
        return getattr(item, name)
    try:
        payload = asdict(item)  # type: ignore[arg-type]
    except TypeError:
        return default
    return payload.get(name, default)


def _float_value(value: object) -> float | None:
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def _int_value(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _rate(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), 6)
