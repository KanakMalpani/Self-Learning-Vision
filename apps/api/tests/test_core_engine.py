from __future__ import annotations

from pathlib import Path

from app.schemas.api import FaceBox
from app.schemas.memory_report import FaceAssessment
from app.services.core_engine import RecognitionCoreService
from app.services.face_detection import FaceDetectionService
from app.services.face_reference_registry import FaceReferenceRegistry
from app.services.recognition import FaceEmbeddingProvider, stable_reference_embedding


class _StaticFaceDetectionService(FaceDetectionService):
    def __init__(self, face_boxes: list[FaceBox]) -> None:
        super().__init__()
        self._face_boxes = face_boxes

    def detect_faces(self, image_path: str):  # type: ignore[override]
        return list(self._face_boxes)


class _ConditionalEmbeddingProvider(FaceEmbeddingProvider):
    name = "local-face-embedding"

    def __init__(self, mapping: dict[tuple[float, float, float, float], list[float]]) -> None:
        self._mapping = mapping

    def extract_embedding(self, image_path: str, face_box: dict) -> list[float] | None:
        key = (
            round(float(face_box.get("x", 0.0)), 3),
            round(float(face_box.get("y", 0.0)), 3),
            round(float(face_box.get("width", 0.0)), 3),
            round(float(face_box.get("height", 0.0)), 3),
        )
        return self._mapping.get(key)


class _StaticQualityAssessor:
    def __init__(self, assessment: FaceAssessment) -> None:
        self._assessment = assessment

    def assess_faces(self, image_path: str, face_boxes: list[dict]) -> list[FaceAssessment]:
        _ = image_path
        return [self._assessment.model_copy(update={"face_index": index}) for index, _box in enumerate(face_boxes)]


def _quality(score: float = 0.9, flags: list[str] | None = None, detector_confidence: float = 0.95) -> FaceAssessment:
    return FaceAssessment(
        face_index=0,
        detector_confidence=detector_confidence,
        blur_score=score,
        box_size_ratio=0.2,
        pose_score=score,
        occlusion_score=score,
        face_quality_score=score,
        face_quality_flags=flags or [],
    )


def test_core_engine_enrolls_identity_into_local_registry(tmp_path: Path) -> None:
    registry = FaceReferenceRegistry(tmp_path / "references.json")
    face_boxes = [FaceBox(x=0.1, y=0.1, width=0.4, height=0.4, score=0.98)]
    provider = _ConditionalEmbeddingProvider({(0.1, 0.1, 0.4, 0.4): stable_reference_embedding("ada")})
    engine = RecognitionCoreService(
        detection_service=_StaticFaceDetectionService(face_boxes),
        reference_registry=registry,
        embedding_provider=provider,
        accept_threshold=0.72,
    )

    record, detected_faces, embedding = engine.enroll_identity(
        name_or_alias="Ada Lovelace",
        image_path=str(tmp_path / "frame.jpg"),
        selected_face_index=0,
        notes="met at a conference",
        tags=["trusted", "vip", "trusted"],
    )

    assert record.name_or_alias == "Ada Lovelace"
    assert detected_faces[0].score == 0.98
    assert embedding
    assert engine.reference_count == 1
    stored = registry.list_records()[0]
    assert stored.name_or_alias == "Ada Lovelace"
    assert stored.tags == ["trusted", "vip"]
    assert stored.seen_count == 0
    assert stored.last_seen_at is None


def test_core_engine_matches_known_face_and_rejects_weak_match(tmp_path: Path) -> None:
    registry = FaceReferenceRegistry(tmp_path / "references.json")
    registry.add_reference(
        name_or_alias="Ada Lovelace",
        embedding=stable_reference_embedding("ada"),
        provider="local-face-embedding",
    )

    face_boxes = [FaceBox(x=0.1, y=0.1, width=0.4, height=0.4, score=0.98)]
    engine = RecognitionCoreService(
        detection_service=_StaticFaceDetectionService(face_boxes),
        reference_registry=registry,
        embedding_provider=_ConditionalEmbeddingProvider({(0.1, 0.1, 0.4, 0.4): stable_reference_embedding("ada")}),
        accept_threshold=0.72,
    )

    match = engine.match_face(image_path=str(tmp_path / "frame.jpg"), selected_face_index=0)

    assert match.status == "matched"
    assert match.top_candidate_name == "Ada Lovelace"
    assert match.confidence >= 0.72
    assert "seen 1 times" in match.reason
    assert match.memory_summary == "Seen 1 time(s)"
    assert match.seen_count == 1
    assert match.last_seen_at is not None
    refreshed = registry.list_records()[0]
    assert refreshed.seen_count == 1
    assert refreshed.last_seen_at is not None

    weak_engine = RecognitionCoreService(
        detection_service=_StaticFaceDetectionService(face_boxes),
        reference_registry=registry,
        embedding_provider=_ConditionalEmbeddingProvider({(0.1, 0.1, 0.4, 0.4): stable_reference_embedding("other")}),
        accept_threshold=0.72,
        tentative_threshold=0.72,
    )

    weak_match = weak_engine.match_face(image_path=str(tmp_path / "frame.jpg"), selected_face_index=0)

    assert weak_match.status == "unknown"
    assert weak_match.top_candidate_name is None
    assert weak_match.confidence == 0.0
    assert weak_match.embedding
    assert weak_match.embedding_provider == "local-face-embedding"
    assert weak_match.quality_score is not None
    assert registry.list_records()[0].seen_count == 1


def test_core_engine_returns_tentative_without_marking_seen(tmp_path: Path) -> None:
    registry = FaceReferenceRegistry(tmp_path / "references.json")
    registry.add_reference(
        name_or_alias="Ada Lovelace",
        embedding=stable_reference_embedding("ada"),
        provider="local-face-embedding",
    )

    face_boxes = [FaceBox(x=0.1, y=0.1, width=0.4, height=0.4, score=0.98)]
    engine = RecognitionCoreService(
        detection_service=_StaticFaceDetectionService(face_boxes),
        reference_registry=registry,
        embedding_provider=_ConditionalEmbeddingProvider({(0.1, 0.1, 0.4, 0.4): stable_reference_embedding("ada")}),
        accept_threshold=1.01,
        tentative_threshold=0.50,
    )

    result = engine.match_face(image_path=str(tmp_path / "frame.jpg"), selected_face_index=0)

    assert result.status == "tentative"
    assert result.top_candidate_name == "Ada Lovelace"
    assert result.confidence >= 0.50
    assert "Possible local match" in result.reason
    assert registry.list_records()[0].seen_count == 0


def test_core_engine_returns_memory_recall_fields_for_matched_identity(tmp_path: Path) -> None:
    registry = FaceReferenceRegistry(tmp_path / "references.json")
    registry.add_reference(
        name_or_alias="Maya",
        embedding=stable_reference_embedding("maya"),
        provider="local-face-embedding",
        notes="met at hackathon",
        tags=["builder", "friend"],
    )

    face_boxes = [FaceBox(x=0.1, y=0.1, width=0.4, height=0.4, score=0.98)]
    engine = RecognitionCoreService(
        detection_service=_StaticFaceDetectionService(face_boxes),
        reference_registry=registry,
        embedding_provider=_ConditionalEmbeddingProvider({(0.1, 0.1, 0.4, 0.4): stable_reference_embedding("maya")}),
        accept_threshold=0.72,
    )

    result = engine.match_face(image_path=str(tmp_path / "frame.jpg"), selected_face_index=0)

    assert result.status == "matched"
    assert result.top_candidate_name == "Maya"
    assert result.memory_summary == "met at hackathon"
    assert result.notes == "met at hackathon"
    assert result.tags == ["builder", "friend"]
    assert result.seen_count == 1
    assert result.last_seen_at is not None


def test_core_engine_rejects_low_quality_faces_before_embedding(tmp_path: Path) -> None:
    registry = FaceReferenceRegistry(tmp_path / "references.json")
    registry.add_reference(
        name_or_alias="Ada Lovelace",
        embedding=stable_reference_embedding("ada"),
        provider="local-face-embedding",
    )

    face_boxes = [FaceBox(x=0.1, y=0.1, width=0.4, height=0.4, score=0.98)]
    provider = _ConditionalEmbeddingProvider({(0.1, 0.1, 0.4, 0.4): stable_reference_embedding("ada")})
    engine = RecognitionCoreService(
        detection_service=_StaticFaceDetectionService(face_boxes),
        quality_assessor=_StaticQualityAssessor(_quality(0.25, flags=["blurry"])),
        reference_registry=registry,
        embedding_provider=provider,
        accept_threshold=0.72,
    )

    result = engine.match_face(image_path=str(tmp_path / "frame.jpg"), selected_face_index=0)

    assert result.status == "unknown"
    assert result.confidence == 0.0
    assert "blurry" in result.reason
    assert registry.list_records()[0].seen_count == 0

    try:
        engine.enroll_identity(
            name_or_alias="Grace Hopper",
            image_path=str(tmp_path / "frame.jpg"),
            selected_face_index=0,
        )
    except ValueError as exc:
        assert "Face quality too low" in str(exc)
    else:
        raise AssertionError("Low-quality enrollment should be rejected")


def test_core_engine_scans_multiple_faces_without_forcing_false_positives(tmp_path: Path) -> None:
    registry = FaceReferenceRegistry(tmp_path / "references.json")
    registry.add_reference(
        name_or_alias="Ada Lovelace",
        embedding=stable_reference_embedding("ada"),
        provider="local-face-embedding",
    )

    face_boxes = [
        FaceBox(x=0.1, y=0.1, width=0.35, height=0.35, score=0.98),
        FaceBox(x=0.6, y=0.1, width=0.35, height=0.35, score=0.98),
    ]
    provider = _ConditionalEmbeddingProvider(
        {
            (0.1, 0.1, 0.35, 0.35): stable_reference_embedding("ada"),
            (0.6, 0.1, 0.35, 0.35): stable_reference_embedding("other"),
        }
    )
    engine = RecognitionCoreService(
        detection_service=_StaticFaceDetectionService(face_boxes),
        reference_registry=registry,
        embedding_provider=provider,
        accept_threshold=0.72,
        tentative_threshold=0.72,
    )

    results = engine.analyze_image(image_path=str(tmp_path / "frame.jpg"))

    assert len(results) == 2
    assert results[0].status == "matched"
    assert results[0].top_candidate_name == "Ada Lovelace"
    assert results[1].status == "unknown"
    assert results[1].top_candidate_name is None

