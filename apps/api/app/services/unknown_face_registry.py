from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from math import sqrt
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class UnknownFaceSample:
    unknown_sample_id: str
    embedding: list[float]
    source_upload_id: str
    face_index: int
    quality_score: float
    provider: str
    created_at: str


@dataclass
class UnknownFaceCluster:
    unknown_cluster_id: str
    sample_ids: list[str]
    centroid_embedding: list[float]
    sighting_count: int
    first_seen_at: str
    last_seen_at: str
    familiarity_state: str
    suggested_for_enrollment: bool = False
    promoted: bool = False


class UnknownFaceRegistry:
    def __init__(
        self,
        path: str | Path,
        *,
        cluster_path: str | Path | None = None,
        cluster_similarity_threshold: float = 0.88,
        familiarity_min_samples: int = 2,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cluster_path = Path(cluster_path) if cluster_path is not None else self.path.with_name("clusters.json")
        self.cluster_path.parent.mkdir(parents=True, exist_ok=True)
        self.cluster_similarity_threshold = max(-1.0, min(1.0, float(cluster_similarity_threshold)))
        self.familiarity_min_samples = max(2, int(familiarity_min_samples))
        self._lock = threading.Lock()

    def list_samples(self) -> list[UnknownFaceSample]:
        samples: list[UnknownFaceSample] = []
        for item in self._load_payload():
            if not isinstance(item, dict):
                continue
            embedding = item.get("embedding")
            source_upload_id = str(item.get("source_upload_id") or "").strip()
            provider = str(item.get("provider") or "").strip()
            if not isinstance(embedding, list) or not embedding or not source_upload_id or not provider:
                continue
            try:
                vector = [float(value) for value in embedding if isinstance(value, (int, float))]
                face_index = max(0, int(item.get("face_index") or 0))
                quality_score = max(0.0, min(1.0, float(item.get("quality_score") or 0.0)))
            except (TypeError, ValueError):
                continue
            if not vector:
                continue
            samples.append(
                UnknownFaceSample(
                    unknown_sample_id=str(item.get("unknown_sample_id") or uuid4()),
                    embedding=vector,
                    source_upload_id=source_upload_id,
                    face_index=face_index,
                    quality_score=quality_score,
                    provider=provider,
                    created_at=str(item.get("created_at") or "") or datetime.now(UTC).isoformat(),
                )
            )
        return samples

    def add_sample(
        self,
        *,
        embedding: list[float],
        source_upload_id: str,
        face_index: int,
        quality_score: float,
        provider: str,
    ) -> UnknownFaceSample:
        source = source_upload_id.strip()
        if not source:
            raise ValueError("source_upload_id is required")
        if not embedding:
            raise ValueError("embedding is required")
        if not provider.strip():
            raise ValueError("provider is required")

        with self._lock:
            samples = self.list_samples()
            for sample in samples:
                if sample.source_upload_id == source and sample.face_index == max(0, int(face_index)):
                    return sample

            sample = UnknownFaceSample(
                unknown_sample_id=str(uuid4()),
                embedding=[float(value) for value in embedding],
                source_upload_id=source,
                face_index=max(0, int(face_index)),
                quality_score=round(max(0.0, min(1.0, float(quality_score))), 6),
                provider=provider.strip(),
                created_at=datetime.now(UTC).isoformat(),
            )
            samples.append(sample)
            self._save_payload([asdict(item) for item in samples])
            self._assign_sample_to_cluster(sample)
            return sample

    def sample_count(self) -> int:
        return len(self.list_samples())

    def list_clusters(self) -> list[UnknownFaceCluster]:
        clusters: list[UnknownFaceCluster] = []
        for item in self._load_cluster_payload():
            if not isinstance(item, dict):
                continue
            sample_ids = item.get("sample_ids")
            centroid = item.get("centroid_embedding")
            cluster_id = str(item.get("unknown_cluster_id") or "").strip()
            if not cluster_id or not isinstance(sample_ids, list) or not isinstance(centroid, list):
                continue
            try:
                vector = [float(value) for value in centroid if isinstance(value, (int, float))]
                ids = [str(value) for value in sample_ids if str(value or "").strip()]
                sighting_count = max(0, int(item.get("sighting_count") or len(ids)))
            except (TypeError, ValueError):
                continue
            if not vector or not ids:
                continue
            clusters.append(
                UnknownFaceCluster(
                    unknown_cluster_id=cluster_id,
                    sample_ids=ids,
                    centroid_embedding=_normalize(vector),
                    sighting_count=sighting_count,
                    first_seen_at=str(item.get("first_seen_at") or "") or datetime.now(UTC).isoformat(),
                    last_seen_at=str(item.get("last_seen_at") or "") or datetime.now(UTC).isoformat(),
                    familiarity_state=str(item.get("familiarity_state") or "new"),
                    suggested_for_enrollment=bool(item.get("suggested_for_enrollment") or False),
                    promoted=bool(item.get("promoted") or False),
                )
            )
        return clusters

    def find_cluster_for_sample(self, unknown_sample_id: str) -> UnknownFaceCluster | None:
        sample_id = unknown_sample_id.strip()
        if not sample_id:
            return None
        for cluster in self.list_clusters():
            if sample_id in cluster.sample_ids:
                return cluster
        return None

    def cluster_count(self) -> int:
        return len(self.list_clusters())

    def suggested_clusters(self) -> list[UnknownFaceCluster]:
        return [
            cluster
            for cluster in self.list_clusters()
            if cluster.suggested_for_enrollment and not cluster.promoted
        ]

    def find_cluster(self, unknown_cluster_id: str) -> UnknownFaceCluster | None:
        cluster_id = unknown_cluster_id.strip()
        if not cluster_id:
            return None
        for cluster in self.list_clusters():
            if cluster.unknown_cluster_id == cluster_id:
                return cluster
        return None

    def samples_for_cluster(self, unknown_cluster_id: str) -> list[UnknownFaceSample]:
        cluster = self.find_cluster(unknown_cluster_id)
        if cluster is None:
            return []
        by_id = {sample.unknown_sample_id: sample for sample in self.list_samples()}
        return [by_id[sample_id] for sample_id in cluster.sample_ids if sample_id in by_id]

    def mark_cluster_promoted(self, unknown_cluster_id: str) -> UnknownFaceCluster | None:
        cluster_id = unknown_cluster_id.strip()
        if not cluster_id:
            return None
        clusters = self.list_clusters()
        updated: UnknownFaceCluster | None = None
        for index, cluster in enumerate(clusters):
            if cluster.unknown_cluster_id != cluster_id:
                continue
            cluster.promoted = True
            cluster.suggested_for_enrollment = False
            cluster.familiarity_state = "promoted"
            clusters[index] = cluster
            updated = cluster
            break
        if updated is None:
            return None
        self._save_cluster_payload([asdict(item) for item in clusters])
        return updated

    def _load_payload(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if isinstance(payload, list):
            return payload
        return []

    def _save_payload(self, payload: list[dict[str, Any]]) -> None:
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(self.path)

    def _assign_sample_to_cluster(self, sample: UnknownFaceSample) -> UnknownFaceCluster:
        clusters = self.list_clusters()
        best_index: int | None = None
        best_similarity = -1.0
        for index, cluster in enumerate(clusters):
            if cluster.promoted:
                continue
            similarity = _cosine_similarity(sample.embedding, cluster.centroid_embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_index = index

        if best_index is None or best_similarity < self.cluster_similarity_threshold:
            cluster = UnknownFaceCluster(
                unknown_cluster_id=str(uuid4()),
                sample_ids=[sample.unknown_sample_id],
                centroid_embedding=_normalize(sample.embedding),
                sighting_count=1,
                first_seen_at=sample.created_at,
                last_seen_at=sample.created_at,
                familiarity_state="new",
                suggested_for_enrollment=False,
            )
            clusters.append(cluster)
        else:
            existing = clusters[best_index]
            if sample.unknown_sample_id not in existing.sample_ids:
                existing.sample_ids.append(sample.unknown_sample_id)
            existing.sighting_count = len(existing.sample_ids)
            existing.centroid_embedding = _centroid_for_sample_ids(existing.sample_ids, self.list_samples())
            existing.last_seen_at = max(existing.last_seen_at, sample.created_at)
            if existing.sighting_count >= self.familiarity_min_samples:
                existing.familiarity_state = "familiar"
                existing.suggested_for_enrollment = True
            clusters[best_index] = existing
            cluster = existing

        self._save_cluster_payload([asdict(item) for item in clusters])
        return cluster

    def _load_cluster_payload(self) -> list[dict[str, Any]]:
        if not self.cluster_path.exists():
            return []
        try:
            payload = json.loads(self.cluster_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if isinstance(payload, list):
            return payload
        return []

    def _save_cluster_payload(self, payload: list[dict[str, Any]]) -> None:
        temp_path = self.cluster_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(self.cluster_path)


def _normalize(vector: list[float]) -> list[float]:
    norm = sqrt(sum(value * value for value in vector))
    if norm <= 0:
        return []
    return [float(value / norm) for value in vector]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    dim = min(len(left), len(right))
    if dim <= 0:
        return 0.0
    a = left[:dim]
    b = right[:dim]
    na = sqrt(sum(value * value for value in a))
    nb = sqrt(sum(value * value for value in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b)) / (na * nb)))


def _centroid_for_sample_ids(sample_ids: list[str], samples: list[UnknownFaceSample]) -> list[float]:
    by_id = {sample.unknown_sample_id: sample for sample in samples}
    vectors = [by_id[sample_id].embedding for sample_id in sample_ids if sample_id in by_id]
    if not vectors:
        return []
    dim = min(len(vector) for vector in vectors)
    centroid = [sum(vector[index] for vector in vectors) / len(vectors) for index in range(dim)]
    return _normalize(centroid)

