"""HTTP routes for identity."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.support import (
    _reference_item,
    _sync_person_entity_from_reference,
    face_service,
    get_core_recognition_service,
    get_face_reference_registry,
    get_unknown_face_registry,
    storage_service,
)
from app.core.db import get_db
from app.models import MemoryRun, Upload, User
from app.schemas import (
    FaceReferenceEnrollRequest,
    FaceReferenceEnrollResponse,
)

router = APIRouter(tags=["identity"])


@router.post(
    "/api/v1/identity/references", response_model=FaceReferenceEnrollResponse, status_code=201
)
def enroll_face_reference(
    name_or_alias: str = Form(...),
    file: UploadFile = File(...),
    selected_face_index: int = Form(0),
    notes: str | None = Form(default=None),
    tags: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
) -> FaceReferenceEnrollResponse:
    if not file.content_type or not file.content_type.startswith("image"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported")

    frame_bytes = file.file.read()
    if not frame_bytes:
        raise HTTPException(status_code=400, detail="Empty image payload")

    suffix = Path(file.filename or "reference.jpg").suffix or ".jpg"
    saved_path, _ = storage_service.save_bytes(frame_bytes, suffix=suffix, subdir="references")
    face_boxes = face_service.detect_faces(saved_path)
    if not face_boxes:
        raise HTTPException(status_code=400, detail="No face detected in reference image")
    if selected_face_index < 0 or selected_face_index >= len(face_boxes):
        raise HTTPException(status_code=400, detail="selected_face_index is out of range")

    parsed_tags = [tag.strip() for tag in (tags or "").split(",") if tag.strip()]
    user_service = get_core_recognition_service(str(current_user.id))
    user_registry = get_face_reference_registry(str(current_user.id))
    try:
        record, embedding = user_service.enroll_identity_from_face_box(
            name_or_alias=name_or_alias,
            image_path=saved_path,
            face_box=face_boxes[selected_face_index],
            face_index=selected_face_index,
            notes=notes,
            tags=parsed_tags,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Face embedding provider unavailable")

    _sync_person_entity_from_reference(
        user_id=str(current_user.id),
        reference=record,
        confidence=1.0,
    )
    return FaceReferenceEnrollResponse(
        reference=_reference_item(record),
        total_references=user_registry.reference_count(),
        embedding_dimensions=len(embedding),
    )


@router.post(
    "/api/v1/memory-runs/{memory_run_id}/reference",
    response_model=FaceReferenceEnrollResponse,
    status_code=201,
)
def enroll_memory_run_face_reference(
    memory_run_id: UUID,
    payload: FaceReferenceEnrollRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FaceReferenceEnrollResponse:
    memory_run = (
        db.query(MemoryRun)
        .filter(
            MemoryRun.id == memory_run_id,
            MemoryRun.user_id == current_user.id,
        )
        .first()
    )
    if not memory_run:
        raise HTTPException(status_code=404, detail="Memory run not found")

    upload = memory_run.upload
    if not upload:
        raise HTTPException(status_code=404, detail="Upload data missing")

    face_boxes = upload.face_boxes or []
    if payload.selected_face_index < 0 or payload.selected_face_index >= len(face_boxes):
        raise HTTPException(status_code=400, detail="selected_face_index is out of range")
    selected_box = face_boxes[payload.selected_face_index]
    if not isinstance(selected_box, dict):
        raise HTTPException(status_code=400, detail="Selected face data is invalid")

    user_service = get_core_recognition_service(str(current_user.id))
    user_registry = get_face_reference_registry(str(current_user.id))

    try:
        if payload.unknown_cluster_id:
            unknown_registry = get_unknown_face_registry(str(current_user.id))
            cluster = unknown_registry.find_cluster(payload.unknown_cluster_id)
            if cluster is None or cluster.promoted:
                raise HTTPException(status_code=404, detail="Unknown cluster not found")
            samples = unknown_registry.samples_for_cluster(payload.unknown_cluster_id)
            if not samples:
                raise HTTPException(status_code=400, detail="Unknown cluster has no usable samples")
            records = []
            for sample in samples:
                source_upload = db.get(Upload, UUID(sample.source_upload_id))
                records.append(
                    user_registry.add_reference(
                        name_or_alias=payload.name_or_alias,
                        embedding=sample.embedding,
                        provider=sample.provider,
                        source_image_path=source_upload.file_path if source_upload else None,
                        face_index=sample.face_index,
                        notes=payload.notes,
                        tags=payload.tags,
                    )
                )
            unknown_registry.mark_cluster_promoted(payload.unknown_cluster_id)
            record = records[0]
            embedding = samples[0].embedding
        else:
            record, embedding = user_service.enroll_identity_from_face_box(
                name_or_alias=payload.name_or_alias,
                image_path=upload.file_path,
                face_box=selected_box,
                face_index=payload.selected_face_index,
                notes=payload.notes,
                tags=payload.tags,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Face embedding provider unavailable")

    _sync_person_entity_from_reference(
        user_id=str(current_user.id),
        reference=record,
        confidence=1.0,
        source_upload_id=str(upload.id),
    )
    return FaceReferenceEnrollResponse(
        reference=_reference_item(record),
        total_references=user_registry.reference_count(),
        embedding_dimensions=len(embedding),
    )
