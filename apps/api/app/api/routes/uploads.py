"""HTTP routes for uploads."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.support import (
    face_service,
    logger,
    storage_service,
)
from app.core.db import get_db
from app.models import Upload, User
from app.schemas import (
    UploadResponse,
)

router = APIRouter(tags=["uploads"])


@router.post("/api/v1/upload", response_model=UploadResponse)
def upload_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadResponse:
    if not file.content_type or not file.content_type.startswith("image"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported")

    try:
        saved_path, file_id = storage_service.save_upload(file)
        face_boxes = face_service.detect_faces(saved_path)
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="Face detection failed")
    except Exception as exc:
        logger.error("Upload processing failed: %s", exc)
        raise HTTPException(status_code=500, detail="Upload processing failed")

    upload = Upload(
        user_id=current_user.id,
        file_path=saved_path,
        content_type=file.content_type,
        original_filename=file.filename or file_id,
        face_boxes=[box.model_dump() for box in face_boxes],
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    return UploadResponse(upload_id=upload.id, face_boxes=face_boxes)


@router.delete("/api/v1/upload/{upload_id}", status_code=204)
def delete_upload(
    upload_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    upload = (
        db.query(Upload).filter(Upload.id == upload_id, Upload.user_id == current_user.id).first()
    )
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    for memory_run in list(upload.memory_runs):
        db.delete(memory_run)
    file_path = Path(upload.file_path)
    db.delete(upload)
    db.commit()
    if file_path.exists():
        file_path.unlink()
    return Response(status_code=204)
