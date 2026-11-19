"""HTTP routes for providers."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import get_current_user
from app.api.support import (
    _provider_card_item,
    _provider_privacy_flags,
    get_provider_selection_registry,
    provider_marketplace,
)
from app.core.config import settings
from app.models import User
from app.schemas import (
    ProviderConformanceListResponse,
    ProviderHealthItem,
    ProviderHealthResponse,
    ProviderMarketplaceResponse,
    ProviderPluginListResponse,
    ProviderSelectionRequest,
    ProviderSelectionResponse,
)
from app.services.model_assets import provider_health
from app.services.provider_conformance import evaluate_provider_catalog
from app.services.provider_marketplace import (
    PROVIDER_CAPABILITIES,
    ProviderSelectionRegistry,
)

router = APIRouter(tags=["providers"])


@router.get("/api/v1/providers", response_model=ProviderMarketplaceResponse)
def list_providers(current_user: User = Depends(get_current_user)) -> ProviderMarketplaceResponse:
    user_id = str(current_user.id)
    local_only, allow_hosted = _provider_privacy_flags(user_id)
    cards = provider_marketplace.list_cards(
        privacy_local_only=local_only, allow_hosted=allow_hosted
    )
    selections = get_provider_selection_registry(user_id).get().selections
    return ProviderMarketplaceResponse(
        providers=[_provider_card_item(card) for card in cards],
        capabilities=sorted(PROVIDER_CAPABILITIES),
        selections=selections,
    )


@router.get("/api/v1/provider-plugins", response_model=ProviderPluginListResponse)
def list_provider_plugins(
    current_user: User = Depends(get_current_user),
) -> ProviderPluginListResponse:
    user_id = str(current_user.id)
    local_only, allow_hosted = _provider_privacy_flags(user_id)
    plugin_cards = [
        provider_marketplace._card_with_policy_status(
            card,
            privacy_local_only=local_only,
            allow_hosted=allow_hosted,
        )
        for card in provider_marketplace.plugin_registry.list_cards()
    ]
    return ProviderPluginListResponse(
        plugins=[_provider_card_item(card) for card in plugin_cards],
        manifest_dirs=[path.name for path in provider_marketplace.plugin_registry.manifest_dirs],
    )


@router.get("/api/v1/provider-conformance", response_model=ProviderConformanceListResponse)
def list_provider_conformance(
    current_user: User = Depends(get_current_user),
) -> ProviderConformanceListResponse:
    user_id = str(current_user.id)
    local_only, allow_hosted = _provider_privacy_flags(user_id)
    cards = provider_marketplace.list_cards(
        privacy_local_only=local_only, allow_hosted=allow_hosted
    )
    return ProviderConformanceListResponse(**evaluate_provider_catalog(cards))


@router.get("/api/v1/providers/health", response_model=ProviderHealthResponse)
def list_provider_health(current_user: User = Depends(get_current_user)) -> ProviderHealthResponse:
    _ = current_user
    return ProviderHealthResponse(
        providers=[
            ProviderHealthItem(
                provider_id=item.provider_id,
                ready=item.ready,
                status=item.status,
                detail=item.detail,
                model_cache_dir=item.model_cache_dir,
                optional_dependencies=item.optional_dependencies,
            )
            for item in provider_health(settings.model_cache_dir)
        ]
    )


@router.get("/api/v1/providers/selection", response_model=ProviderSelectionResponse)
def get_provider_selection(
    current_user: User = Depends(get_current_user),
) -> ProviderSelectionResponse:
    user_id = str(current_user.id)
    local_only, allow_hosted = _provider_privacy_flags(user_id)
    record = get_provider_selection_registry(user_id).get()
    provider_id = record.selections.get("face_embedding") or "local-face-embedding"
    card = provider_marketplace.find_card(
        provider_id, privacy_local_only=local_only, allow_hosted=allow_hosted
    )
    if card is None:
        card = provider_marketplace.find_card(
            "local-face-embedding",
            privacy_local_only=local_only,
            allow_hosted=allow_hosted,
        )
    assert card is not None
    return ProviderSelectionResponse(
        selections=record.selections,
        updated_at=datetime.fromisoformat(record.updated_at),
        provider=_provider_card_item(card),
    )


@router.put("/api/v1/providers/selection", response_model=ProviderSelectionResponse)
def update_provider_selection(
    payload: ProviderSelectionRequest,
    current_user: User = Depends(get_current_user),
) -> ProviderSelectionResponse:
    user_id = str(current_user.id)
    local_only, allow_hosted = _provider_privacy_flags(user_id)
    capability = ProviderSelectionRegistry.normalize_capability(payload.capability)
    if capability not in PROVIDER_CAPABILITIES:
        raise HTTPException(status_code=400, detail="Unsupported provider capability")
    card = provider_marketplace.find_card(
        payload.provider_id,
        privacy_local_only=local_only,
        allow_hosted=allow_hosted,
    )
    if card is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    if capability not in card.capabilities:
        raise HTTPException(
            status_code=400, detail="Provider does not support requested capability"
        )
    if card.status == "blocked_by_privacy_policy":
        raise HTTPException(status_code=403, detail="Provider is blocked by privacy settings")
    record = get_provider_selection_registry(user_id).set_selection(
        capability=capability,
        provider_id=card.provider_id,
    )
    return ProviderSelectionResponse(
        selections=record.selections,
        updated_at=datetime.fromisoformat(record.updated_at),
        provider=_provider_card_item(card),
    )
