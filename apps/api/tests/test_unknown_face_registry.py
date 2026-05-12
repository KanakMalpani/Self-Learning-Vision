from __future__ import annotations

from pathlib import Path

from app.services.recognition import stable_reference_embedding
from app.services.unknown_face_registry import UnknownFaceRegistry


def test_unknown_registry_clusters_similar_samples(tmp_path: Path) -> None:
    registry = UnknownFaceRegistry(
        tmp_path / "samples.json",
        cluster_similarity_threshold=0.80,
        familiarity_min_samples=2,
    )

    first = registry.add_sample(
        embedding=stable_reference_embedding("same-person"),
        source_upload_id="upload-a",
        face_index=0,
        quality_score=0.9,
        provider="local-face-embedding",
    )
    second = registry.add_sample(
        embedding=stable_reference_embedding("same-person"),
        source_upload_id="upload-b",
        face_index=0,
        quality_score=0.88,
        provider="local-face-embedding",
    )

    first_cluster = registry.find_cluster_for_sample(first.unknown_sample_id)
    second_cluster = registry.find_cluster_for_sample(second.unknown_sample_id)

    assert first_cluster is not None and second_cluster is not None
    assert first_cluster.unknown_cluster_id == second_cluster.unknown_cluster_id
    assert second_cluster.sighting_count == 2
    assert second_cluster.familiarity_state == "familiar"
    assert second_cluster.suggested_for_enrollment is True
    assert registry.suggested_clusters()[0].unknown_cluster_id == second_cluster.unknown_cluster_id


def test_unknown_registry_separates_different_samples_at_conservative_threshold(tmp_path: Path) -> None:
    registry = UnknownFaceRegistry(
        tmp_path / "samples.json",
        cluster_similarity_threshold=0.99,
        familiarity_min_samples=2,
    )

    registry.add_sample(
        embedding=stable_reference_embedding("person-a"),
        source_upload_id="upload-a",
        face_index=0,
        quality_score=0.9,
        provider="local-face-embedding",
    )
    registry.add_sample(
        embedding=stable_reference_embedding("person-b"),
        source_upload_id="upload-b",
        face_index=0,
        quality_score=0.9,
        provider="local-face-embedding",
    )

    clusters = registry.list_clusters()

    assert len(clusters) == 2
    assert all(cluster.sighting_count == 1 for cluster in clusters)
    assert all(cluster.suggested_for_enrollment is False for cluster in clusters)


def test_unknown_registry_dedupes_same_upload_face_without_incrementing_cluster(tmp_path: Path) -> None:
    registry = UnknownFaceRegistry(tmp_path / "samples.json")

    first = registry.add_sample(
        embedding=stable_reference_embedding("same-person"),
        source_upload_id="upload-a",
        face_index=0,
        quality_score=0.9,
        provider="local-face-embedding",
    )
    second = registry.add_sample(
        embedding=stable_reference_embedding("same-person"),
        source_upload_id="upload-a",
        face_index=0,
        quality_score=0.9,
        provider="local-face-embedding",
    )

    assert first.unknown_sample_id == second.unknown_sample_id
    assert registry.sample_count() == 1
    assert registry.cluster_count() == 1
    assert registry.list_clusters()[0].sighting_count == 1


def test_unknown_registry_marks_promoted_cluster_out_of_suggestions(tmp_path: Path) -> None:
    registry = UnknownFaceRegistry(tmp_path / "samples.json", familiarity_min_samples=2)
    registry.add_sample(
        embedding=stable_reference_embedding("same-person"),
        source_upload_id="upload-a",
        face_index=0,
        quality_score=0.9,
        provider="local-face-embedding",
    )
    second = registry.add_sample(
        embedding=stable_reference_embedding("same-person"),
        source_upload_id="upload-b",
        face_index=0,
        quality_score=0.9,
        provider="local-face-embedding",
    )
    cluster = registry.find_cluster_for_sample(second.unknown_sample_id)
    assert cluster is not None
    assert registry.suggested_clusters()

    promoted = registry.mark_cluster_promoted(cluster.unknown_cluster_id)

    assert promoted is not None
    assert promoted.promoted is True
    assert promoted.suggested_for_enrollment is False
    assert promoted.familiarity_state == "promoted"
    assert registry.suggested_clusters() == []

