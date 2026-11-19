"""HTTP routes for memory runs."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.support import (
    _create_active_learning_questions,
    _local_memory_report,
    _store_unknown_sample_if_useful,
    _sync_person_entity_from_reference,
    _upload_recognition_response,
    get_core_recognition_service,
    get_face_reference_registry,
)
from app.core.db import get_db
from app.models import Activity, MemoryRun, MemoryRunStatus, Upload, User
from app.schemas import (
    ActivityEntry,
    MemoryRunCreateResponse,
    MemoryRunHistoryItem,
    MemoryRunHistoryResponse,
    MemoryRunRequest,
    MemoryRunResponse,
)
from app.schemas.memory_report import MemoryReport

router = APIRouter(tags=["memory_runs"])


@router.post("/api/v1/memory-runs", response_model=MemoryRunCreateResponse)
def create_memory_run(
    payload: MemoryRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MemoryRunCreateResponse:
    upload = (
        db.query(Upload)
        .filter(Upload.id == payload.upload_id, Upload.user_id == current_user.id)
        .first()
    )
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    face_boxes = upload.face_boxes or []
    if payload.selected_face_index < 0 or payload.selected_face_index >= len(face_boxes):
        raise HTTPException(status_code=400, detail="selected_face_index is out of range")
    selected_box = face_boxes[payload.selected_face_index]
    if not isinstance(selected_box, dict):
        raise HTTPException(status_code=400, detail="Selected face data is invalid")

    user_service = get_core_recognition_service(str(current_user.id))
    result = user_service.match_face_box(
        image_path=upload.file_path,
        face_box=selected_box,
        face_index=payload.selected_face_index,
    )
    unknown_payload = _store_unknown_sample_if_useful(
        user_id=str(current_user.id), upload_id=upload.id, result=result
    )
    recognition_result = _upload_recognition_response(result, **unknown_payload)
    if recognition_result.status == "matched" and recognition_result.top_candidate_name:
        reference = get_face_reference_registry(str(current_user.id)).find_by_name(
            name_or_alias=recognition_result.top_candidate_name
        )
        if reference:
            _sync_person_entity_from_reference(
                user_id=str(current_user.id),
                reference=reference,
                confidence=recognition_result.confidence,
                source_upload_id=str(upload.id),
            )

    memory_report_payload = _local_memory_report(recognition_result, payload.notes).model_dump(
        mode="json"
    )
    memory_run = MemoryRun(
        user_id=current_user.id,
        upload_id=upload.id,
        selected_face_index=payload.selected_face_index,
        notes=payload.notes or "",
        status=MemoryRunStatus.done,
        memory_report=memory_report_payload,
    )
    db.add(memory_run)
    db.flush()
    questions = _create_active_learning_questions(
        user_id=str(current_user.id),
        memory_run_id=memory_run.id,
        upload_id=upload.id,
        result=recognition_result,
    )
    if questions:
        recognition_summary = memory_report_payload.setdefault("recognition_summary", {})
        if isinstance(recognition_summary, dict):
            recognition_summary["active_learning_question_ids"] = [
                question.question_id for question in questions
            ]
            recognition_summary["active_learning_pending_count"] = len(questions)
        memory_run.memory_report = memory_report_payload
        db.add(
            Activity(
                memory_run_id=memory_run.id,
                stage="active_learning",
                message=f"Queued {len(questions)} active-learning question(s)",
            )
        )
    db.add(
        Activity(
            memory_run_id=memory_run.id, stage="done", message="Local vision memory run complete"
        )
    )
    db.commit()
    db.refresh(memory_run)
    return MemoryRunCreateResponse(
        memory_run_id=memory_run.id, recognition_result=recognition_result
    )


@router.get("/api/v1/memory-runs/{memory_run_id}", response_model=MemoryRunResponse)
def get_memory_run(
    memory_run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MemoryRunResponse:
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

    activities: list[ActivityEntry] = [
        ActivityEntry(
            stage=activity.stage, message=activity.message, created_at=activity.created_at
        )
        for activity in memory_run.activities
    ]
    memory_report = (
        MemoryReport.model_validate(memory_run.memory_report) if memory_run.memory_report else None
    )
    return MemoryRunResponse(
        id=memory_run.id,
        status=memory_run.status,
        memory_report=memory_report,
        activities=activities,
    )


@router.get("/api/v1/memory-runs", response_model=MemoryRunHistoryResponse)
def list_memory_runs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MemoryRunHistoryResponse:
    rows = (
        db.query(MemoryRun)
        .filter(MemoryRun.user_id == current_user.id)
        .order_by(MemoryRun.created_at.desc())
        .limit(100)
        .all()
    )
    return MemoryRunHistoryResponse(
        memory_runs=[
            MemoryRunHistoryItem(
                memory_run_id=row.id,
                status=row.status,
                created_at=row.created_at,
                last_updated=row.updated_at,
            )
            for row in rows
        ]
    )


@router.get("/api/v1/memory-run-events/stream")
def memory_run_stream() -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        while True:
            yield ": keep-alive\n\n"
            await asyncio.sleep(15)

    return StreamingResponse(events(), media_type="text/event-stream")


@router.delete("/api/v1/memory-runs/{memory_run_id}", status_code=204)
def delete_memory_run(
    memory_run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
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
    db.delete(memory_run)
    db.commit()
    return Response(status_code=204)
