"""HTTP routes for data controls."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.support import (
    _build_user_export_payload,
    _safe_remove_tree,
    get_memory_entity_registry,
    privacy_vault_service,
    user_registry_directories,
)
from app.core.config import settings
from app.core.db import get_db
from app.models import MemoryRun, Upload, User
from app.schemas import (
    VaultExportRequest,
    VaultImportRequest,
    VaultImportResponse,
)
from app.services.privacy_vault import VaultEncryptionUnavailable

router = APIRouter(tags=["data_controls"])


@router.get("/api/v1/data/export")
def export_user_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    return JSONResponse(_build_user_export_payload(db=db, current_user=current_user))


@router.post("/api/v1/data/vault/export")
def export_user_vault(
    payload: VaultExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    export_payload = _build_user_export_payload(db=db, current_user=current_user)
    try:
        vault = (
            privacy_vault_service.encrypt_export(export_payload, payload.passphrase or "")
            if payload.encrypt
            else privacy_vault_service.wrap_plain_export(export_payload)
        )
    except VaultEncryptionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return JSONResponse(vault)


@router.post("/api/v1/data/vault/import", response_model=VaultImportResponse)
def import_user_vault(
    payload: VaultImportRequest,
    current_user: User = Depends(get_current_user),
) -> VaultImportResponse:
    vault = payload.vault
    encrypted = bool(vault.get("encrypted"))
    try:
        if encrypted:
            wrapped = privacy_vault_service.decrypt_export(vault, payload.passphrase or "")
        else:
            wrapped = vault
    except VaultEncryptionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if wrapped.get("format") != privacy_vault_service.format_version:
        raise HTTPException(status_code=400, detail="Vault format is not supported")
    vault_payload = wrapped.get("payload")
    if not isinstance(vault_payload, dict):
        raise HTTPException(status_code=400, detail="Vault payload is missing")
    memory_entities = vault_payload.get("memory_entities")
    if not isinstance(memory_entities, list):
        memory_entities = []
    imported = get_memory_entity_registry(str(current_user.id)).import_entities(
        [item for item in memory_entities if isinstance(item, dict)],
        replace=payload.replace_memory_entities,
    )
    return VaultImportResponse(
        imported_entities=imported,
        encrypted=encrypted,
        format=str(wrapped.get("format") or ""),
    )


@router.delete("/api/v1/data/purge", status_code=204)
def purge_user_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    for memory_run in db.query(MemoryRun).filter(MemoryRun.user_id == current_user.id).all():
        db.delete(memory_run)

    uploads = db.query(Upload).filter(Upload.user_id == current_user.id).all()
    for upload in uploads:
        file_path = Path(upload.file_path)
        db.delete(upload)
        if file_path.exists():
            file_path.unlink()

    storage_root = Path(settings.storage_dir)
    for directory in user_registry_directories(str(current_user.id)):
        _safe_remove_tree(directory, storage_root)
    db.commit()
    return Response(status_code=204)
