from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.services.memory_entity_registry import MemoryEntityRegistry, MemoryObservation


def test_reinforce_entity_raises_confidence_and_records_event(tmp_path: Path) -> None:
    registry = MemoryEntityRegistry(tmp_path / "entities.json")
    entity = registry.upsert_entity(domain_type="person", label="Ada", confidence=0.7)

    reinforced = registry.reinforce_entity(
        entity_id=entity.entity_id,
        amount=0.2,
        reason="user confirmed",
    )

    assert reinforced is not None
    assert reinforced.lifecycle_state == "confirmed"
    assert reinforced.confidence == 0.9
    assert reinforced.lifecycle_events[-1].event_type == "reinforced"
    assert reinforced.lifecycle_events[-1].confidence_before == 0.7
    assert reinforced.lifecycle_events[-1].confidence_after == 0.9


def test_record_contradiction_lowers_confidence_and_marks_uncertain(tmp_path: Path) -> None:
    registry = MemoryEntityRegistry(tmp_path / "entities.json")
    entity = registry.upsert_entity(
        domain_type="person",
        label="Maya",
        confidence=0.8,
        lifecycle_state="confirmed",
    )

    updated = registry.record_contradiction(
        entity_id=entity.entity_id,
        rejected_label="Ada",
        amount=0.25,
        reason="wrong match",
    )

    assert updated is not None
    assert updated.lifecycle_state == "uncertain"
    assert updated.confidence == 0.55
    assert updated.attributes["contradictions"][0]["rejected_label"] == "Ada"
    assert updated.lifecycle_events[-1].event_type == "contradiction"


def test_decay_stale_entities_only_affects_old_active_memories(tmp_path: Path) -> None:
    registry = MemoryEntityRegistry(tmp_path / "entities.json")
    old_time = datetime.now(UTC) - timedelta(days=90)
    fresh_time = datetime.now(UTC) - timedelta(days=2)
    old = registry.upsert_entity(
        domain_type="object",
        label="Old Camera",
        confidence=0.8,
        lifecycle_state="confirmed",
        observation=MemoryObservation(
            observation_id="old-obs",
            source="manual",
            modality="vision",
            observed_at=old_time.isoformat(),
        ),
    )
    fresh = registry.upsert_entity(
        domain_type="object",
        label="Fresh Camera",
        confidence=0.8,
        lifecycle_state="confirmed",
        observation=MemoryObservation(
            observation_id="fresh-obs",
            source="manual",
            modality="vision",
            observed_at=fresh_time.isoformat(),
        ),
    )
    snapshot = registry.snapshot()
    for item in snapshot:
        if item["entity_id"] == old.entity_id:
            item["created_at"] = old_time.isoformat()
            item["updated_at"] = old_time.isoformat()
        if item["entity_id"] == fresh.entity_id:
            item["created_at"] = fresh_time.isoformat()
            item["updated_at"] = fresh_time.isoformat()
    registry.restore_snapshot(snapshot)

    decayed = registry.decay_stale_entities(stale_after_days=30, amount=0.1, now=datetime.now(UTC))

    assert [item.label for item in decayed] == ["Old Camera"]
    old_after = registry.find(old.entity_id)
    fresh_after = registry.find(fresh.entity_id)
    assert old_after is not None and fresh_after is not None
    assert old_after.lifecycle_state == "stale"
    assert old_after.confidence == 0.7
    assert fresh_after.lifecycle_state == "confirmed"
    assert fresh_after.confidence == 0.8


def test_lifecycle_summary_counts_states_domains_and_events(tmp_path: Path) -> None:
    registry = MemoryEntityRegistry(tmp_path / "entities.json")
    ada = registry.upsert_entity(domain_type="person", label="Ada", confidence=0.8)
    registry.upsert_entity(domain_type="place", label="Lab", confidence=0.6)
    registry.reinforce_entity(entity_id=ada.entity_id, amount=0.1)
    registry.record_contradiction(entity_id=ada.entity_id, rejected_label="Maya", amount=0.2)

    summary = registry.lifecycle_summary()

    assert summary["total_entities"] == 2
    assert summary["by_domain"]["person"] == 1
    assert summary["by_domain"]["place"] == 1
    assert summary["by_state"]["uncertain"] == 1
    assert summary["by_state"]["candidate"] == 1
    assert summary["contradictions"] == 1
    assert summary["lifecycle_events"] == 2
