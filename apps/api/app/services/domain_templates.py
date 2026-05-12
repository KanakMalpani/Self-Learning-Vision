from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class MemoryDomainTemplate:
    template_id: str
    domain_type: str
    display_name: str
    description: str
    fields: dict[str, str] = field(default_factory=dict)
    default_attributes: dict[str, Any] = field(default_factory=dict)
    recommended_tags: list[str] = field(default_factory=list)
    observation_modality: str = "vision"
    lifecycle_state: str = "candidate"
    confidence: float = 0.5
    prompts: list[str] = field(default_factory=list)

    def to_schema(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "domain_type": self.domain_type,
            "display_name": self.display_name,
            "description": self.description,
            "fields": dict(self.fields),
            "default_attributes": dict(self.default_attributes),
            "recommended_tags": list(self.recommended_tags),
            "observation_modality": self.observation_modality,
            "lifecycle_state": self.lifecycle_state,
            "confidence": self.confidence,
            "prompts": list(self.prompts),
        }

    def user_schema(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "label": self.display_name,
            "fields": dict(self.fields),
            "prompts": list(self.prompts),
        }


BUILT_IN_DOMAIN_TEMPLATES = [
    MemoryDomainTemplate(
        template_id="person",
        domain_type="person",
        display_name="Person",
        description="A user-confirmed person remembered through face, context, or manual notes.",
        fields={
            "default_recognition_domain": "string",
            "relationship": "string",
            "last_known_context": "string",
            "consent_scope": "string",
        },
        default_attributes={"default_recognition_domain": "face", "consent_scope": "local_user_memory"},
        recommended_tags=["person", "identity", "local-memory"],
        observation_modality="face",
        lifecycle_state="candidate",
        confidence=0.6,
        prompts=["Who is this?", "Where do I know them from?", "What should I remember carefully?"],
    ),
    MemoryDomainTemplate(
        template_id="object",
        domain_type="object",
        display_name="Object",
        description="A recurring physical object, tool, device, or visual item.",
        fields={
            "category": "string",
            "color": "string",
            "location_hint": "string",
            "condition": "string",
        },
        recommended_tags=["object", "visual-memory"],
        prompts=["What is this object?", "Where is it usually seen?", "What condition is it in?"],
    ),
    MemoryDomainTemplate(
        template_id="place",
        domain_type="place",
        display_name="Place",
        description="A recognizable location, room, venue, route, or environment.",
        fields={
            "place_type": "string",
            "address_or_area": "string",
            "visual_landmarks": "list[string]",
            "access_notes": "string",
        },
        recommended_tags=["place", "location"],
        prompts=["Where is this?", "What visual landmarks make it recognizable?"],
    ),
    MemoryDomainTemplate(
        template_id="scene",
        domain_type="scene",
        display_name="Scene",
        description="A visual context such as a meeting, workspace state, shelf state, or setup.",
        fields={
            "scene_type": "string",
            "participants_or_objects": "list[string]",
            "state": "string",
            "environment": "string",
        },
        recommended_tags=["scene", "context"],
        prompts=["What is happening here?", "What changed since the last observation?"],
    ),
    MemoryDomainTemplate(
        template_id="event",
        domain_type="event",
        display_name="Event",
        description="A time-bound happening remembered from visual evidence and user notes.",
        fields={
            "event_type": "string",
            "date_or_period": "string",
            "participants": "list[string]",
            "outcome": "string",
        },
        recommended_tags=["event", "timeline"],
        prompts=["What happened?", "Who or what was involved?", "What outcome matters?"],
    ),
    MemoryDomainTemplate(
        template_id="document",
        domain_type="document",
        display_name="Document",
        description="A seen document, form, receipt, label, page, sign, or OCR target.",
        fields={
            "document_type": "string",
            "issuer_or_source": "string",
            "visible_text_summary": "string",
            "date_or_version": "string",
        },
        recommended_tags=["document", "ocr"],
        prompts=["What type of document is this?", "What text should be remembered?"],
    ),
    MemoryDomainTemplate(
        template_id="product",
        domain_type="product",
        display_name="Product",
        description="A product, SKU, package, part, or branded item remembered visually.",
        fields={
            "brand": "string",
            "model_or_sku": "string",
            "category": "string",
            "barcode_or_serial": "string",
            "condition": "string",
        },
        recommended_tags=["product", "catalog"],
        prompts=["What product is this?", "What SKU or identifying mark is visible?"],
    ),
    MemoryDomainTemplate(
        template_id="inventory",
        domain_type="inventory",
        display_name="Inventory Item",
        description="A stock item, asset, tool, or supply tracked through visual observations.",
        fields={
            "asset_id": "string",
            "quantity": "number",
            "storage_location": "string",
            "reorder_state": "string",
            "owner_or_team": "string",
        },
        recommended_tags=["inventory", "asset"],
        prompts=["How many are present?", "Where is it stored?", "Does it need action?"],
    ),
]


class DomainTemplateCatalog:
    def __init__(self, templates: list[MemoryDomainTemplate] | None = None) -> None:
        self._templates = templates or BUILT_IN_DOMAIN_TEMPLATES

    def list_templates(self) -> list[MemoryDomainTemplate]:
        return sorted(self._templates, key=lambda item: item.display_name.lower())

    def find(self, template_id: str) -> MemoryDomainTemplate | None:
        needle = self._normalize(template_id)
        for template in self._templates:
            if template.template_id == needle or template.domain_type == needle:
                return template
        return None

    def build_entity_payload(
        self,
        *,
        template_id: str,
        label: str,
        attributes: dict[str, Any] | None = None,
        aliases: list[str] | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
        confidence: float | None = None,
        lifecycle_state: str | None = None,
    ) -> dict[str, Any]:
        template = self.find(template_id)
        if template is None:
            raise ValueError(f"Unknown memory domain template: {template_id}")
        merged_tags = _dedupe([*template.recommended_tags, *(tags or [])])
        return {
            "domain_type": template.domain_type,
            "label": label,
            "attributes": {**template.default_attributes, **(attributes or {})},
            "user_schema": template.user_schema(),
            "aliases": _dedupe(aliases or []),
            "tags": merged_tags,
            "notes": notes,
            "confidence": template.confidence if confidence is None else confidence,
            "lifecycle_state": lifecycle_state or template.lifecycle_state,
            "observation_modality": template.observation_modality,
        }

    def _normalize(self, value: str) -> str:
        normalized = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value.lower())
        return normalized.strip("_-")


def template_payloads() -> list[dict[str, Any]]:
    return [asdict(template) for template in BUILT_IN_DOMAIN_TEMPLATES]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(text)
    return out
