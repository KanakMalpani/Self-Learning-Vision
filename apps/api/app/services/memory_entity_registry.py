from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


RESERVED_DOMAIN_TYPES = {"person", "object", "place", "scene", "event", "document", "product", "inventory"}


@dataclass
class MemoryObservation:
    observation_id: str
    source: str
    source_id: str | None = None
    modality: str = "vision"
    confidence: float | None = None
    notes: str | None = None
    observed_at: str = ""


@dataclass
class MemoryLifecycleEvent:
    event_id: str
    event_type: str
    from_state: str
    to_state: str
    confidence_before: float
    confidence_after: float
    reason: str | None = None
    created_at: str = ""


@dataclass
class MemoryEntityRecord:
    entity_id: str
    domain_type: str
    label: str
    attributes: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"
    user_schema: dict[str, Any] = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    notes: str | None = None
    confidence: float = 0.0
    lifecycle_state: str = "candidate"
    observations: list[MemoryObservation] = field(default_factory=list)
    lifecycle_events: list[MemoryLifecycleEvent] = field(default_factory=list)
    source_reference_ids: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class MemoryEntityRegistry:
    """Local, user-scoped registry for generic memory entities.

    This is intentionally domain-neutral. Face identity is one built-in domain
    (`person`), while users and providers can introduce custom domain types
    without changing the storage contract.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def list_entities(self, domain_type: str | None = None) -> list[MemoryEntityRecord]:
        entities = [self._record_from_payload(item) for item in self._load_payload()]
        records = [record for record in entities if record is not None]
        if domain_type:
            normalized = self.normalize_domain_type(domain_type)
            records = [record for record in records if record.domain_type == normalized]
        return records

    def list_domain_types(self) -> list[str]:
        domains = {record.domain_type for record in self.list_entities()}
        domains.update(RESERVED_DOMAIN_TYPES)
        return sorted(domains)

    def find(self, entity_id: str) -> MemoryEntityRecord | None:
        needle = entity_id.strip()
        if not needle:
            return None
        for record in self.list_entities():
            if record.entity_id == needle:
                return record
        return None

    def find_by_label(self, *, domain_type: str, label: str) -> MemoryEntityRecord | None:
        normalized_domain = self.normalize_domain_type(domain_type)
        normalized_label = label.strip().lower()
        if not normalized_label:
            return None
        for record in self.list_entities(normalized_domain):
            labels = [record.label, *record.aliases]
            if any(item.strip().lower() == normalized_label for item in labels):
                return record
        return None

    def upsert_entity(
        self,
        *,
        domain_type: str,
        label: str,
        attributes: dict[str, Any] | None = None,
        user_schema: dict[str, Any] | None = None,
        aliases: list[str] | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
        confidence: float | None = None,
        lifecycle_state: str | None = None,
        source_reference_id: str | None = None,
        observation: MemoryObservation | None = None,
    ) -> MemoryEntityRecord:
        normalized_domain = self.normalize_domain_type(domain_type)
        clean_label = label.strip()
        if not clean_label:
            raise ValueError("Memory entity label is required")

        with self._lock:
            payload = self._load_payload()
            records = [self._record_from_payload(item) for item in payload]
            records = [record for record in records if record is not None]
            existing_index = self._find_index(records, domain_type=normalized_domain, label=clean_label)
            now_iso = datetime.now(UTC).isoformat()

            if existing_index is None:
                record = MemoryEntityRecord(
                    entity_id=str(uuid4()),
                    domain_type=normalized_domain,
                    label=clean_label,
                    attributes=self._sanitize_mapping(attributes),
                    user_schema=self._sanitize_mapping(user_schema),
                    aliases=self._sanitize_list(aliases),
                    tags=self._sanitize_list(tags),
                    notes=notes.strip() if notes else None,
                    confidence=self._clamp_confidence(confidence if confidence is not None else 0.0),
                    lifecycle_state=self._normalize_lifecycle(lifecycle_state or "candidate"),
                    observations=[],
                    source_reference_ids=[],
                    created_at=now_iso,
                    updated_at=now_iso,
                )
                records.append(record)
            else:
                record = records[existing_index]
                record.attributes = {**record.attributes, **self._sanitize_mapping(attributes)}
                record.user_schema = {**record.user_schema, **self._sanitize_mapping(user_schema)}
                record.aliases = self._merge_lists(record.aliases, aliases)
                record.tags = self._merge_lists(record.tags, tags)
                if notes and notes.strip():
                    record.notes = notes.strip()
                if confidence is not None:
                    record.confidence = max(record.confidence, self._clamp_confidence(confidence))
                if lifecycle_state:
                    record.lifecycle_state = self._normalize_lifecycle(lifecycle_state)
                record.updated_at = now_iso

            if source_reference_id:
                record.source_reference_ids = self._merge_lists(record.source_reference_ids, [source_reference_id])
            if observation:
                if not observation.observed_at:
                    observation.observed_at = now_iso
                if all(item.observation_id != observation.observation_id for item in record.observations):
                    record.observations.append(observation)
                record.updated_at = now_iso

            self._save_payload([asdict(item) for item in records])
            return record

    def add_observation(
        self,
        *,
        entity_id: str,
        source: str,
        source_id: str | None = None,
        modality: str = "vision",
        confidence: float | None = None,
        notes: str | None = None,
    ) -> MemoryEntityRecord | None:
        with self._lock:
            records = [self._record_from_payload(item) for item in self._load_payload()]
            records = [record for record in records if record is not None]
            for record in records:
                if record.entity_id != entity_id:
                    continue
                now_iso = datetime.now(UTC).isoformat()
                record.observations.append(
                    MemoryObservation(
                        observation_id=str(uuid4()),
                        source=source.strip() or "manual",
                        source_id=source_id,
                        modality=modality.strip() or "vision",
                        confidence=self._clamp_confidence(confidence) if confidence is not None else None,
                        notes=notes.strip() if notes else None,
                        observed_at=now_iso,
                    )
                )
                if confidence is not None:
                    record.confidence = max(record.confidence, self._clamp_confidence(confidence))
                record.updated_at = now_iso
                self._save_payload([asdict(item) for item in records])
                return record
        return None

    def reinforce_entity(
        self,
        *,
        entity_id: str,
        amount: float = 0.05,
        reason: str | None = None,
        source_id: str | None = None,
    ) -> MemoryEntityRecord | None:
        return self._apply_lifecycle_event(
            entity_id=entity_id,
            event_type="reinforced",
            confidence_delta=abs(float(amount)),
            target_state="confirmed",
            reason=reason or "User or system reinforced this memory",
            source_id=source_id,
        )

    def record_contradiction(
        self,
        *,
        entity_id: str,
        rejected_label: str | None = None,
        amount: float = 0.15,
        reason: str | None = None,
    ) -> MemoryEntityRecord | None:
        with self._lock:
            records = [self._record_from_payload(item) for item in self._load_payload()]
            records = [record for record in records if record is not None]
            now_iso = datetime.now(UTC).isoformat()
            for record in records:
                if record.entity_id != entity_id:
                    continue
                contradictions = record.attributes.get("contradictions")
                if not isinstance(contradictions, list):
                    contradictions = []
                contradictions.append(
                    {
                        "rejected_label": rejected_label,
                        "reason": reason,
                        "created_at": now_iso,
                    }
                )
                record.attributes["contradictions"] = contradictions
                self._append_lifecycle_event(
                    record,
                    event_type="contradiction",
                    target_state="uncertain",
                    confidence_after=self._clamp_confidence(record.confidence - abs(float(amount))),
                    reason=reason or "Memory received contradictory feedback",
                    created_at=now_iso,
                )
                self._save_payload([asdict(item) for item in records])
                return record
        return None

    def decay_stale_entities(
        self,
        *,
        stale_after_days: int = 30,
        amount: float = 0.05,
        now: datetime | None = None,
    ) -> list[MemoryEntityRecord]:
        current = now or datetime.now(UTC)
        stale_after_days = max(1, int(stale_after_days))
        decayed: list[MemoryEntityRecord] = []
        with self._lock:
            records = [self._record_from_payload(item) for item in self._load_payload()]
            records = [record for record in records if record is not None]
            for record in records:
                if record.lifecycle_state in {"archived", "forgotten"}:
                    continue
                last_seen = self._last_memory_time(record)
                age_days = (current - last_seen).days
                if age_days < stale_after_days:
                    continue
                to_state = "stale" if record.lifecycle_state == "confirmed" else record.lifecycle_state
                self._append_lifecycle_event(
                    record,
                    event_type="decayed",
                    target_state=to_state,
                    confidence_after=self._clamp_confidence(record.confidence - abs(float(amount))),
                    reason=f"No reinforcing observation for {age_days} day(s)",
                    created_at=current.isoformat(),
                )
                decayed.append(record)
            if decayed:
                self._save_payload([asdict(item) for item in records])
        return decayed

    def lifecycle_summary(self) -> dict[str, Any]:
        records = self.list_entities()
        by_state: dict[str, int] = {}
        by_domain: dict[str, int] = {}
        total_confidence = 0.0
        contradiction_count = 0
        for record in records:
            by_state[record.lifecycle_state] = by_state.get(record.lifecycle_state, 0) + 1
            by_domain[record.domain_type] = by_domain.get(record.domain_type, 0) + 1
            total_confidence += record.confidence
            contradictions = record.attributes.get("contradictions")
            if isinstance(contradictions, list):
                contradiction_count += len(contradictions)
        return {
            "total_entities": len(records),
            "by_state": by_state,
            "by_domain": by_domain,
            "average_confidence": round(total_confidence / len(records), 6) if records else 0.0,
            "contradictions": contradiction_count,
            "lifecycle_events": sum(len(record.lifecycle_events) for record in records),
        }

    def entity_count(self, domain_type: str | None = None) -> int:
        return len(self.list_entities(domain_type))

    def snapshot(self) -> list[dict[str, Any]]:
        return [asdict(record) for record in self.list_entities()]

    def restore_snapshot(self, snapshot: list[dict[str, Any]]) -> None:
        records = [self._record_from_payload(item) for item in snapshot]
        clean_records = [record for record in records if record is not None]
        with self._lock:
            self._save_payload([asdict(record) for record in clean_records])

    def import_entities(self, snapshot: list[dict[str, Any]], *, replace: bool = False) -> int:
        incoming_records = [self._record_from_payload(item) for item in snapshot]
        incoming = [record for record in incoming_records if record is not None]
        with self._lock:
            if replace:
                self._save_payload([asdict(record) for record in incoming])
                return len(incoming)

            existing = [self._record_from_payload(item) for item in self._load_payload()]
            records = [record for record in existing if record is not None]
            by_id = {record.entity_id: index for index, record in enumerate(records)}
            imported = 0
            for record in incoming:
                if record.entity_id in by_id:
                    records[by_id[record.entity_id]] = record
                else:
                    records.append(record)
                imported += 1
            self._save_payload([asdict(record) for record in records])
            return imported

    def rename_entity(
        self,
        *,
        entity_id: str,
        label: str,
        aliases: list[str] | None = None,
        notes: str | None = None,
    ) -> MemoryEntityRecord | None:
        clean_label = label.strip()
        if not clean_label:
            raise ValueError("Memory entity label is required")
        with self._lock:
            records = [self._record_from_payload(item) for item in self._load_payload()]
            records = [record for record in records if record is not None]
            for record in records:
                if record.entity_id != entity_id:
                    continue
                old_label = record.label
                record.label = clean_label
                record.aliases = self._merge_lists(record.aliases, [old_label, *(aliases or [])])
                if notes and notes.strip():
                    record.notes = notes.strip()
                record.updated_at = datetime.now(UTC).isoformat()
                self._save_payload([asdict(item) for item in records])
                return record
        return None

    def update_entity(
        self,
        *,
        entity_id: str,
        attributes: dict[str, Any] | None = None,
        user_schema: dict[str, Any] | None = None,
        aliases: list[str] | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
        confidence: float | None = None,
        lifecycle_state: str | None = None,
    ) -> MemoryEntityRecord | None:
        with self._lock:
            records = [self._record_from_payload(item) for item in self._load_payload()]
            records = [record for record in records if record is not None]
            for record in records:
                if record.entity_id != entity_id:
                    continue
                if attributes is not None:
                    record.attributes = self._sanitize_mapping(attributes)
                if user_schema is not None:
                    record.user_schema = self._sanitize_mapping(user_schema)
                if aliases is not None:
                    record.aliases = self._sanitize_list(aliases)
                if tags is not None:
                    record.tags = self._sanitize_list(tags)
                if notes is not None:
                    record.notes = notes.strip() or None
                if confidence is not None:
                    record.confidence = self._clamp_confidence(confidence)
                if lifecycle_state is not None:
                    record.lifecycle_state = self._normalize_lifecycle(lifecycle_state)
                record.updated_at = datetime.now(UTC).isoformat()
                self._save_payload([asdict(item) for item in records])
                return record
        return None

    def set_lifecycle(
        self,
        *,
        entity_id: str,
        lifecycle_state: str,
        notes: str | None = None,
    ) -> MemoryEntityRecord | None:
        with self._lock:
            records = [self._record_from_payload(item) for item in self._load_payload()]
            records = [record for record in records if record is not None]
            for record in records:
                if record.entity_id != entity_id:
                    continue
                record.lifecycle_state = self._normalize_lifecycle(lifecycle_state)
                if notes and notes.strip():
                    record.notes = notes.strip()
                record.updated_at = datetime.now(UTC).isoformat()
                self._save_payload([asdict(item) for item in records])
                return record
        return None

    def mark_not_this(
        self,
        *,
        entity_id: str,
        rejected_label: str | None = None,
        notes: str | None = None,
    ) -> MemoryEntityRecord | None:
        with self._lock:
            records = [self._record_from_payload(item) for item in self._load_payload()]
            records = [record for record in records if record is not None]
            now_iso = datetime.now(UTC).isoformat()
            for record in records:
                if record.entity_id != entity_id:
                    continue
                rejected = self._sanitize_list(record.attributes.get("rejected_labels"))
                if rejected_label and rejected_label.strip():
                    rejected = self._merge_lists(rejected, [rejected_label])
                record.attributes["rejected_labels"] = rejected
                record.lifecycle_state = "uncertain"
                record.observations.append(
                    MemoryObservation(
                        observation_id=str(uuid4()),
                        source="correction",
                        modality="vision",
                        confidence=1.0,
                        notes=notes.strip() if notes else "Marked as not this memory",
                        observed_at=now_iso,
                    )
                )
                self._append_lifecycle_event(
                    record,
                    event_type="not_this",
                    target_state="uncertain",
                    confidence_after=self._clamp_confidence(record.confidence - 0.1),
                    reason=notes or "Marked as not this memory",
                    created_at=now_iso,
                )
                record.updated_at = now_iso
                self._save_payload([asdict(item) for item in records])
                return record
        return None

    def merge_entities(
        self,
        *,
        target_entity_id: str,
        source_entity_ids: list[str],
        notes: str | None = None,
    ) -> MemoryEntityRecord | None:
        clean_sources = [item.strip() for item in source_entity_ids if item.strip()]
        if not clean_sources:
            raise ValueError("At least one source entity is required")
        with self._lock:
            records = [self._record_from_payload(item) for item in self._load_payload()]
            records = [record for record in records if record is not None]
            target = next((record for record in records if record.entity_id == target_entity_id), None)
            if target is None:
                return None
            sources = [record for record in records if record.entity_id in clean_sources]
            if not sources:
                raise ValueError("No source entities found")
            now_iso = datetime.now(UTC).isoformat()
            for source in sources:
                if source.entity_id == target.entity_id:
                    continue
                target.aliases = self._merge_lists(target.aliases, [source.label, *source.aliases])
                target.tags = self._merge_lists(target.tags, source.tags)
                target.source_reference_ids = self._merge_lists(
                    target.source_reference_ids,
                    source.source_reference_ids,
                )
                target.attributes = {**source.attributes, **target.attributes}
                target.observations.extend(source.observations)
                target.confidence = max(target.confidence, source.confidence)
                source.lifecycle_state = "archived"
                source.attributes["merged_into_entity_id"] = target.entity_id
                source.updated_at = now_iso
            if notes and notes.strip():
                target.notes = notes.strip()
            target.updated_at = now_iso
            self._save_payload([asdict(item) for item in records])
            return target

    def split_entity(
        self,
        *,
        entity_id: str,
        new_label: str,
        observation_ids: list[str],
        notes: str | None = None,
    ) -> tuple[MemoryEntityRecord, MemoryEntityRecord] | None:
        clean_label = new_label.strip()
        if not clean_label:
            raise ValueError("New split entity label is required")
        selected_ids = {item.strip() for item in observation_ids if item.strip()}
        if not selected_ids:
            raise ValueError("At least one observation is required to split a memory")
        with self._lock:
            records = [self._record_from_payload(item) for item in self._load_payload()]
            records = [record for record in records if record is not None]
            original = next((record for record in records if record.entity_id == entity_id), None)
            if original is None:
                return None
            moved = [item for item in original.observations if item.observation_id in selected_ids]
            if not moved:
                raise ValueError("No matching observations found for split")
            now_iso = datetime.now(UTC).isoformat()
            original.observations = [item for item in original.observations if item.observation_id not in selected_ids]
            original.lifecycle_state = "uncertain"
            original.updated_at = now_iso
            new_entity = MemoryEntityRecord(
                entity_id=str(uuid4()),
                domain_type=original.domain_type,
                label=clean_label,
                attributes={"split_from_entity_id": original.entity_id},
                user_schema=dict(original.user_schema),
                aliases=[],
                tags=list(original.tags),
                notes=notes.strip() if notes else None,
                confidence=max(0.0, min(1.0, original.confidence)),
                lifecycle_state="candidate",
                observations=moved,
                source_reference_ids=[],
                created_at=now_iso,
                updated_at=now_iso,
            )
            records.append(new_entity)
            self._save_payload([asdict(item) for item in records])
            return original, new_entity

    def _find_index(self, records: list[MemoryEntityRecord], *, domain_type: str, label: str) -> int | None:
        normalized_label = label.strip().lower()
        for index, record in enumerate(records):
            if record.domain_type != domain_type:
                continue
            labels = [record.label, *record.aliases]
            if any(item.strip().lower() == normalized_label for item in labels):
                return index
        return None

    def _load_payload(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return payload if isinstance(payload, list) else []

    def _save_payload(self, payload: list[dict[str, Any]]) -> None:
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(self.path)

    def _record_from_payload(self, item: dict[str, Any]) -> MemoryEntityRecord | None:
        if not isinstance(item, dict):
            return None
        label = str(item.get("label") or "").strip()
        if not label:
            return None
        observations = []
        for observation in item.get("observations") or []:
            if not isinstance(observation, dict):
                continue
            observations.append(
                MemoryObservation(
                    observation_id=str(observation.get("observation_id") or uuid4()),
                    source=str(observation.get("source") or "manual"),
                    source_id=str(observation.get("source_id") or "") or None,
                    modality=str(observation.get("modality") or "vision"),
                    confidence=(
                        self._clamp_confidence(observation.get("confidence"))
                        if observation.get("confidence") is not None
                        else None
                    ),
                    notes=str(observation.get("notes") or "") or None,
                    observed_at=str(observation.get("observed_at") or "") or datetime.now(UTC).isoformat(),
                )
            )

        now_iso = datetime.now(UTC).isoformat()
        return MemoryEntityRecord(
            entity_id=str(item.get("entity_id") or uuid4()),
            domain_type=self.normalize_domain_type(str(item.get("domain_type") or "custom")),
            label=label,
            attributes=self._sanitize_mapping(item.get("attributes")),
            schema_version=str(item.get("schema_version") or "1.0"),
            user_schema=self._sanitize_mapping(item.get("user_schema")),
            aliases=self._sanitize_list(item.get("aliases")),
            tags=self._sanitize_list(item.get("tags")),
            notes=str(item.get("notes") or "") or None,
            confidence=self._clamp_confidence(item.get("confidence") or 0.0),
            lifecycle_state=self._normalize_lifecycle(str(item.get("lifecycle_state") or "candidate")),
            observations=observations,
            lifecycle_events=self._lifecycle_events_from_payload(item.get("lifecycle_events")),
            source_reference_ids=self._sanitize_list(item.get("source_reference_ids")),
            created_at=str(item.get("created_at") or "") or now_iso,
            updated_at=str(item.get("updated_at") or "") or now_iso,
        )

    def _apply_lifecycle_event(
        self,
        *,
        entity_id: str,
        event_type: str,
        confidence_delta: float,
        target_state: str,
        reason: str | None,
        source_id: str | None = None,
    ) -> MemoryEntityRecord | None:
        with self._lock:
            records = [self._record_from_payload(item) for item in self._load_payload()]
            records = [record for record in records if record is not None]
            now_iso = datetime.now(UTC).isoformat()
            for record in records:
                if record.entity_id != entity_id:
                    continue
                self._append_lifecycle_event(
                    record,
                    event_type=event_type,
                    target_state=target_state,
                    confidence_after=self._clamp_confidence(record.confidence + confidence_delta),
                    reason=reason,
                    created_at=now_iso,
                )
                record.observations.append(
                    MemoryObservation(
                        observation_id=str(uuid4()),
                        source="lifecycle",
                        source_id=source_id,
                        modality="vision",
                        confidence=record.confidence,
                        notes=reason,
                        observed_at=now_iso,
                    )
                )
                self._save_payload([asdict(item) for item in records])
                return record
        return None

    def _append_lifecycle_event(
        self,
        record: MemoryEntityRecord,
        *,
        event_type: str,
        target_state: str,
        confidence_after: float,
        reason: str | None,
        created_at: str,
    ) -> None:
        from_state = record.lifecycle_state
        confidence_before = record.confidence
        record.lifecycle_state = self._normalize_lifecycle(target_state)
        record.confidence = self._clamp_confidence(confidence_after)
        record.lifecycle_events.append(
            MemoryLifecycleEvent(
                event_id=str(uuid4()),
                event_type=event_type,
                from_state=from_state,
                to_state=record.lifecycle_state,
                confidence_before=confidence_before,
                confidence_after=record.confidence,
                reason=reason.strip() if reason else None,
                created_at=created_at,
            )
        )
        record.updated_at = created_at

    def _lifecycle_events_from_payload(self, value: object) -> list[MemoryLifecycleEvent]:
        if not isinstance(value, list):
            return []
        events: list[MemoryLifecycleEvent] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            now_iso = datetime.now(UTC).isoformat()
            events.append(
                MemoryLifecycleEvent(
                    event_id=str(item.get("event_id") or uuid4()),
                    event_type=str(item.get("event_type") or "updated"),
                    from_state=self._normalize_lifecycle(str(item.get("from_state") or "candidate")),
                    to_state=self._normalize_lifecycle(str(item.get("to_state") or "candidate")),
                    confidence_before=self._clamp_confidence(item.get("confidence_before") or 0.0),
                    confidence_after=self._clamp_confidence(item.get("confidence_after") or 0.0),
                    reason=str(item.get("reason") or "") or None,
                    created_at=str(item.get("created_at") or "") or now_iso,
                )
            )
        return events

    def _last_memory_time(self, record: MemoryEntityRecord) -> datetime:
        candidates = [record.updated_at, record.created_at]
        candidates.extend(observation.observed_at for observation in record.observations)
        parsed: list[datetime] = []
        for value in candidates:
            try:
                parsed.append(datetime.fromisoformat(value.replace("Z", "+00:00")))
            except (ValueError, AttributeError):
                continue
        if not parsed:
            return datetime.now(UTC)
        latest = max(parsed)
        return latest if latest.tzinfo else latest.replace(tzinfo=UTC)

    @staticmethod
    def normalize_domain_type(domain_type: str) -> str:
        normalized = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in domain_type.lower())
        normalized = normalized.strip("_-")
        return normalized or "custom"

    def _sanitize_mapping(self, value: object) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        clean: dict[str, Any] = {}
        for key, item in value.items():
            clean_key = str(key or "").strip()
            if not clean_key:
                continue
            clean[clean_key] = item
        return clean

    def _sanitize_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        seen: set[str] = set()
        clean: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if not text:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            clean.append(text)
        return clean

    def _merge_lists(self, existing: list[str], incoming: list[str] | None) -> list[str]:
        return self._sanitize_list([*existing, *(incoming or [])])

    def _normalize_lifecycle(self, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"candidate", "confirmed", "uncertain", "stale", "archived", "forgotten"}
        return normalized if normalized in allowed else "candidate"

    def _clamp_confidence(self, value: object) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = 0.0
        return round(max(0.0, min(1.0, confidence)), 6)
