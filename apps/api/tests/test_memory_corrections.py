from __future__ import annotations

from pathlib import Path

from app.services.correction_log_registry import CorrectionLogRegistry
from app.services.memory_entity_registry import MemoryEntityRegistry, MemoryObservation


def test_memory_entity_rename_and_undo_snapshot(tmp_path: Path) -> None:
    entities = MemoryEntityRegistry(tmp_path / "entities.json")
    corrections = CorrectionLogRegistry(tmp_path / "corrections.json")
    entity = entities.upsert_entity(domain_type="person", label="Ada", tags=["math"], confidence=0.8)

    before = entities.snapshot()
    renamed = entities.rename_entity(entity_id=entity.entity_id, label="Ada Lovelace")
    assert renamed is not None
    after = entities.snapshot()
    correction = corrections.add_record(
        operation_type="rename",
        target_entity_id=entity.entity_id,
        summary="Renamed entity",
        before_entities=before,
        after_entities=after,
    )

    assert entities.find(entity.entity_id).label == "Ada Lovelace"  # type: ignore[union-attr]
    entities.restore_snapshot(correction.before_entities)
    corrections.mark_undone(correction.correction_id)

    restored = entities.find(entity.entity_id)
    assert restored is not None
    assert restored.label == "Ada"
    assert corrections.find(correction.correction_id).undone is True  # type: ignore[union-attr]


def test_memory_entity_not_this_marks_uncertain_with_rejected_label(tmp_path: Path) -> None:
    registry = MemoryEntityRegistry(tmp_path / "entities.json")
    entity = registry.upsert_entity(domain_type="person", label="Maya", confidence=0.7)

    updated = registry.mark_not_this(
        entity_id=entity.entity_id,
        rejected_label="Ada",
        notes="The tentative match was wrong",
    )

    assert updated is not None
    assert updated.lifecycle_state == "uncertain"
    assert updated.attributes["rejected_labels"] == ["Ada"]
    assert updated.observations[-1].source == "correction"


def test_memory_entity_merge_archives_sources_and_combines_context(tmp_path: Path) -> None:
    registry = MemoryEntityRegistry(tmp_path / "entities.json")
    target = registry.upsert_entity(
        domain_type="person",
        label="Ada",
        tags=["math"],
        source_reference_id="ref-a",
        confidence=0.7,
    )
    source = registry.upsert_entity(
        domain_type="person",
        label="A. Lovelace",
        tags=["writer"],
        source_reference_id="ref-b",
        confidence=0.9,
    )

    merged = registry.merge_entities(
        target_entity_id=target.entity_id,
        source_entity_ids=[source.entity_id],
        notes="same person",
    )

    assert merged is not None
    assert merged.label == "Ada"
    assert "A. Lovelace" in merged.aliases
    assert merged.tags == ["math", "writer"]
    assert merged.source_reference_ids == ["ref-a", "ref-b"]
    assert merged.confidence == 0.9
    archived = registry.find(source.entity_id)
    assert archived is not None
    assert archived.lifecycle_state == "archived"
    assert archived.attributes["merged_into_entity_id"] == target.entity_id


def test_memory_entity_split_moves_selected_observations(tmp_path: Path) -> None:
    registry = MemoryEntityRegistry(tmp_path / "entities.json")
    entity = registry.upsert_entity(
        domain_type="object",
        label="Camera",
        observation=MemoryObservation(
            observation_id="obs-a",
            source="manual",
            modality="vision",
            notes="front camera",
        ),
    )
    registry.add_observation(
        entity_id=entity.entity_id,
        source="manual",
        modality="vision",
        notes="thermal camera",
    )
    refreshed = registry.find(entity.entity_id)
    assert refreshed is not None
    moved_id = refreshed.observations[-1].observation_id

    result = registry.split_entity(
        entity_id=entity.entity_id,
        new_label="Thermal Camera",
        observation_ids=[moved_id],
    )

    assert result is not None
    original, new_entity = result
    assert original.lifecycle_state == "uncertain"
    assert all(item.observation_id != moved_id for item in original.observations)
    assert new_entity.label == "Thermal Camera"
    assert new_entity.observations[0].observation_id == moved_id
    assert new_entity.attributes["split_from_entity_id"] == entity.entity_id
