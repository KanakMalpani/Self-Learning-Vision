from __future__ import annotations

from app.services.domain_templates import DomainTemplateCatalog
from app.services.memory_entity_registry import RESERVED_DOMAIN_TYPES


def test_domain_template_catalog_covers_core_visual_domains() -> None:
    catalog = DomainTemplateCatalog()
    templates = {template.domain_type: template for template in catalog.list_templates()}

    for domain_type in ["person", "object", "place", "scene", "event", "document", "product", "inventory"]:
        assert domain_type in templates
        assert domain_type in RESERVED_DOMAIN_TYPES
        assert templates[domain_type].fields
        assert templates[domain_type].prompts


def test_domain_template_builds_entity_payload_with_overrides() -> None:
    catalog = DomainTemplateCatalog()

    payload = catalog.build_entity_payload(
        template_id="product",
        label="Camera Lens",
        attributes={"brand": "DemoOptics", "model_or_sku": "DX-50"},
        tags=["photography"],
        confidence=0.91,
        lifecycle_state="confirmed",
    )

    assert payload["domain_type"] == "product"
    assert payload["attributes"]["brand"] == "DemoOptics"
    assert payload["attributes"]["model_or_sku"] == "DX-50"
    assert payload["user_schema"]["template_id"] == "product"
    assert payload["tags"] == ["product", "catalog", "photography"]
    assert payload["confidence"] == 0.91
    assert payload["lifecycle_state"] == "confirmed"
