from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from app.core.config import settings
from app.schemas.api import FaceBox
from app.schemas.memory_report import IdentityCandidate
from app.services.face_detection import FaceDetectionService
from app.services.face_reference_registry import FaceReferenceRecord, FaceReferenceRegistry
from app.services.recognition import (
    EmbeddingMatcher,
    FaceEmbeddingProvider,
    FaceQualityAssessor,
    InsightFaceEmbeddingProvider,
    LocalFaceEmbeddingProvider,
)


@dataclass(frozen=True)
class FaceRecognitionResult:
    face_index: int | None
    face_box: FaceBox | None
    status: Literal["matched", "tentative", "unknown"]
    confidence: float
    top_candidate_name: str | None = None
    top_candidate_provider: str | None = None
    top_candidate: IdentityCandidate | None = None
    candidates: list[IdentityCandidate] = field(default_factory=list)
    embedding_dimensions: int = 0
    reason: str = ""
    reference_id: str | None = None
    memory_summary: str | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    seen_count: int | None = None
    last_seen_at: str | None = None
    embedding: list[float] = field(default_factory=list)
    embedding_provider: str | None = None
    quality_score: float | None = None


class RecognitionCoreService:
    """High-level face pipeline for detection, enrollment, and conservative matching."""

    def __init__(
        self,
        *,
        detection_service: FaceDetectionService | None = None,
        quality_assessor: FaceQualityAssessor | None = None,
        reference_registry: FaceReferenceRegistry | None = None,
        reference_registry_factory: Callable[[], FaceReferenceRegistry] | None = None,
        embedding_provider: FaceEmbeddingProvider | None = None,
        embedding_provider_factory: Callable[[], FaceEmbeddingProvider | None] | None = None,
        accept_threshold: float | None = None,
        tentative_threshold: float | None = None,
        min_quality_threshold: float | None = None,
        top_k: int | None = None,
    ) -> None:
        self._detection_service = detection_service or FaceDetectionService()
        self._quality_assessor = quality_assessor or FaceQualityAssessor()
        self._reference_registry = reference_registry or FaceReferenceRegistry(
            Path(settings.storage_dir) / "face-reference-registry.json"
        )
        self._reference_registry_factory = reference_registry_factory
        self._embedding_provider = embedding_provider
        self._embedding_provider_factory = embedding_provider_factory
        self._accept_threshold = accept_threshold if accept_threshold is not None else settings.recognition_accept_threshold
        self._tentative_threshold = (
            tentative_threshold if tentative_threshold is not None else settings.recognition_tentative_threshold
        )
        self._min_quality_threshold = (
            min_quality_threshold if min_quality_threshold is not None else settings.face_quality_min_threshold
        )
        self._top_k = max(1, int(top_k or settings.recognition_top_k))

    @property
    def reference_count(self) -> int:
        return self._get_reference_registry().reference_count()

    def detect_faces(self, image_path: str) -> list[FaceBox]:
        return self._detection_service.detect_faces(image_path)

    def list_references(self) -> list[FaceReferenceRecord]:
        return self._get_reference_registry().list_records()

    def enroll_identity(
        self,
        *,
        name_or_alias: str,
        image_path: str,
        selected_face_index: int = 0,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> tuple[FaceReferenceRecord, list[FaceBox], list[float]]:
        face_boxes = self.detect_faces(image_path)
        if not face_boxes:
            raise ValueError("No face detected in reference image")
        if selected_face_index < 0 or selected_face_index >= len(face_boxes):
            raise IndexError("selected_face_index is out of range")

        record, embedding = self.enroll_identity_from_face_box(
            name_or_alias=name_or_alias,
            image_path=image_path,
            face_box=face_boxes[selected_face_index],
            face_index=selected_face_index,
            notes=notes,
            tags=tags,
        )
        return record, face_boxes, embedding

    def enroll_identity_from_face_box(
        self,
        *,
        name_or_alias: str,
        image_path: str,
        face_box: FaceBox | dict[str, object],
        face_index: int = 0,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> tuple[FaceReferenceRecord, list[float]]:
        provider = self._get_embedding_provider()
        if provider is None:
            raise RuntimeError("Face embedding provider unavailable")

        face_payload = self._face_box_payload(face_box)
        quality = self._assess_selected_face(image_path=image_path, face_box=face_payload)
        if not self._passes_quality_gate(quality):
            raise ValueError(self._quality_rejection_reason(quality))

        embedding = provider.extract_embedding(image_path, face_payload)
        if not embedding:
            raise ValueError("Could not extract an embedding from the selected face")

        record = self._get_reference_registry().add_reference(
            name_or_alias=name_or_alias,
            embedding=embedding,
            provider=provider.name,
            source_image_path=image_path,
            face_index=face_index,
            notes=notes,
            tags=tags,
        )
        return record, embedding

    def match_face(self, *, image_path: str, selected_face_index: int = 0) -> FaceRecognitionResult:
        face_boxes = self.detect_faces(image_path)
        if not face_boxes:
            return FaceRecognitionResult(
                face_index=None,
                face_box=None,
                status="unknown",
                confidence=0.0,
                reason="No face detected",
            )
        if selected_face_index < 0 or selected_face_index >= len(face_boxes):
            return FaceRecognitionResult(
                face_index=selected_face_index,
                face_box=None,
                status="unknown",
                confidence=0.0,
                reason="Selected face index is out of range",
            )

        return self._match_single_face(image_path=image_path, face_index=selected_face_index, face_box=face_boxes[selected_face_index])

    def match_face_box(
        self,
        *,
        image_path: str,
        face_box: FaceBox | dict[str, object],
        face_index: int = 0,
    ) -> FaceRecognitionResult:
        payload = self._face_box_payload(face_box)
        return self._match_single_face(
            image_path=image_path,
            face_index=face_index,
            face_box=FaceBox(**payload),
        )

    def analyze_image(self, *, image_path: str) -> list[FaceRecognitionResult]:
        face_boxes = self.detect_faces(image_path)
        if not face_boxes:
            return []

        return [
            self._match_single_face(image_path=image_path, face_index=index, face_box=face_box)
            for index, face_box in enumerate(face_boxes)
        ]

    def _match_single_face(self, *, image_path: str, face_index: int, face_box: FaceBox) -> FaceRecognitionResult:
        provider = self._get_embedding_provider()
        if provider is None:
            return FaceRecognitionResult(
                face_index=face_index,
                face_box=face_box,
                status="unknown",
                confidence=0.0,
                reason="Face embedding provider unavailable",
            )

        face_payload = self._face_box_payload(face_box)
        quality = self._assess_selected_face(image_path=image_path, face_box=face_payload)
        if not self._passes_quality_gate(quality):
            return FaceRecognitionResult(
                face_index=face_index,
                face_box=face_box,
                status="unknown",
                confidence=0.0,
                quality_score=self._quality_score(quality),
                reason=self._quality_rejection_reason(quality),
            )

        embedding = provider.extract_embedding(image_path, face_payload)
        if not embedding:
            return FaceRecognitionResult(
                face_index=face_index,
                face_box=face_box,
                status="unknown",
                confidence=0.0,
                quality_score=self._quality_score(quality),
                reason="Could not extract an embedding for the selected face",
            )

        matcher = EmbeddingMatcher(
            provider=provider,
            reference_embeddings_json=self._get_reference_registry().reference_embeddings_json(),
        )
        candidates = matcher.build_candidates(
            image_path,
            {
                **face_payload,
                "multi_frame_embedding": embedding,
            },
        )
        if not candidates:
            return FaceRecognitionResult(
                face_index=face_index,
                face_box=face_box,
                status="unknown",
                confidence=0.0,
                candidates=[],
                embedding_dimensions=len(embedding),
                embedding=embedding,
                embedding_provider=provider.name,
                quality_score=self._quality_score(quality),
                reason="No stored identities available",
            )

        top_candidate = candidates[0]
        accepted = top_candidate.raw_confidence >= self._accept_threshold
        tentative = not accepted and top_candidate.raw_confidence >= self._tentative_threshold
        matched_record = None
        if accepted:
            matched_record = self._get_reference_registry().mark_seen(name_or_alias=top_candidate.name_or_alias)
        elif tentative:
            matched_record = self._get_reference_registry().find_by_name(name_or_alias=top_candidate.name_or_alias)
        return FaceRecognitionResult(
            face_index=face_index,
            face_box=face_box,
            status="matched" if accepted else ("tentative" if tentative else "unknown"),
            confidence=top_candidate.raw_confidence if (accepted or tentative) else 0.0,
            top_candidate_name=top_candidate.name_or_alias if (accepted or tentative) else None,
            top_candidate_provider=top_candidate.provider if (accepted or tentative) else None,
            top_candidate=top_candidate if (accepted or tentative) else None,
            candidates=candidates[: self._top_k],
            embedding_dimensions=len(embedding),
            embedding=embedding,
            embedding_provider=provider.name,
            quality_score=self._quality_score(quality),
            reason=(
                f"Matched stored identity; seen {matched_record.seen_count} times"
                if accepted and matched_record is not None
                else (
                    "Matched stored identity"
                    if accepted
                    else (
                        "Possible local match below the conservative acceptance threshold"
                        if tentative
                        else "Best match fell below the conservative tentative threshold"
                    )
                )
            ),
            reference_id=matched_record.reference_id if matched_record else None,
            memory_summary=self._memory_summary(matched_record),
            notes=matched_record.notes if matched_record else None,
            tags=list(matched_record.tags or []) if matched_record else [],
            seen_count=matched_record.seen_count if matched_record else None,
            last_seen_at=matched_record.last_seen_at if matched_record else None,
        )

    def _face_box_payload(self, face_box: FaceBox | dict[str, object]) -> dict[str, object]:
        if isinstance(face_box, FaceBox):
            return face_box.model_dump()
        return dict(face_box)

    def _assess_selected_face(self, *, image_path: str, face_box: dict[str, object]):
        assessments = self._quality_assessor.assess_faces(image_path, [face_box])
        return assessments[0] if assessments else None

    def _passes_quality_gate(self, assessment: object | None) -> bool:
        if assessment is None:
            return False
        quality = float(getattr(assessment, "face_quality_score", 0.0))
        detector_confidence = float(getattr(assessment, "detector_confidence", 0.0))
        return quality >= self._min_quality_threshold and detector_confidence >= 0.4

    def _quality_rejection_reason(self, assessment: object | None) -> str:
        if assessment is None:
            return "Face quality could not be assessed"
        flags = list(getattr(assessment, "face_quality_flags", []) or [])
        quality = float(getattr(assessment, "face_quality_score", 0.0))
        if flags:
            return f"Face quality too low for reliable recognition: {', '.join(flags)}"
        return f"Face quality too low for reliable recognition: score {quality:.2f}"

    def _quality_score(self, assessment: object | None) -> float | None:
        if assessment is None:
            return None
        return round(float(getattr(assessment, "face_quality_score", 0.0)), 6)

    def _memory_summary(self, record: FaceReferenceRecord | None) -> str | None:
        if record is None:
            return None
        if record.notes and record.notes.strip():
            return record.notes.strip()
        if record.tags:
            return ", ".join(record.tags)
        if record.seen_count > 0:
            return f"Seen {record.seen_count} time(s)"
        return "Saved in local memory"

    def _get_embedding_provider(self) -> FaceEmbeddingProvider | None:
        if self._embedding_provider is not None:
            return self._embedding_provider

        if self._embedding_provider_factory is not None:
            provider = self._embedding_provider_factory()
            if provider is not None:
                self._embedding_provider = provider
                return provider

        if settings.enable_face_matching:
            provider = InsightFaceEmbeddingProvider()
            if getattr(provider, "is_ready", False):
                self._embedding_provider = provider
                return provider

        if self._get_reference_registry().has_references() or settings.enable_face_matching:
            provider = LocalFaceEmbeddingProvider()
            if getattr(provider, "is_ready", False):
                self._embedding_provider = provider
                return provider

        return None

    def _get_reference_registry(self) -> FaceReferenceRegistry:
        if self._reference_registry_factory is not None:
            return self._reference_registry_factory()
        return self._reference_registry

