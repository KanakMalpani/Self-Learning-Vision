from __future__ import annotations

from pathlib import Path

import pytest

from app.services.provider_marketplace import (
    PROVIDER_CAPABILITIES,
    ProviderMarketplace,
    ProviderPluginRegistry,
    ProviderSelectionRegistry,
)


def test_provider_marketplace_lists_core_capabilities() -> None:
    marketplace = ProviderMarketplace()

    cards = marketplace.list_cards(privacy_local_only=True, allow_hosted=False)
    by_id = {card.provider_id: card for card in cards}

    assert "face_embedding" in PROVIDER_CAPABILITIES
    assert by_id["local-face-embedding"].status in {"ready", "unavailable"}
    assert by_id["local-face-embedding"].images_leave_device is False
    assert by_id["template-paid-provider"].status == "blocked_by_privacy_policy"
    assert "multimodal_reasoning" in by_id["template-paid-provider"].capabilities


def test_provider_marketplace_allows_hosted_when_privacy_allows() -> None:
    marketplace = ProviderMarketplace()

    card = marketplace.find_card(
        "template-paid-provider",
        privacy_local_only=False,
        allow_hosted=True,
    )

    assert card is not None
    assert card.status in {"ready", "not_configured"}
    assert card.images_leave_device is True


def test_provider_selection_registry_persists_selection(tmp_path: Path) -> None:
    registry = ProviderSelectionRegistry(tmp_path / "providers.json")

    record = registry.set_selection(
        capability="face-embedding",
        provider_id="local-face-embedding",
    )

    assert record.selections["face_embedding"] == "local-face-embedding"
    assert registry.selected_provider_for("face_embedding") == "local-face-embedding"


def test_provider_selection_registry_rejects_unknown_capability(tmp_path: Path) -> None:
    registry = ProviderSelectionRegistry(tmp_path / "providers.json")

    with pytest.raises(ValueError):
        registry.set_selection(capability="telepathy", provider_id="local-face-embedding")


def test_provider_plugin_registry_loads_manifest_cards(tmp_path: Path) -> None:
    manifest = tmp_path / "local-plugin.json"
    manifest.write_text(
        """
        {
          "provider_id": "local-demo-plugin",
          "display_name": "Local Demo Plugin",
          "mode": "local_free",
          "capabilities": ["face_embedding", "ocr", "telepathy"],
          "status": "manifest_ready",
          "images_leave_device": false,
          "entrypoint": "app.providers.local:LocalFaceEmbeddingProvider"
        }
        """,
        encoding="utf-8",
    )
    registry = ProviderPluginRegistry([tmp_path], include_default=False)

    cards = registry.list_cards()

    assert len(cards) == 1
    assert cards[0].provider_id == "local-demo-plugin"
    assert cards[0].capabilities == ["face_embedding", "ocr"]
    assert cards[0].plugin_source == "manifest"
    assert cards[0].entrypoint == "app.providers.local:LocalFaceEmbeddingProvider"


def test_provider_marketplace_includes_file_backed_plugins(tmp_path: Path) -> None:
    manifest = tmp_path / "local-plugin.json"
    manifest.write_text(
        """
        {
          "provider_id": "local-demo-plugin",
          "display_name": "Local Demo Plugin",
          "mode": "local_free",
          "capabilities": ["face_embedding"],
          "status": "manifest_ready",
          "images_leave_device": false,
          "entrypoint": "app.providers.local:LocalFaceEmbeddingProvider"
        }
        """,
        encoding="utf-8",
    )
    marketplace = ProviderMarketplace(plugin_registry=ProviderPluginRegistry([tmp_path], include_default=False))

    card = marketplace.find_card("local-demo-plugin", privacy_local_only=True, allow_hosted=False)
    provider = marketplace.build_face_embedding_provider("local-demo-plugin")

    assert card is not None
    assert card.status == "manifest_ready"
    assert provider is not None
    assert provider.name == "local-face-embedding"
