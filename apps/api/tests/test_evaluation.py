from __future__ import annotations

from types import SimpleNamespace

from app.services.evaluation import (
    build_evaluation_dataset,
    build_evaluation_metrics,
    build_provider_scorecard,
)


def test_evaluation_metrics_estimate_quality_from_feedback_signals() -> None:
    memory_runs = [
        SimpleNamespace(memory_report={"recognition_summary": {"recognition_decision": "matched", "confidence": 0.9}}),
        SimpleNamespace(memory_report={"recognition_summary": {"recognition_decision": "tentative", "confidence": 0.6}}),
        SimpleNamespace(memory_report={"recognition_summary": {"recognition_decision": "unknown", "confidence": 0.2}}),
    ]
    active_questions = [
        SimpleNamespace(status="answered", response=SimpleNamespace(action="confirm")),
        SimpleNamespace(status="answered", response=SimpleNamespace(action="label")),
        SimpleNamespace(status="answered", response=SimpleNamespace(action="reject")),
        SimpleNamespace(status="pending", response=None),
    ]
    corrections = [
        SimpleNamespace(operation_type="not_this"),
        SimpleNamespace(operation_type="merge"),
    ]
    entities = [SimpleNamespace(entity_id="entity-a"), SimpleNamespace(entity_id="entity-b")]

    metrics = build_evaluation_metrics(
        memory_runs=memory_runs,
        active_learning_questions=active_questions,
        corrections=corrections,
        memory_entities=entities,
        lifecycle_summary={"contradictions": 1},
    )

    assert metrics["recognition_decisions"] == {"matched": 1, "tentative": 1, "unknown": 1}
    assert metrics["average_recognition_confidence"] == 0.566667
    assert metrics["false_match_signals"] == 3
    assert metrics["missed_match_signals"] == 2
    assert metrics["uncertainty_rate"] == 0.666667
    assert metrics["estimated_precision"] == 0.25
    assert metrics["estimated_recall"] == 0.5


def test_evaluation_dataset_excludes_raw_artifacts() -> None:
    active_questions = [
        SimpleNamespace(
            question_id="q1",
            question_type="label_unknown_cluster",
            domain_type="person",
            status="answered",
            response=SimpleNamespace(action="label", label="Ada", answered_at="2026-01-01T00:00:00+00:00"),
            memory_run_id="run-1",
            upload_id="upload-1",
            selected_face_index=0,
            candidate_label=None,
            unknown_cluster_id="cluster-1",
            confidence=0.4,
            created_at="2026-01-01T00:00:00+00:00",
        )
    ]
    corrections = [
        SimpleNamespace(
            correction_id="c1",
            operation_type="not_this",
            target_entity_id="entity-a",
            summary="Marked as incorrect",
            undone=False,
            created_at="2026-01-02T00:00:00+00:00",
        )
    ]
    entities = [
        SimpleNamespace(
            entity_id="entity-a",
            domain_type="person",
            label="Ada",
            lifecycle_state="confirmed",
            confidence=0.9,
            observations=[object()],
            lifecycle_events=[],
            created_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-02T00:00:00+00:00",
        )
    ]

    dataset = build_evaluation_dataset(
        active_learning_questions=active_questions,
        corrections=corrections,
        memory_entities=entities,
    )

    assert dataset["example_count"] == 3
    assert dataset["redaction"]["raw_images"] == "excluded"
    assert dataset["redaction"]["biometric_embeddings"] == "excluded"
    assert all("embedding" not in example for example in dataset["examples"])
    assert all("image_path" not in example for example in dataset["examples"])


def test_provider_scorecard_only_reports_selected_providers() -> None:
    cards = [
        SimpleNamespace(
            provider_id="local-face-embedding",
            display_name="Local Face Embedding",
            mode="local_free",
            status="ready",
            capabilities=["face_embedding"],
            cost_model="free",
            images_leave_device=False,
            privacy_notes="Images stay local.",
        ),
        SimpleNamespace(
            provider_id="template-paid-provider",
            display_name="Template Hosted Provider",
            mode="hosted_paid",
            status="blocked_by_privacy_policy",
            capabilities=["face_embedding"],
            cost_model="paid",
            images_leave_device=True,
            privacy_notes="Images may leave the device.",
        ),
    ]

    scorecard = build_provider_scorecard(
        provider_cards=cards,
        provider_selections={"face_embedding": "local-face-embedding"},
        evaluation_metrics={
            "memory_runs": 4,
            "recognition_decisions": {"matched": 3, "unknown": 1},
            "uncertainty_rate": 0.25,
            "correction_rate": 0.0,
            "estimated_precision": None,
            "estimated_recall": None,
        },
    )

    assert len(scorecard["providers"]) == 1
    assert scorecard["providers"][0]["provider_id"] == "local-face-embedding"
    assert scorecard["providers"][0]["images_leave_device"] is False
    assert scorecard["metrics"]["memory_runs"] == 4
