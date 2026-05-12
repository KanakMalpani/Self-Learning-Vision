from __future__ import annotations

from pathlib import Path

from app.services.memory_entity_registry import MemoryEntityRegistry
from app.services.privacy_settings_registry import PrivacySettingsRegistry
from app.services.privacy_vault import PrivacyVaultService


def test_privacy_settings_default_to_local_only_and_no_sensitive_export(tmp_path: Path) -> None:
    registry = PrivacySettingsRegistry(tmp_path / "settings.json")

    settings = registry.get()

    assert settings.local_only_mode is True
    assert settings.allow_hosted_providers is False
    assert settings.export_include_biometric_embeddings is False
    assert settings.export_include_upload_paths is False


def test_privacy_settings_sanitize_domain_visibility(tmp_path: Path) -> None:
    registry = PrivacySettingsRegistry(tmp_path / "settings.json")

    updated = registry.update(
        allow_hosted_providers=True,
        export_include_upload_paths=True,
        domain_visibility={"person": "hidden", "object": "exportable", "place": "surprise"},
    )

    assert updated.allow_hosted_providers is True
    assert updated.export_include_upload_paths is True
    assert updated.domain_visibility == {
        "person": "hidden",
        "object": "exportable",
        "place": "private",
    }


def test_privacy_vault_encrypts_and_decrypts_payload() -> None:
    service = PrivacyVaultService()
    payload = {
        "memory_entities": [{"entity_id": "entity-a", "label": "Ada"}],
        "redaction": {"biometric_embeddings_included": False},
    }

    encrypted = service.encrypt_export(payload, "correct horse battery staple")
    decrypted = service.decrypt_export(encrypted, "correct horse battery staple")

    assert encrypted["encrypted"] is True
    assert "ciphertext" in encrypted
    assert "memory_entities" not in encrypted
    assert decrypted["payload"] == payload


def test_memory_entity_import_merges_redacted_vault_entities(tmp_path: Path) -> None:
    registry = MemoryEntityRegistry(tmp_path / "entities.json")
    existing = registry.upsert_entity(domain_type="person", label="Ada", confidence=0.8)
    payload = registry.snapshot()
    payload[0]["label"] = "Ada Lovelace"

    imported = registry.import_entities(payload, replace=False)

    updated = registry.find(existing.entity_id)
    assert imported == 1
    assert updated is not None
    assert updated.label == "Ada Lovelace"
    assert updated.confidence == 0.8
