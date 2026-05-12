from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.memory_entity_registry import MemoryEntityRecord


@dataclass(frozen=True)
class MemorySearchResult:
    entity_id: str
    domain_type: str
    label: str
    lifecycle_state: str
    confidence: float
    score: float
    matched_fields: list[str]
    tags: list[str]


def search_memory_entities(
    *,
    entities: list[MemoryEntityRecord],
    query: str = "",
    domain_type: str | None = None,
    lifecycle_state: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    normalized_query = query.strip().lower()
    normalized_domain = _normalize_filter(domain_type)
    normalized_state = _normalize_filter(lifecycle_state)
    results: list[MemorySearchResult] = []

    for entity in entities:
        if normalized_domain and entity.domain_type != normalized_domain:
            continue
        if normalized_state and entity.lifecycle_state != normalized_state:
            continue
        score, matched_fields = _score_entity(entity, normalized_query)
        if normalized_query and score <= 0:
            continue
        results.append(
            MemorySearchResult(
                entity_id=entity.entity_id,
                domain_type=entity.domain_type,
                label=entity.label,
                lifecycle_state=entity.lifecycle_state,
                confidence=entity.confidence,
                score=round(score, 6),
                matched_fields=matched_fields,
                tags=list(entity.tags),
            )
        )

    results.sort(key=lambda item: (item.score, item.confidence, item.label.lower()), reverse=True)
    limited = results[: max(1, min(int(limit), 100))]
    return {
        "query": query,
        "results": [item.__dict__ for item in limited],
        "result_count": len(limited),
        "total_candidates": len(results),
    }


def _score_entity(entity: MemoryEntityRecord, query: str) -> tuple[float, list[str]]:
    if not query:
        return 0.25 + (0.25 * entity.confidence), ["all"]
    score = 0.0
    matched: list[str] = []
    fields = {
        "label": entity.label,
        "domain_type": entity.domain_type,
        "aliases": " ".join(entity.aliases),
        "tags": " ".join(entity.tags),
        "notes": entity.notes or "",
        "attributes": " ".join(_flatten_mapping(entity.attributes)),
    }
    for field_name, value in fields.items():
        text = value.lower()
        if not text:
            continue
        if query == text:
            score += 1.0
            matched.append(field_name)
        elif query in text:
            score += 0.6 if field_name == "label" else 0.35
            matched.append(field_name)
        else:
            tokens = [token for token in query.split() if token]
            token_hits = [token for token in tokens if token in text]
            if token_hits:
                score += min(0.3, 0.1 * len(token_hits))
                matched.append(field_name)
    if matched:
        score += 0.2 * entity.confidence
    return score, sorted(set(matched))


def _flatten_mapping(value: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key, item in value.items():
        out.append(str(key))
        if isinstance(item, dict):
            out.extend(_flatten_mapping(item))
        elif isinstance(item, list):
            out.extend(str(part) for part in item)
        else:
            out.append(str(item))
    return out


def _normalize_filter(value: str | None) -> str | None:
    if not value:
        return None
    normalized = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value.lower())
    return normalized.strip("_-") or None
