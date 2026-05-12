from __future__ import annotations

from pathlib import Path

from app.services.active_learning_priority import ActiveLearningPriorityScorer
from app.services.active_learning_registry import ActiveLearningRegistry
from app.services.contradiction_detector import detect_memory_contradictions
from app.services.correction_log_registry import CorrectionLogRecord
from app.services.evidence_bundles import build_evidence_bundles
from app.services.learning_replay import apply_learning_replay
from app.services.learning_policy_registry import LearningPolicyRegistry
from app.services.learning_policy_simulator import simulate_learning_policy
from app.services.learning_signal_registry import LearningSignalRegistry
from app.services.learning_timeline import build_learning_timeline
from app.services.memory_entity_registry import MemoryEntityRecord, MemoryEntityRegistry, MemoryObservation
from app.services.memory_health import build_memory_health
from app.services.memory_lifecycle_policy import MemoryLifecyclePolicy
from app.services.review_inbox import build_learning_review_inbox


def test_learning_signal_registry_dedupes_and_redacts_sensitive_metadata(tmp_path: Path) -> None:
    registry = LearningSignalRegistry(tmp_path / "signals.json")

    first = registry.upsert_signal(
        signal_type="memory_run_match",
        source="memory_run",
        summary="High-confidence match",
        dedupe_key="match:run-a",
        domain_type="person",
        entity_id="entity-a",
        confidence=0.91,
        learning_value=0.8,
        metadata={"embedding": [1, 2, 3], "file_path": "private.jpg", "provider": "local"},
    )
    second = registry.upsert_signal(
        signal_type="memory_run_match",
        source="memory_run",
        summary="Updated match",
        dedupe_key="match:run-a",
        domain_type="person",
        entity_id="entity-a",
        confidence=0.93,
        learning_value=0.85,
    )

    assert first.signal_id == second.signal_id
    assert registry.pending_count() == 1
    assert second.summary == "Updated match"
    assert second.metadata == {"provider": "local"}


def test_priority_scorer_ranks_conflicts_above_plain_review() -> None:
    conflict_signal = type(
        "Signal",
        (),
        {
            "signal_id": "signal-a",
            "status": "pending",
            "entity_id": "entity-a",
            "source_id": None,
            "metadata": {},
            "signal_type": "contradiction",
            "learning_value": 0.9,
        },
    )()
    scorer = ActiveLearningPriorityScorer()

    conflict = scorer.score(
        question_type="review_memory",
        confidence=0.5,
        domain_type="person",
        suggested_action="confirm_or_correct_memory",
        context={"entity_id": "entity-a", "lifecycle_state": "uncertain"},
        signals=[conflict_signal],
    )
    plain = scorer.score(
        question_type="review_memory",
        confidence=0.9,
        domain_type="object",
        suggested_action="fill_missing_memory_fields",
        context={"entity_id": "entity-b", "lifecycle_state": "confirmed"},
        signals=[],
    )

    assert conflict.priority > plain.priority
    assert conflict.risk_level == "high"
    assert conflict.source_signal_ids == ["signal-a"]


def test_lifecycle_policy_auto_reinforces_existing_memory_only(tmp_path: Path) -> None:
    entity_registry = MemoryEntityRegistry(tmp_path / "entities.json")
    signal_registry = LearningSignalRegistry(tmp_path / "signals.json")
    entity = entity_registry.upsert_entity(
        domain_type="object",
        label="Lab Camera",
        confidence=0.72,
        lifecycle_state="confirmed",
    )
    for index in range(2):
        signal_registry.upsert_signal(
            signal_type="memory_run_match",
            source="memory_run",
            summary=f"Matched camera {index}",
            dedupe_key=f"match:{index}",
            entity_id=entity.entity_id,
            domain_type=entity.domain_type,
            confidence=0.9,
            learning_value=0.8,
        )

    result = MemoryLifecyclePolicy().apply_balanced_auto_reinforcement(
        entity=entity,
        entity_registry=entity_registry,
        signal_registry=signal_registry,
    )

    assert result.applied is True
    assert result.entity is not None
    assert result.entity.confidence > 0.72
    assert len(result.signal_ids) == 2
    assert signal_registry.list_signals(signal_type="auto_reinforcement")

    person_candidate = entity_registry.upsert_entity(
        domain_type="person",
        label="Candidate Person",
        confidence=0.9,
        lifecycle_state="candidate",
    )
    blocked = MemoryLifecyclePolicy().apply_balanced_auto_reinforcement(
        entity=person_candidate,
        entity_registry=entity_registry,
        signal_registry=signal_registry,
    )
    assert blocked.applied is False


def test_conflicts_evidence_and_health_use_related_learning_signals(tmp_path: Path) -> None:
    entity = MemoryEntityRecord(
        entity_id="entity-a",
        domain_type="person",
        label="Ada",
        confidence=0.8,
        lifecycle_state="confirmed",
        observations=[
            MemoryObservation(
                observation_id="obs-a",
                source="manual",
                confidence=0.8,
                observed_at="2026-01-01T00:00:00+00:00",
            )
        ],
    )
    correction = CorrectionLogRecord(
        correction_id="correction-a",
        operation_type="not_this",
        target_entity_id="entity-a",
        summary="Marked as incorrect",
        created_at="2026-01-02T00:00:00+00:00",
    )
    signal = LearningSignalRegistry(tmp_path / "signals.json").upsert_signal(
        signal_type="contradiction",
        source="test",
        summary="Conflict",
        dedupe_key="conflict:a",
        entity_id="entity-a",
        domain_type="person",
        confidence=0.7,
        learning_value=0.9,
        risk_level="high",
    )

    conflicts = detect_memory_contradictions(
        entity=entity,
        all_entities=[entity],
        corrections=[correction],
        active_learning_questions=[],
        learning_signals=[signal],
    )
    bundles = build_evidence_bundles(
        entity=entity,
        corrections=[correction],
        active_learning_questions=[],
        learning_signals=[signal],
    )
    health = build_memory_health(
        entity=entity,
        corrections=[correction],
        active_learning_questions=[],
        learning_signals=[signal],
    )

    assert len(conflicts) >= 2
    assert {bundle["source"] for bundle in bundles} >= {"memory_observations", "corrections", "learning_signals"}
    assert health["state"] == "needs_review"
    assert health["contradiction_count"] >= 2


def test_learning_replay_resolves_signals_and_queues_review(tmp_path: Path) -> None:
    entity_registry = MemoryEntityRegistry(tmp_path / "entities.json")
    signal_registry = LearningSignalRegistry(tmp_path / "signals.json")
    active_registry = ActiveLearningRegistry(tmp_path / "questions.json")
    entity = entity_registry.upsert_entity(
        domain_type="object",
        label="Lab Camera",
        confidence=0.75,
        lifecycle_state="confirmed",
    )
    signal_registry.upsert_signal(
        signal_type="contradiction",
        source="test",
        summary="Object label conflict",
        dedupe_key="conflict:camera",
        entity_id=entity.entity_id,
        domain_type=entity.domain_type,
        confidence=0.7,
        learning_value=0.9,
        risk_level="high",
    )

    result = apply_learning_replay(
        entity_id=entity.entity_id,
        entity_registry=entity_registry,
        active_learning_registry=active_registry,
        signal_registry=signal_registry,
        corrections=[],
        active_learning_questions=[],
    )

    assert result.applied is True
    assert result.entity is not None
    assert result.entity.lifecycle_state == "uncertain"
    assert result.affected_signal_ids
    assert result.queued_question_ids


def test_review_inbox_groups_questions_signals_and_health(tmp_path: Path) -> None:
    entity_registry = MemoryEntityRegistry(tmp_path / "entities.json")
    signal_registry = LearningSignalRegistry(tmp_path / "signals.json")
    active_registry = ActiveLearningRegistry(tmp_path / "questions.json")
    entity = entity_registry.upsert_entity(
        domain_type="object",
        label="Candidate Camera",
        confidence=0.35,
        lifecycle_state="candidate",
    )
    active_registry.upsert_question(
        question_type="review_memory",
        prompt="Review camera",
        dedupe_key="review:camera",
        domain_type="object",
        priority=80,
        context={"entity_id": entity.entity_id, "lifecycle_state": entity.lifecycle_state},
    )
    signal_registry.upsert_signal(
        signal_type="candidate_review",
        source="test",
        summary="Candidate needs review",
        dedupe_key="candidate:camera",
        entity_id=entity.entity_id,
        domain_type=entity.domain_type,
        confidence=0.35,
        learning_value=0.7,
    )

    inbox = build_learning_review_inbox(
        questions=active_registry.list_questions(status=None),
        entities=entity_registry.list_entities(),
        corrections=[],
        signal_registry=signal_registry,
    )

    assert inbox["summary"]["pending_question_count"] == 1
    assert inbox["summary"]["pending_signal_count"] == 1
    assert inbox["candidate_memories"][0]["entity"].entity_id == entity.entity_id


def test_policy_registry_and_simulator_preview_learning_effects(tmp_path: Path) -> None:
    policy_registry = LearningPolicyRegistry(tmp_path / "policy.json")
    policy = policy_registry.set_preset("experimental")
    entity_registry = MemoryEntityRegistry(tmp_path / "entities.json")
    signal_registry = LearningSignalRegistry(tmp_path / "signals.json")
    entity = entity_registry.upsert_entity(
        domain_type="object",
        label="Workbench Camera",
        confidence=0.8,
        lifecycle_state="confirmed",
    )
    for index in range(2):
        signal_registry.upsert_signal(
            signal_type="positive_observation",
            source="test",
            summary="High confidence object sighting",
            dedupe_key=f"positive:{index}",
            entity_id=entity.entity_id,
            domain_type=entity.domain_type,
            confidence=0.8,
            learning_value=0.8,
        )

    simulation = simulate_learning_policy(
        policy=policy,
        entities=entity_registry.list_entities(),
        learning_signals=signal_registry.list_signals(status=None),
        corrections=[],
        active_learning_questions=[],
    )

    assert policy.preset == "experimental"
    assert simulation["auto_reinforce_count"] == 1
    assert simulation["auto_reinforce"][0]["entity_id"] == entity.entity_id


def test_learning_timeline_combines_memory_events() -> None:
    entity = MemoryEntityRecord(
        entity_id="entity-a",
        domain_type="object",
        label="Camera",
        confidence=0.7,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-03T00:00:00+00:00",
        observations=[
            MemoryObservation(
                observation_id="obs-a",
                source="manual",
                confidence=0.7,
                observed_at="2026-01-02T00:00:00+00:00",
            )
        ],
    )
    signal = type(
        "Signal",
        (),
        {
            "signal_id": "signal-a",
            "entity_id": "entity-a",
            "signal_type": "positive_observation",
            "summary": "Passive evidence",
            "confidence": 0.8,
            "updated_at": "2026-01-04T00:00:00+00:00",
        },
    )()

    timeline = build_learning_timeline(
        entity=entity,
        corrections=[],
        active_learning_questions=[],
        learning_signals=[signal],
    )

    assert timeline[0]["timeline_id"] == "signal:signal-a"
    assert {item["source"] for item in timeline} >= {"memory_entity", "manual", "learning_signal"}
