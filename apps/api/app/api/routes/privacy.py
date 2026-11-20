"""HTTP routes for privacy."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import get_current_user
from app.api.support import (
    _privacy_settings_item,
    get_privacy_settings_registry,
)
from app.models import User
from app.schemas import (
    PrivacySettingsItem,
    PrivacySettingsUpdateRequest,
)

router = APIRouter(tags=["privacy"])


@router.get("/api/v1/privacy/settings", response_model=PrivacySettingsItem)
def get_privacy_settings(current_user: User = Depends(get_current_user)) -> PrivacySettingsItem:
    return _privacy_settings_item(get_privacy_settings_registry(str(current_user.id)).get())


@router.put("/api/v1/privacy/settings", response_model=PrivacySettingsItem)
def update_privacy_settings(
    payload: PrivacySettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> PrivacySettingsItem:
    updated = get_privacy_settings_registry(str(current_user.id)).update(
        local_only_mode=payload.local_only_mode,
        allow_hosted_providers=payload.allow_hosted_providers,
        export_include_biometric_embeddings=False,
        export_include_upload_paths=payload.export_include_upload_paths,
        data_retention_days=payload.data_retention_days,
        domain_visibility=payload.domain_visibility,
    )
    return _privacy_settings_item(updated)
