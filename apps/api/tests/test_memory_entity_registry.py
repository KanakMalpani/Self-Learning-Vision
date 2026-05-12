from __future__ import annotations

from pathlib import Path

from app.services.memory_entity_registry import MemoryEntityRegistry, MemoryObservation


def test_memory_entity_registry_creates_custom_domain_entity(tmp_path: Path) -> None:
    registry = MemoryEntityRegistry(tmp_path / "entities.json")

    entity = registry.upsert_entity(
        domain_type="Tool/Device",
        label="Thermal Camera",
        attributes={"serial_number": "demo-123", "room": "Lab"},
        user_schema={"fields": {"serial_number": "string", "room": "string"}},
        aliases=["IR Camera", "IR Camera"],
        tags=["hardware", "vision", "hardware"],
        notes="Used for night experiments",
        confidence=0.82,
        lifecycle_state="confirmed",
    )

    assert entity.domain_type == "tool_device"
    assert entity.label == "Thermal Camera"
    assert entity.attributes["room"] == "Lab"
    assert entity.aliases == ["IR Camera"]
    assert entity.tags == ["hardware", "vision"]
    assert entity.confidence == 0.82
    assert entity.lifecycle_state == "confirmed"
    assert registry.entity_count("tool_device") == 1
    assert "tool_device" in registry.list_domain_types()


def test_memory_entity_registry_upserts_by_domain_and_label(tmp_path: Path) -> None:
    registry = MemoryEntityRegistry(tmp_path / "entities.json")

    first = registry.upsert_entity(
        domain_type="person",
        label="Ada",
        attributes={"source": "manual"},
        confidence=0.5,
        source_reference_id="ref-a",
    )
    second = registry.upsert_entity(
        domain_type="person",
        label="Ada",
        attributes={"seen_count": 2},
        confidence=0.9,
        source_reference_id="ref-b",
        observation=MemoryObservation(
            observation_id="obs-a",
            source="face_reference",
            source_id="upload-a",
            modality="face",
            confidence=0.9,
            notes="confirmed",
        ),
    )
    third = registry.upsert_entity(
        domain_type="person",
        label="Ada",
        observation=MemoryObservation(
            observation_id="obs-a",
            source="face_reference",
            source_id="upload-a",
            modality="face",
            confidence=0.9,
            notes="confirmed",
        ),
    )

    assert first.entity_id == second.entity_id
    assert third.entity_id == second.entity_id
    assert second.attributes["source"] == "manual"
    assert second.attributes["seen_count"] == 2
    assert second.confidence == 0.9
    assert second.source_reference_ids == ["ref-a", "ref-b"]
    assert len(third.observations) == 1
    assert registry.entity_count("person") == 1


def test_memory_entity_registry_updates_editable_fields(tmp_path: Path) -> None:
    registry = MemoryEntityRegistry(tmp_path / "entities.json")
    entity = registry.upsert_entity(
        domain_type="product",
        label="Lens",
        attributes={"brand": "Old"},
        tags=["camera"],
        confidence=0.5,
    )

    updated = registry.update_entity(
        entity_id=entity.entity_id,
        attributes={"brand": "New", "sku": "L-50"},
        tags=["optics"],
        notes="clean copy",
        confidence=0.8,
        lifecycle_state="confirmed",
    )

    assert updated is not None
    assert updated.attributes == {"brand": "New", "sku": "L-50"}
    assert updated.tags == ["optics"]
    assert updated.notes == "clean copy"
    assert updated.confidence == 0.8
    assert updated.lifecycle_state == "confirmed"


def test_memory_entity_registry_keeps_same_label_separate_across_domains(tmp_path: Path) -> None:
    registry = MemoryEntityRegistry(tmp_path / "entities.json")

    person = registry.upsert_entity(domain_type="person", label="Phoenix", confidence=0.7)
    place = registry.upsert_entity(domain_type="place", label="Phoenix", confidence=0.6)

    assert person.entity_id != place.entity_id
    assert registry.entity_count("person") == 1
    assert registry.entity_count("place") == 1
    assert registry.find_by_label(domain_type="person", label="Phoenix") == person
    assert registry.find_by_label(domain_type="place", label="Phoenix") == place
