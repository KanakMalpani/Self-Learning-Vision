from __future__ import annotations

from app.services.benchmark_pack import build_benchmark_pack
from app.services.benchmark_run_registry import BenchmarkRunRegistry
from app.services.confidence_ledger import build_confidence_ledger
from app.services.correction_log_registry import CorrectionLogRecord
from app.services.domain_active_learning import DomainActiveLearningPlanner
from app.services.memory_detail import build_memory_entity_detail
from app.services.memory_entity_registry import MemoryEntityRecord, MemoryLifecycleEvent, MemoryObservation
from app.services.memory_search import search_memory_entities
from app.services.provider_conformance import evaluate_provider_conformance
from app.services.provider_marketplace import ProviderCard


def test_confidence_ledger_combines_creation_observations_lifecycle_and_corrections() -> None:
    entity = MemoryEntityRecord(
        entity_id="entity-a",
        domain_type="product",
        label="Camera Lens",
        confidence=0.75,
        observations=[
            MemoryObservation(
                observation_id="obs-a",
                source="template",
                confidence=0.6,
                notes="Created from product template",
                observed_at="2026-01-01T00:00:00+00:00",
            )
        ],
        lifecycle_events=[
            MemoryLifecycleEvent(
                event_id="event-a",
                event_type="reinforced",
                from_state="candidate",
                to_state="confirmed",
                confidence_before=0.6,
                confidence_after=0.75,
                reason="User confirmed product",
                created_at="2026-01-02T00:00:00+00:00",
            )
        ],
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-02T00:00:00+00:00",
    )
    corrections = [
        CorrectionLogRecord(
            correction_id="correction-a",
            operation_type="not_this",
            target_entity_id="entity-a",
            summary="Marked a candidate as wrong",
            created_at="2026-01-03T00:00:00+00:00",
        )
    ]

    ledger = build_confidence_ledger(entity=entity, corrections=corrections)

    assert ledger["current_confidence"] == 0.75
    assert len(ledger["entries"]) == 4
    assert ledger["summary"]["negative_events"] == 1


def test_domain_active_learning_asks_domain_specific_questions() -> None:
    entity = MemoryEntityRecord(
        entity_id="entity-a",
        domain_type="inventory",
        label="Tripod Stock",
        attributes={"quantity": "", "storage_location": ""},
        confidence=0.4,
        lifecycle_state="candidate",
    )

    drafts = DomainActiveLearningPlanner().draft_questions(entity)

    assert len(drafts) == 2
    assert "quantity" in drafts[0].prompt.lower()
    assert drafts[0].suggested_action == "fill_missing_memory_fields"
    assert drafts[1].suggested_action == "confirm_or_correct_memory"


def test_provider_conformance_reports_privacy_and_setup_gaps() -> None:
    card = ProviderCard(
        provider_id="remote-unknown",
        display_name="Remote Unknown",
        mode="local_free",
        capabilities=["ocr"],
        status="manifest_ready",
        images_leave_device=True,
        privacy_notes="",
        cost_model="",
        setup="",
    )

    report = evaluate_provider_conformance(card)

    assert report["passed"] is False
    assert report["summary"]["errors"] == 2
    assert report["summary"]["warnings"] >= 2


def test_benchmark_pack_is_metadata_only() -> None:
    pack = build_benchmark_pack()

    assert pack["case_count"] >= 5
    assert pack["redaction"]["raw_images"] == "not_included"
    assert all("description" in case for case in pack["cases"])


def test_memory_search_matches_label_tags_notes_and_attributes() -> None:
    entities = [
        MemoryEntityRecord(
            entity_id="entity-a",
            domain_type="product",
            label="Camera Lens",
            attributes={"brand": "DemoOptics", "model_or_sku": "DX-50"},
            tags=["photography"],
            notes="Used on the lab camera",
            confidence=0.8,
        ),
        MemoryEntityRecord(
            entity_id="entity-b",
            domain_type="place",
            label="Workshop",
            confidence=0.7,
        ),
    ]

    result = search_memory_entities(entities=entities, query="DX-50", domain_type="product")

    assert result["result_count"] == 1
    assert result["results"][0]["entity_id"] == "entity-a"
    assert "attributes" in result["results"][0]["matched_fields"]


def test_memory_detail_summarizes_related_questions_and_corrections() -> None:
    entity = MemoryEntityRecord(entity_id="entity-a", domain_type="inventory", label="Tripods")
    correction = CorrectionLogRecord(
        correction_id="correction-a",
        operation_type="rename",
        target_entity_id="entity-a",
        summary="Renamed memory",
        created_at="2026-01-03T00:00:00+00:00",
    )
    question = type(
        "Question",
        (),
        {"context": {"entity_id": "entity-a"}, "status": "pending"},
    )()

    detail = build_memory_entity_detail(
        entity=entity,
        corrections=[correction],
        active_learning_questions=[question],
    )

    assert detail["summary"]["correction_count"] == 1
    assert detail["summary"]["pending_question_count"] == 1
    assert detail["confidence_ledger"]["entity_id"] == "entity-a"


def test_benchmark_run_registry_persists_sanitized_snapshots(tmp_path) -> None:
    registry = BenchmarkRunRegistry(tmp_path / "runs.json")

    record = registry.add_run(
        label="Local baseline",
        notes="first run",
        benchmark_case_ids=["product-sku-memory"],
        provider_selections={"face_embedding": "local-face-embedding"},
        metrics={"estimated_precision": 0.8, "secret_metric": "nope"},
    )

    runs = registry.list_runs()

    assert runs[0].run_id == record.run_id
    assert runs[0].metrics == {"estimated_precision": 0.8}
