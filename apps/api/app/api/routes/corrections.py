"""HTTP routes for corrections."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import get_current_user
from app.api.support import (
    _correction_log_item,
    _memory_entity_item,
    _record_correction,
    get_correction_log_registry,
    get_memory_entity_registry,
)
from app.models import User
from app.schemas import (
    CorrectionListResponse,
    CorrectionResponse,
    MemoryEntityForgetRequest,
    MemoryEntityMergeRequest,
    MemoryEntityNotThisRequest,
    MemoryEntityRenameRequest,
    MemoryEntitySplitRequest,
)

router = APIRouter(tags=["corrections"])


@router.get("/api/v1/corrections", response_model=CorrectionListResponse)
def list_corrections(current_user: User = Depends(get_current_user)) -> CorrectionListResponse:
    corrections = get_correction_log_registry(str(current_user.id)).list_records()
    return CorrectionListResponse(corrections=[_correction_log_item(item) for item in corrections])


@router.post("/api/v1/corrections/{correction_id}/undo", response_model=CorrectionResponse)
def undo_correction(
    correction_id: str,
    current_user: User = Depends(get_current_user),
) -> CorrectionResponse:
    user_id = str(current_user.id)
    log_registry = get_correction_log_registry(user_id)
    correction = log_registry.find(correction_id)
    if not correction:
        raise HTTPException(status_code=404, detail="Correction not found")
    if correction.undone:
        return CorrectionResponse(correction=_correction_log_item(correction), entity=None)

    entity_registry = get_memory_entity_registry(user_id)
    entity_registry.restore_snapshot(correction.before_entities)
    undone = log_registry.mark_undone(correction_id)
    if not undone:
        raise HTTPException(status_code=404, detail="Correction not found")
    restored = entity_registry.find(correction.target_entity_id)
    return CorrectionResponse(
        correction=_correction_log_item(undone),
        entity=_memory_entity_item(restored) if restored else None,
    )


@router.post(
    "/api/v1/memory-entities/{entity_id}/corrections/rename", response_model=CorrectionResponse
)
def rename_memory_entity(
    entity_id: str,
    payload: MemoryEntityRenameRequest,
    current_user: User = Depends(get_current_user),
) -> CorrectionResponse:
    user_id = str(current_user.id)
    registry = get_memory_entity_registry(user_id)
    before = registry.snapshot()
    record = registry.rename_entity(
        entity_id=entity_id,
        label=payload.label,
        aliases=payload.aliases,
        notes=payload.notes,
    )
    if not record:
        raise HTTPException(status_code=404, detail="Memory entity not found")
    after = registry.snapshot()
    correction = _record_correction(
        user_id=user_id,
        operation_type="rename",
        target_entity_id=entity_id,
        summary=f"Renamed memory entity to {record.label}",
        before_entities=before,
        after_entities=after,
        metadata={"label": record.label, "aliases": record.aliases},
    )
    return CorrectionResponse(
        correction=_correction_log_item(correction), entity=_memory_entity_item(record)
    )


@router.post(
    "/api/v1/memory-entities/{entity_id}/corrections/forget", response_model=CorrectionResponse
)
def forget_memory_entity(
    entity_id: str,
    payload: MemoryEntityForgetRequest,
    current_user: User = Depends(get_current_user),
) -> CorrectionResponse:
    user_id = str(current_user.id)
    registry = get_memory_entity_registry(user_id)
    before = registry.snapshot()
    record = registry.set_lifecycle(
        entity_id=entity_id, lifecycle_state=payload.mode, notes=payload.notes
    )
    if not record:
        raise HTTPException(status_code=404, detail="Memory entity not found")
    after = registry.snapshot()
    correction = _record_correction(
        user_id=user_id,
        operation_type="forget",
        target_entity_id=entity_id,
        summary=f"Set memory entity lifecycle to {record.lifecycle_state}",
        before_entities=before,
        after_entities=after,
        metadata={"mode": payload.mode},
    )
    return CorrectionResponse(
        correction=_correction_log_item(correction), entity=_memory_entity_item(record)
    )


@router.post(
    "/api/v1/memory-entities/{entity_id}/corrections/not-this", response_model=CorrectionResponse
)
def mark_memory_entity_not_this(
    entity_id: str,
    payload: MemoryEntityNotThisRequest,
    current_user: User = Depends(get_current_user),
) -> CorrectionResponse:
    user_id = str(current_user.id)
    registry = get_memory_entity_registry(user_id)
    before = registry.snapshot()
    record = registry.mark_not_this(
        entity_id=entity_id,
        rejected_label=payload.rejected_label,
        notes=payload.notes,
    )
    if not record:
        raise HTTPException(status_code=404, detail="Memory entity not found")
    after = registry.snapshot()
    correction = _record_correction(
        user_id=user_id,
        operation_type="not_this",
        target_entity_id=entity_id,
        summary="Marked memory entity as an incorrect match",
        before_entities=before,
        after_entities=after,
        metadata={"rejected_label": payload.rejected_label},
    )
    return CorrectionResponse(
        correction=_correction_log_item(correction), entity=_memory_entity_item(record)
    )


@router.post(
    "/api/v1/memory-entities/{entity_id}/corrections/merge", response_model=CorrectionResponse
)
def merge_memory_entities(
    entity_id: str,
    payload: MemoryEntityMergeRequest,
    current_user: User = Depends(get_current_user),
) -> CorrectionResponse:
    user_id = str(current_user.id)
    registry = get_memory_entity_registry(user_id)
    before = registry.snapshot()
    try:
        record = registry.merge_entities(
            target_entity_id=entity_id,
            source_entity_ids=payload.source_entity_ids,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not record:
        raise HTTPException(status_code=404, detail="Memory entity not found")
    after = registry.snapshot()
    related = [
        item
        for item in registry.list_entities()
        if item.entity_id in set(payload.source_entity_ids)
    ]
    correction = _record_correction(
        user_id=user_id,
        operation_type="merge",
        target_entity_id=entity_id,
        summary=f"Merged {len(payload.source_entity_ids)} memory entity/entities into {record.label}",
        before_entities=before,
        after_entities=after,
        metadata={"source_entity_ids": payload.source_entity_ids},
    )
    return CorrectionResponse(
        correction=_correction_log_item(correction),
        entity=_memory_entity_item(record),
        related_entities=[_memory_entity_item(item) for item in related],
    )


@router.post(
    "/api/v1/memory-entities/{entity_id}/corrections/split", response_model=CorrectionResponse
)
def split_memory_entity(
    entity_id: str,
    payload: MemoryEntitySplitRequest,
    current_user: User = Depends(get_current_user),
) -> CorrectionResponse:
    user_id = str(current_user.id)
    registry = get_memory_entity_registry(user_id)
    before = registry.snapshot()
    try:
        result = registry.split_entity(
            entity_id=entity_id,
            new_label=payload.new_label,
            observation_ids=payload.observation_ids,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail="Memory entity not found")
    original, new_entity = result
    after = registry.snapshot()
    correction = _record_correction(
        user_id=user_id,
        operation_type="split",
        target_entity_id=entity_id,
        summary=f"Split observations into new memory entity {new_entity.label}",
        before_entities=before,
        after_entities=after,
        metadata={
            "new_entity_id": new_entity.entity_id,
            "observation_ids": payload.observation_ids,
        },
    )
    return CorrectionResponse(
        correction=_correction_log_item(correction),
        entity=_memory_entity_item(original),
        related_entities=[_memory_entity_item(new_entity)],
    )
