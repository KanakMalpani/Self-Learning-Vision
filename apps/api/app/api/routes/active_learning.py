"""HTTP routes for active learning."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.support import (
    _active_learning_question_item,
    _promote_unknown_cluster_from_question,
    _sync_person_entity_from_reference,
    get_active_learning_registry,
    get_face_reference_registry,
    get_learning_signal_registry,
    get_memory_entity_registry,
)
from app.core.db import get_db
from app.models import User
from app.schemas import (
    ActiveLearningQuestionListResponse,
    ActiveLearningQuestionResponse,
    ActiveLearningQuestionResponseRequest,
)

router = APIRouter(tags=["active_learning"])


@router.get("/api/v1/active-learning/questions", response_model=ActiveLearningQuestionListResponse)
def list_active_learning_questions(
    status: str | None = "pending",
    current_user: User = Depends(get_current_user),
) -> ActiveLearningQuestionListResponse:
    registry = get_active_learning_registry(str(current_user.id))
    questions = registry.list_questions(status)
    return ActiveLearningQuestionListResponse(
        questions=[_active_learning_question_item(question) for question in questions],
        pending_count=registry.pending_count(),
    )


@router.post(
    "/api/v1/active-learning/questions/{question_id}/response",
    response_model=ActiveLearningQuestionResponse,
)
def respond_to_active_learning_question(
    question_id: str,
    payload: ActiveLearningQuestionResponseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ActiveLearningQuestionResponse:
    user_id = str(current_user.id)
    registry = get_active_learning_registry(user_id)
    question = registry.find(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Active-learning question not found")
    if question.status != "pending":
        return ActiveLearningQuestionResponse(
            question=_active_learning_question_item(question),
            applied=False,
            result={"reason": "Question already answered"},
        )

    applied = False
    result: dict[str, object] = {}
    action = payload.action
    label = payload.label.strip() if payload.label else None

    if question.question_type == "confirm_match" and action == "confirm":
        candidate_label = question.candidate_label
        if not candidate_label:
            raise HTTPException(
                status_code=400, detail="Question has no candidate label to confirm"
            )
        reference = get_face_reference_registry(user_id).mark_seen(name_or_alias=candidate_label)
        if reference:
            _sync_person_entity_from_reference(
                user_id=user_id,
                reference=reference,
                confidence=1.0,
                source_upload_id=question.upload_id,
            )
            applied = True
            result = {
                "confirmed_label": candidate_label,
                "reference_id": reference.reference_id,
                "seen_count": reference.seen_count,
            }
    elif question.question_type == "label_unknown_cluster" and action in {"label", "confirm"}:
        if not label:
            raise HTTPException(
                status_code=400, detail="A label is required for this active-learning response"
            )
        result = _promote_unknown_cluster_from_question(
            user_id=user_id,
            question=question,
            label=label,
            notes=payload.notes,
            tags=payload.tags,
            db=db,
        )
        applied = True

    answered = registry.answer_question(
        question_id=question_id,
        action=action,
        label=label,
        notes=payload.notes,
        tags=payload.tags,
    )
    if not answered:
        raise HTTPException(status_code=404, detail="Active-learning question not found")
    signal_registry = get_learning_signal_registry(user_id)
    signal_registry.resolve_many(
        answered.source_signal_ids,
        resolution=f"Active-learning question answered with {action}",
    )
    linked_entity_id = (
        answered.context.get("entity_id") if isinstance(answered.context, dict) else None
    )
    if not linked_entity_id and answered.candidate_label:
        matched_entity = get_memory_entity_registry(user_id).find_by_label(
            domain_type=answered.domain_type,
            label=answered.candidate_label,
        )
        linked_entity_id = matched_entity.entity_id if matched_entity else None
    if action == "reject" and answered.candidate_label and linked_entity_id:
        get_memory_entity_registry(user_id).record_contradiction(
            entity_id=str(linked_entity_id),
            rejected_label=answered.candidate_label,
            amount=0.1,
            reason="Active-learning response rejected this match",
        )
    signal_registry.upsert_signal(
        signal_type=(
            "active_learning_confirmation"
            if action in {"confirm", "label"}
            else "active_learning_response"
        ),
        source="active_learning",
        source_id=answered.question_id,
        question_id=answered.question_id,
        entity_id=str(linked_entity_id) if linked_entity_id else None,
        domain_type=answered.domain_type,
        summary=f"Active-learning response recorded: {action}",
        dedupe_key=f"active_learning_response:{answered.question_id}",
        confidence=answered.confidence,
        learning_value=0.85 if action in {"confirm", "label", "reject"} else 0.35,
        risk_level="high" if action == "reject" else "low",
        evidence=[answered.question_type, action],
        metadata={
            "candidate_label": answered.candidate_label,
            "unknown_cluster_id": answered.unknown_cluster_id,
        },
    )
    return ActiveLearningQuestionResponse(
        question=_active_learning_question_item(answered),
        applied=applied,
        result=result,
    )
