from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.domain_templates import DomainTemplateCatalog
from app.services.memory_entity_registry import MemoryEntityRecord


@dataclass(frozen=True)
class DomainQuestionDraft:
    question_type: str
    prompt: str
    domain_type: str
    priority: int
    confidence: float
    suggested_action: str
    dedupe_key: str
    context: dict[str, Any]


class DomainActiveLearningPlanner:
    def __init__(self, template_catalog: DomainTemplateCatalog | None = None) -> None:
        self.template_catalog = template_catalog or DomainTemplateCatalog()

    def draft_questions(self, entity: MemoryEntityRecord) -> list[DomainQuestionDraft]:
        template = self.template_catalog.find(entity.domain_type)
        fields = template.fields if template else {}
        missing_fields = [
            field_name
            for field_name in fields
            if _is_missing(entity.attributes.get(field_name))
        ]
        prompts = template.prompts if template else []

        drafts: list[DomainQuestionDraft] = []
        if missing_fields:
            drafts.append(
                DomainQuestionDraft(
                    question_type="review_memory",
                    prompt=self._field_prompt(entity, missing_fields, prompts),
                    domain_type=entity.domain_type,
                    priority=70,
                    confidence=entity.confidence,
                    suggested_action="fill_missing_memory_fields",
                    dedupe_key=f"domain_review:{entity.entity_id}:missing_fields:{','.join(missing_fields)}",
                    context={
                        "entity_id": entity.entity_id,
                        "label": entity.label,
                        "missing_fields": missing_fields,
                        "template_id": template.template_id if template else None,
                    },
                )
            )

        if entity.lifecycle_state in {"candidate", "uncertain"}:
            drafts.append(
                DomainQuestionDraft(
                    question_type="review_memory",
                    prompt=f"Should '{entity.label}' be trusted as a {entity.domain_type} memory?",
                    domain_type=entity.domain_type,
                    priority=80 if entity.lifecycle_state == "uncertain" else 60,
                    confidence=entity.confidence,
                    suggested_action="confirm_or_correct_memory",
                    dedupe_key=f"domain_review:{entity.entity_id}:trust_state:{entity.lifecycle_state}",
                    context={
                        "entity_id": entity.entity_id,
                        "label": entity.label,
                        "lifecycle_state": entity.lifecycle_state,
                    },
                )
            )

        return drafts

    def _field_prompt(
        self,
        entity: MemoryEntityRecord,
        missing_fields: list[str],
        prompts: list[str],
    ) -> str:
        if entity.domain_type == "inventory":
            return f"What quantity, location, or reorder state should be remembered for '{entity.label}'?"
        if entity.domain_type == "document":
            return f"What visible text or document type should be remembered for '{entity.label}'?"
        if entity.domain_type == "product":
            return f"What brand, model, SKU, or condition should be remembered for '{entity.label}'?"
        if entity.domain_type == "place":
            return f"What landmarks or location details identify '{entity.label}'?"
        if entity.domain_type == "scene":
            return f"What changed or matters in the scene '{entity.label}'?"
        if entity.domain_type == "event":
            return f"What happened, who was involved, and what outcome matters for '{entity.label}'?"
        if prompts:
            return prompts[0]
        field_list = ", ".join(missing_fields[:4])
        return f"What should be remembered for '{entity.label}'? Missing fields: {field_list}."


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False
