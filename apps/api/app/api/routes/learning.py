"""HTTP routes for learning."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import get_current_user
from app.api.support import (
    _active_learning_question_item,
    _learning_policy_item,
    _learning_signal_item,
    _memory_entity_item,
    _record_correction,
    _replay_suggestion_item,
    _sync_face_references_to_memory_entities,
    get_active_learning_registry,
    get_correction_log_registry,
    get_learning_policy_registry,
    get_learning_signal_registry,
    get_memory_entity_registry,
)
from app.models import User
from app.schemas import (
    LearningPolicyItem,
    LearningPolicySimulationResponse,
    LearningPolicyUpdateRequest,
    LearningReplayResponse,
    LearningReviewInboxResponse,
    LearningReviewMemoryItem,
    LearningSignalDismissRequest,
    LearningSignalItem,
    LearningSignalListResponse,
)
from app.services.learning_policy_simulator import simulate_learning_policy
from app.services.learning_replay import apply_learning_replay
from app.services.review_inbox import build_learning_review_inbox

router = APIRouter(tags=["learning"])


@router.get("/api/v1/learning/signals", response_model=LearningSignalListResponse)
def list_learning_signals(
    status: str | None = "pending",
    entity_id: str | None = None,
    signal_type: str | None = None,
    current_user: User = Depends(get_current_user),
) -> LearningSignalListResponse:
    registry = get_learning_signal_registry(str(current_user.id))
    records = registry.list_signals(status=status, entity_id=entity_id, signal_type=signal_type)
    return LearningSignalListResponse(
        signals=[_learning_signal_item(record) for record in records],
        signal_count=len(records),
        pending_count=registry.pending_count(),
    )


@router.get("/api/v1/learning/policy", response_model=LearningPolicyItem)
def get_learning_policy(current_user: User = Depends(get_current_user)) -> LearningPolicyItem:
    return _learning_policy_item(get_learning_policy_registry(str(current_user.id)).get())


@router.put("/api/v1/learning/policy", response_model=LearningPolicyItem)
def update_learning_policy(
    payload: LearningPolicyUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> LearningPolicyItem:
    return _learning_policy_item(
        get_learning_policy_registry(str(current_user.id)).set_preset(payload.preset)
    )


@router.get("/api/v1/learning/policy/simulation", response_model=LearningPolicySimulationResponse)
def simulate_current_learning_policy(
    current_user: User = Depends(get_current_user),
) -> LearningPolicySimulationResponse:
    user_id = str(current_user.id)
    entity_registry = get_memory_entity_registry(user_id)
    return LearningPolicySimulationResponse(
        **simulate_learning_policy(
            policy=get_learning_policy_registry(user_id).get(),
            entities=entity_registry.list_entities(),
            learning_signals=get_learning_signal_registry(user_id).list_signals(status=None),
            corrections=get_correction_log_registry(user_id).list_records(),
            active_learning_questions=get_active_learning_registry(user_id).list_questions(
                status=None
            ),
        )
    )


@router.post("/api/v1/learning/signals/{signal_id}/dismiss", response_model=LearningSignalItem)
def dismiss_learning_signal(
    signal_id: str,
    payload: LearningSignalDismissRequest,
    current_user: User = Depends(get_current_user),
) -> LearningSignalItem:
    record = get_learning_signal_registry(str(current_user.id)).dismiss_signal(
        signal_id,
        resolution=payload.reason,
    )
    if not record:
        raise HTTPException(status_code=404, detail="Learning signal not found")
    return _learning_signal_item(record)


@router.get("/api/v1/learning/review-inbox", response_model=LearningReviewInboxResponse)
def get_learning_review_inbox(
    current_user: User = Depends(get_current_user),
) -> LearningReviewInboxResponse:
    user_id = str(current_user.id)
    _sync_face_references_to_memory_entities(user_id)
    entity_registry = get_memory_entity_registry(user_id)
    inbox = build_learning_review_inbox(
        questions=get_active_learning_registry(user_id).list_questions(status=None),
        entities=entity_registry.list_entities(),
        corrections=get_correction_log_registry(user_id).list_records(),
        signal_registry=get_learning_signal_registry(user_id),
    )
    return LearningReviewInboxResponse(
        questions=[_active_learning_question_item(question) for question in inbox["questions"]],
        contradictions=[_learning_signal_item(signal) for signal in inbox["contradictions"]],
        candidate_memories=[
            LearningReviewMemoryItem(
                entity=_memory_entity_item(row["entity"]), health=row["health"]
            )
            for row in inbox["candidate_memories"]
        ],
        low_health_memories=[
            LearningReviewMemoryItem(
                entity=_memory_entity_item(row["entity"]), health=row["health"]
            )
            for row in inbox["low_health_memories"]
        ],
        replay_suggestions=[_replay_suggestion_item(item) for item in inbox["replay_suggestions"]],
        signals=[_learning_signal_item(signal) for signal in inbox["signals"]],
        summary=inbox["summary"],
    )


@router.post(
    "/api/v1/memory-entities/{entity_id}/learning/replay", response_model=LearningReplayResponse
)
def replay_memory_learning(
    entity_id: str,
    current_user: User = Depends(get_current_user),
) -> LearningReplayResponse:
    user_id = str(current_user.id)
    entity_registry = get_memory_entity_registry(user_id)
    before = entity_registry.snapshot()
    result = apply_learning_replay(
        entity_id=entity_id,
        entity_registry=entity_registry,
        active_learning_registry=get_active_learning_registry(user_id),
        signal_registry=get_learning_signal_registry(user_id),
        corrections=get_correction_log_registry(user_id).list_records(),
        active_learning_questions=get_active_learning_registry(user_id).list_questions(status=None),
    )
    if result.entity is None:
        raise HTTPException(status_code=404, detail="Memory entity not found")
    after = entity_registry.snapshot()
    if result.applied:
        _record_correction(
            user_id=user_id,
            operation_type="learning_replay",
            target_entity_id=entity_id,
            summary=f"Applied learning replay for {result.entity.label}",
            before_entities=before,
            after_entities=after,
            metadata=result.summary,
        )
    return LearningReplayResponse(
        applied=result.applied,
        entity=_memory_entity_item(result.entity),
        affected_signal_ids=result.affected_signal_ids,
        queued_question_ids=result.queued_question_ids,
        suggestions=[_replay_suggestion_item(item) for item in result.suggestions],
        summary=result.summary,
    )
