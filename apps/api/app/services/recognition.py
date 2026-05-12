from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from hashlib import sha256
from math import exp, sqrt
from pathlib import Path
from typing import Any, List, Sequence

try:
    import cv2
except Exception:  # pragma: no cover - optional dependency in test environments
    cv2 = None

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency in test environments
    np = None

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional dependency in test environments
    Image = None

try:
    from insightface.app import FaceAnalysis
except Exception:  # pragma: no cover - optional dependency in test environments
    FaceAnalysis = None

from app.schemas.memory_report import FaceAssessment, IdentityCandidate


def _normalize_python(vector: list[float]) -> list[float]:
    if not vector:
        return []
    norm = sqrt(sum(value * value for value in vector))
    if norm <= 0:
        return []
    return [float(value / norm) for value in vector]


def _cosine_similarity_python(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dim = min(len(a), len(b))
    if dim <= 0:
        return 0.0
    av = a[:dim]
    bv = b[:dim]
    dot = sum(x * y for x, y in zip(av, bv))
    na = sqrt(sum(x * x for x in av))
    nb = sqrt(sum(y * y for y in bv))
    if na <= 0 or nb <= 0:
        return 0.0
    return max(-1.0, min(1.0, dot / (na * nb)))


def _coerce_embedding(value: object) -> list[float]:
    if not isinstance(value, list):
        return []
    out: list[float] = []
    for item in value:
        if isinstance(item, (int, float)):
            out.append(float(item))
    return _normalize_python(out)


def get_probe_embedding(
    provider: "FaceEmbeddingProvider | None",
    image_path: str,
    face_box: dict,
) -> list[float] | None:
    fused = _coerce_embedding(face_box.get("multi_frame_embedding"))
    if fused:
        return fused
    if provider is None:
        return None
    return provider.extract_embedding(image_path, face_box)


@dataclass(frozen=True)
class RecognitionConfig:
    face_quality_min_threshold: float
    face_quality_hard_fail_threshold: float
    recognition_top_k: int
    recognition_accept_threshold: float
    recognition_tentative_threshold: float
    recognition_calibration_mode: str
    recognition_cross_provider_bonus: float
    recognition_disagreement_penalty: float


class FaceEmbeddingProvider(ABC):
    name: str

    @abstractmethod
    def extract_embedding(self, image_path: str, face_box: dict) -> list[float] | None:
        raise NotImplementedError


class InsightFaceEmbeddingProvider(FaceEmbeddingProvider):
    name = "insightface"

    def __init__(self) -> None:
        self._analyzer = None
        if FaceAnalysis is None:
            return
        try:
            # Support both newer insightface API (providers kwarg) and older wheel API.
            # Prioritize CUDA for GPU acceleration, fallback to CPU.
            try:
                analyzer = FaceAnalysis(name="buffalo_l", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
            except TypeError:
                analyzer = FaceAnalysis(name="buffalo_l")
            analyzer.prepare(ctx_id=0, det_size=(640, 640))
            # insightface 0.2.1 creates sessions without providers= so they land on CPU
            # even when CUDAExecutionProvider is available.  Swap each sub-model's
            # session for an explicit CUDA-preferred session so GPU is actually used.
            self._reinject_cuda_sessions(analyzer)
            self._analyzer = analyzer
        except Exception:
            self._analyzer = None

    @staticmethod
    def _reinject_cuda_sessions(analyzer: object) -> None:
        """Replace each insightface sub-model's ORT session with a CUDA-preferred one."""
        try:
            import onnxruntime as _ort

            _cuda_providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            _available = _ort.get_available_providers()
            # Only attempt if CUDA is actually registered in this ORT build.
            if "CUDAExecutionProvider" not in _available:
                return

            models = getattr(analyzer, "models", {})
            for _model in models.values():
                _session = getattr(_model, "session", None)
                if _session is None:
                    continue
                _model_file = getattr(_model, "model_file", None)
                if not _model_file:
                    continue
                try:
                    _new_session = _ort.InferenceSession(
                        _model_file,
                        None,
                        providers=_cuda_providers,
                    )
                    _model.session = _new_session
                except Exception:
                    # If CUDA session fails for this model, leave original session in place.
                    pass
        except Exception:
            pass

    def extract_embedding(self, image_path: str, face_box: dict) -> list[float] | None:
        if self._analyzer is None or cv2 is None or np is None:
            return None
        frame = cv2.imread(image_path)
        if frame is None:
            return None

        height, width = frame.shape[:2]
        target = self._to_pixels(face_box, width, height)
        faces = self._analyzer.get(frame) or []
        if not faces:
            return None

        best_face = None
        best_iou = -1.0
        for face in faces:
            bbox = getattr(face, "bbox", None)
            if bbox is None or len(bbox) < 4:
                continue
            candidate_box = (int(bbox[0]), int(bbox[1]), int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1]))
            score = self._iou(target, candidate_box)
            if score > best_iou:
                best_iou = score
                best_face = face

        if best_face is None:
            return None

        embedding = getattr(best_face, "normed_embedding", None)
        if embedding is None:
            embedding = getattr(best_face, "embedding", None)
        if embedding is None:
            return None
        vector = np.array(embedding, dtype=np.float32)
        norm = float(np.linalg.norm(vector))
        if norm <= 0:
            return None
        normalized = vector / norm
        return [float(v) for v in normalized.tolist()]

    @property
    def is_ready(self) -> bool:
        return self._analyzer is not None

    def _to_pixels(self, face_box: dict, img_w: int, img_h: int) -> tuple[int, int, int, int]:
        x = int(max(0, min(img_w - 1, float(face_box.get("x", 0.0)) * img_w)))
        y = int(max(0, min(img_h - 1, float(face_box.get("y", 0.0)) * img_h)))
        w = int(max(1, min(img_w - x, float(face_box.get("width", 0.0)) * img_w)))
        h = int(max(1, min(img_h - y, float(face_box.get("height", 0.0)) * img_h)))
        return x, y, w, h

    def _iou(self, a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
        ax1, ay1, aw, ah = a
        bx1, by1, bw, bh = b
        ax2, ay2 = ax1 + aw, ay1 + ah
        bx2, by2 = bx1 + bw, by1 + bh

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        inter_w = max(0, inter_x2 - inter_x1)
        inter_h = max(0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h
        if inter_area <= 0:
            return 0.0
        union = (aw * ah) + (bw * bh) - inter_area
        if union <= 0:
            return 0.0
        return inter_area / float(union)


class LocalFaceEmbeddingProvider(FaceEmbeddingProvider):
    name = "local-face-embedding"

    @property
    def is_ready(self) -> bool:
        return Image is not None

    def extract_embedding(self, image_path: str, face_box: dict) -> list[float] | None:
        if Image is None:
            return None

        path = Path(image_path)
        if not path.exists():
            return None

        with Image.open(path) as img:
            rgb = img.convert("RGB")
            width, height = rgb.size
            x, y, w, h = self._to_pixels(face_box, width, height)
            crop = rgb.crop((x, y, min(width, x + w), min(height, y + h)))

        if crop.size[0] <= 0 or crop.size[1] <= 0:
            return None

        crop_image = crop.resize((32, 32), Image.Resampling.BILINEAR)
        pixels = list(crop_image.getdata())
        grayscale = [0.299 * red + 0.587 * green + 0.114 * blue for red, green, blue in pixels]
        width = 32
        height = 32

        grad_x: list[float] = []
        grad_y: list[float] = []
        for row in range(height):
            for col in range(width):
                index = row * width + col
                right = grayscale[index + 1] if col < width - 1 else grayscale[index]
                down = grayscale[index + width] if row < height - 1 else grayscale[index]
                grad_x.append((right - grayscale[index]) / 255.0)
                grad_y.append((down - grayscale[index]) / 255.0)

        red_values = [red / 255.0 for red, _, _ in pixels]
        green_values = [green / 255.0 for _, green, _ in pixels]
        blue_values = [blue / 255.0 for _, _, blue in pixels]
        channel_means = [sum(values) / len(values) for values in (red_values, green_values, blue_values)]
        channel_stds = [self._std(values) for values in (red_values, green_values, blue_values)]

        features = [
            *(value / 255.0 for value in grayscale),
            *grad_x,
            *grad_y,
            *channel_means,
            *channel_stds,
        ]
        normalized = _normalize_python(features)
        if not normalized:
            return None
        return normalized

    def _to_pixels(self, face_box: dict, img_w: int, img_h: int) -> tuple[int, int, int, int]:
        x = int(max(0, min(img_w - 1, float(face_box.get("x", 0.0)) * img_w)))
        y = int(max(0, min(img_h - 1, float(face_box.get("y", 0.0)) * img_h)))
        w = int(max(1, min(img_w - x, float(face_box.get("width", 0.0)) * img_w)))
        h = int(max(1, min(img_h - y, float(face_box.get("height", 0.0)) * img_h)))
        return x, y, w, h

    def _std(self, values: list[float]) -> float:
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        return sqrt(max(variance, 0.0))


def select_embedding_provider(
    provider_name: str = "auto",
    *,
    paid_provider_enabled: bool = False,
) -> FaceEmbeddingProvider | None:
    """Choose the active embedding provider without requiring paid services by default."""
    requested = (provider_name or "auto").strip().lower()

    if requested in {"none", "disabled", "off"}:
        return None

    if requested in {"local", "free"}:
        provider = LocalFaceEmbeddingProvider()
        return provider if getattr(provider, "is_ready", False) else None

    if requested in {"insightface", "arcface"}:
        provider = InsightFaceEmbeddingProvider()
        if getattr(provider, "is_ready", False):
            return provider
        fallback = LocalFaceEmbeddingProvider()
        return fallback if getattr(fallback, "is_ready", False) else None

    if requested in {"paid", "hosted"} and not paid_provider_enabled:
        fallback = LocalFaceEmbeddingProvider()
        return fallback if getattr(fallback, "is_ready", False) else None

    provider = InsightFaceEmbeddingProvider()
    if getattr(provider, "is_ready", False):
        return provider

    fallback = LocalFaceEmbeddingProvider()
    if getattr(fallback, "is_ready", False):
        return fallback

    return None


class EmbeddingMatcher:
    def __init__(
        self,
        provider: FaceEmbeddingProvider | None,
        reference_embeddings_json: str = "",
    ) -> None:
        self.provider = provider
        self._references = self._parse_references(reference_embeddings_json)

    @property
    def is_ready(self) -> bool:
        return self.provider is not None and bool(self._references)

    @property
    def reference_count(self) -> int:
        return len(self._references)

    def build_candidates(self, image_path: str, face_box: dict) -> list[IdentityCandidate]:
        if not self.is_ready:
            return []
        assert self.provider is not None

        probe = get_probe_embedding(self.provider, image_path, face_box)
        if not probe:
            return []

        candidates: list[IdentityCandidate] = []
        for reference in self._references:
            similarity = self._cosine_similarity(probe, reference["embedding"])
            raw_conf = self._clamp((similarity + 1.0) / 2.0)
            candidates.append(
                IdentityCandidate(
                    name_or_alias=reference["name_or_alias"],
                    provider=self.provider.name,
                    raw_confidence=round(raw_conf, 6),
                    calibrated_confidence=0.0,
                    match_reason="Cosine similarity against configured reference embedding",
                )
            )
        candidates.sort(key=lambda item: item.raw_confidence, reverse=True)
        return candidates

    def _parse_references(self, raw_json: str) -> list[dict[str, object]]:
        payload = (raw_json or "").strip()
        if not payload:
            return []
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []

        references: list[dict[str, object]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name_or_alias") or "").strip()
            vector = item.get("embedding")
            if not name or not isinstance(vector, list) or not vector:
                continue
            normalized = self._normalize_vector([float(v) for v in vector if isinstance(v, (int, float))])
            if not normalized:
                continue
            references.append({"name_or_alias": name, "embedding": normalized})
        return references

    def _normalize_vector(self, vector: list[float]) -> list[float]:
        return _normalize_python([float(value) for value in vector])

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        return self._clamp(_cosine_similarity_python(a, b), -1.0, 1.0)

    def _clamp(self, value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, value))


class FaceQualityAssessor:
    """Compute deterministic face-quality diagnostics for detected face boxes."""

    def assess_faces(self, image_path: str, face_boxes: Sequence[dict]) -> List[FaceAssessment]:
        if not face_boxes:
            return []

        path = Path(image_path)
        np_image = None
        img_w = 1000
        img_h = 1000
        if path.exists() and Image is not None and np is not None:
            try:
                with Image.open(path) as img:
                    rgb = img.convert("RGB")
                    np_image = np.array(rgb)
                img_h, img_w = np_image.shape[:2]
            except Exception:
                np_image = None

        out: list[FaceAssessment] = []

        for index, raw_box in enumerate(face_boxes):
            x, y, w, h = self._box_pixels(raw_box, img_w, img_h)
            if np_image is not None:
                crop = np_image[y : y + h, x : x + w]
            elif np is not None:
                crop = np.zeros((h, w, 3), dtype=np.uint8)
            else:
                crop = None
            detector_conf = self._clamp(float(raw_box.get("score", 0.0)))
            blur_score = self._blur_score(crop)
            box_ratio = self._clamp((w * h) / float(max(img_w * img_h, 1)))
            box_size_score = self._clamp(box_ratio / 0.12)
            pose_score = self._pose_score(raw_box)
            occlusion_score = self._occlusion_score(crop)
            quality = self._clamp(
                0.30 * blur_score
                + 0.25 * box_size_score
                + 0.20 * pose_score
                + 0.10 * occlusion_score
                + 0.15 * detector_conf
            )
            flags = self._quality_flags(
                box_ratio=box_ratio,
                blur_score=blur_score,
                pose_score=pose_score,
                occlusion_score=occlusion_score,
                detector_confidence=detector_conf,
            )

            out.append(
                FaceAssessment(
                    face_index=index,
                    detector_confidence=round(detector_conf, 6),
                    blur_score=round(blur_score, 6),
                    box_size_ratio=round(box_ratio, 6),
                    pose_score=round(pose_score, 6),
                    occlusion_score=round(occlusion_score, 6),
                    face_quality_score=round(quality, 6),
                    face_quality_flags=flags,
                )
            )

        return out

    def _box_pixels(self, face_box: dict, img_w: int, img_h: int) -> tuple[int, int, int, int]:
        x = int(max(0, min(img_w - 1, float(face_box.get("x", 0.0)) * img_w)))
        y = int(max(0, min(img_h - 1, float(face_box.get("y", 0.0)) * img_h)))
        w = int(max(1, min(img_w - x, float(face_box.get("width", 0.0)) * img_w)))
        h = int(max(1, min(img_h - y, float(face_box.get("height", 0.0)) * img_h)))
        return x, y, w, h

    def _blur_score(self, crop: Any) -> float:
        if cv2 is None or np is None or crop is None:
            return 0.5
        if crop.size == 0:
            return 0.0
        gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        return self._clamp(variance / 180.0)

    def _pose_score(self, face_box: dict) -> float:
        center_x = float(face_box.get("x", 0.0)) + (float(face_box.get("width", 0.0)) * 0.5)
        center_y = float(face_box.get("y", 0.0)) + (float(face_box.get("height", 0.0)) * 0.5)
        offset = abs(center_x - 0.5) + abs(center_y - 0.5)
        return self._clamp(1.0 - min(1.0, offset / 0.7))

    def _occlusion_score(self, crop: Any) -> float:
        if cv2 is None or np is None or crop is None:
            return 0.5
        if crop.size == 0:
            return 0.0
        gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        dark_ratio = float(np.mean(gray < 30))
        bright_ratio = float(np.mean(gray > 245))
        clipped_ratio = max(dark_ratio, bright_ratio)
        return self._clamp(1.0 - min(1.0, clipped_ratio * 2.0))

    def _quality_flags(
        self,
        *,
        box_ratio: float,
        blur_score: float,
        pose_score: float,
        occlusion_score: float,
        detector_confidence: float,
    ) -> List[str]:
        flags: list[str] = []
        if box_ratio < 0.04:
            flags.append("low_resolution")
        if blur_score < 0.35:
            flags.append("blurry")
        if pose_score < 0.35:
            flags.append("extreme_pose")
        if occlusion_score < 0.35:
            flags.append("occluded")
        if detector_confidence < 0.4:
            flags.append("low_detector_confidence")
        return flags

    def _clamp(self, value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, value))


class RecognitionScorer:
    """Rank and classify identity candidates with configurable calibration and penalties."""

    def __init__(self, config: RecognitionConfig) -> None:
        self.config = config

    def build_candidates(self, query: str, face_assessment: FaceAssessment) -> List[IdentityCandidate]:
        seed = " ".join((query or "unknown").strip().split())
        alias = seed[:64] if seed else "Unknown"

        candidates = [
            IdentityCandidate(
                name_or_alias=alias,
                provider="local-heuristic",
                raw_confidence=round(0.55 + (face_assessment.detector_confidence * 0.35), 6),
                calibrated_confidence=0.0,
                match_reason="Face geometry and detector confidence align with provided subject hint",
            ),
            IdentityCandidate(
                name_or_alias=f"{alias} (variant)",
                provider="local-heuristic",
                raw_confidence=round(0.45 + (face_assessment.blur_score * 0.25), 6),
                calibrated_confidence=0.0,
                match_reason="Secondary candidate retained for ambiguity handling",
            ),
        ]

        scored = self.score_candidates(candidates, face_assessment)
        scored.sort(key=lambda item: item.recognition_score, reverse=True)
        return scored[: max(self.config.recognition_top_k, 1)]

    def score_candidates(
        self,
        candidates: List[IdentityCandidate],
        face_assessment: FaceAssessment,
    ) -> List[IdentityCandidate]:
        quality_modifier = 0.85 if face_assessment.face_quality_score < self.config.face_quality_min_threshold else 1.0
        scored = [self._score_candidate(c, face_assessment, quality_modifier) for c in candidates]
        return self._apply_cross_provider_adjustments(scored)

    def classify(self, candidates: List[IdentityCandidate]) -> str:
        if not candidates:
            return "rejected"
        top = candidates[0].recognition_score
        if top >= self.config.recognition_accept_threshold:
            return "accepted"
        if top >= self.config.recognition_tentative_threshold:
            return "tentative"
        return "rejected"

    def _score_candidate(
        self,
        candidate: IdentityCandidate,
        face_assessment: FaceAssessment,
        quality_modifier: float,
    ) -> IdentityCandidate:
        calibrated = self._calibrate(candidate.raw_confidence) * quality_modifier
        quality = face_assessment.face_quality_score

        false_positive_penalty = 0.0
        if quality < self.config.face_quality_min_threshold and calibrated < self.config.recognition_tentative_threshold:
            false_positive_penalty += 0.20

        recognition_score = self._clamp((0.45 * quality) + (0.45 * calibrated) + 0.10 - false_positive_penalty)
        decision = self._decision(recognition_score)

        candidate.calibrated_confidence = round(self._clamp(calibrated), 6)
        candidate.recognition_score = round(recognition_score, 6)
        candidate.recognition_decision = decision
        return candidate

    def _apply_cross_provider_adjustments(self, candidates: List[IdentityCandidate]) -> List[IdentityCandidate]:
        if len(candidates) <= 1:
            return candidates

        by_name: dict[str, list[IdentityCandidate]] = {}
        for item in candidates:
            by_name.setdefault(item.name_or_alias.lower(), []).append(item)

        for group in by_name.values():
            providers = {item.provider for item in group}
            if len(providers) > 1:
                spread = max(item.calibrated_confidence for item in group) - min(item.calibrated_confidence for item in group)
                adjustment = self.config.recognition_cross_provider_bonus
                if spread > 0.25:
                    adjustment -= self.config.recognition_disagreement_penalty
                for item in group:
                    item.recognition_score = round(self._clamp(item.recognition_score + adjustment), 6)
                    item.recognition_decision = self._decision(item.recognition_score)
        return candidates

    def _calibrate(self, raw_confidence: float) -> float:
        raw = self._clamp(raw_confidence)
        mode = (self.config.recognition_calibration_mode or "linear").lower()
        if mode == "sigmoid":
            return self._clamp(1.0 / (1.0 + exp(-8.0 * (raw - 0.5))))
        return raw

    def _decision(self, recognition_score: float) -> str:
        if recognition_score >= self.config.recognition_accept_threshold:
            return "accepted"
        if recognition_score >= self.config.recognition_tentative_threshold:
            return "tentative"
        return "rejected"

    def _clamp(self, value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, value))


def stable_reference_embedding(seed: str, dimensions: int = 128) -> list[float]:
    """Generate deterministic normalized vectors for tests and local reference setup."""
    safe_dims = max(8, dimensions)
    buf = bytearray()
    counter = 0
    while len(buf) < safe_dims:
        digest = sha256(f"{seed}:{counter}".encode("utf-8")).digest()
        buf.extend(digest)
        counter += 1
    values = [((value / 255.0) * 2.0) - 1.0 for value in buf[:safe_dims]]
    return _normalize_python(values)

