"""HTTP routes for lifecycle."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import get_current_user
from app.api.support import (
    _memory_entity_item,
    get_learning_signal_registry,
    get_memory_entity_registry,
)
from app.models import User
from app.schemas import (
    MemoryLifecycleContradictionRequest,
    MemoryLifecycleDecayRequest,
    MemoryLifecycleOperationResponse,
    MemoryLifecycleReinforceRequest,
    MemoryLifecycleSummaryResponse,
)

router = APIRouter(tags=["lifecycle"])


@router.get("/api/v1/memory-lifecycle/summary", response_model=MemoryLifecycleSummaryResponse)
def memory_lifecycle_summary(
    current_user: User = Depends(get_current_user),
) -> MemoryLifecycleSummaryResponse:
    summary = get_memory_entity_registry(str(current_user.id)).lifecycle_summary()
    return MemoryLifecycleSummaryResponse(**summary)


@router.post(
    "/api/v1/memory-lifecycle/decay-stale", response_model=MemoryLifecycleOperationResponse
)
def decay_stale_memory_entities(
    payload: MemoryLifecycleDecayRequest,
    current_user: User = Depends(get_current_user),
) -> MemoryLifecycleOperationResponse:
    registry = get_memory_entity_registry(str(current_user.id))
    affected = registry.decay_stale_entities(
        stale_after_days=payload.stale_after_days,
        amount=payload.amount,
    )
    return MemoryLifecycleOperationResponse(
        affected_entities=[_memory_entity_item(item) for item in affected],
        summary={
            "affected_count": len(affected),
            "stale_after_days": payload.stale_after_days,
            "amount": payload.amount,
        },
    )


@router.post(
    "/api/v1/memory-entities/{entity_id}/lifecycle/reinforce",
    response_model=MemoryLifecycleOperationResponse,
)
def reinforce_memory_entity(
    entity_id: str,
    payload: MemoryLifecycleReinforceRequest,
    current_user: User = Depends(get_current_user),
) -> MemoryLifecycleOperationResponse:
    record = get_memory_entity_registry(str(current_user.id)).reinforce_entity(
        entity_id=entity_id,
        amount=payload.amount,
        reason=payload.reason,
    )
    if not record:
        raise HTTPException(status_code=404, detail="Memory entity not found")
    get_learning_signal_registry(str(current_user.id)).upsert_signal(
        signal_type="contradiction",
        source="memory_lifecycle",
        source_id=record.entity_id,
        entity_id=record.entity_id,
        domain_type=record.domain_type,
        summary=payload.reason or "Memory received contradictory feedback",
        dedupe_key=f"lifecycle_contradiction:{record.entity_id}:{record.updated_at}",
        confidence=record.confidence,
        learning_value=0.9,
        risk_level="high",
        evidence=["lifecycle_contradiction"],
        metadata={"rejected_label": payload.rejected_label},
    )
    return MemoryLifecycleOperationResponse(
        entity=_memory_entity_item(record),
        summary={"event_type": "reinforced", "amount": payload.amount},
    )


@router.post(
    "/api/v1/memory-entities/{entity_id}/lifecycle/contradiction",
    response_model=MemoryLifecycleOperationResponse,
)
def record_memory_contradiction(
    entity_id: str,
    payload: MemoryLifecycleContradictionRequest,
    current_user: User = Depends(get_current_user),
) -> MemoryLifecycleOperationResponse:
    record = get_memory_entity_registry(str(current_user.id)).record_contradiction(
        entity_id=entity_id,
        rejected_label=payload.rejected_label,
        amount=payload.amount,
        reason=payload.reason,
    )
    if not record:
        raise HTTPException(status_code=404, detail="Memory entity not found")
    get_learning_signal_registry(str(current_user.id)).upsert_signal(
        signal_type=(
            "active_learning_confirmation"
            if payload.reason and "confirm" in payload.reason.lower()
            else "positive_observation"
        ),
        source="memory_lifecycle",
        source_id=record.entity_id,
        entity_id=record.entity_id,
        domain_type=record.domain_type,
        summary=payload.reason or "Memory was reinforced",
        dedupe_key=f"lifecycle_reinforce:{record.entity_id}:{record.updated_at}",
        confidence=record.confidence,
        learning_value=0.65,
        risk_level="low",
        evidence=["lifecycle_reinforcement"],
        metadata={"amount": payload.amount},
    )
    return MemoryLifecycleOperationResponse(
        entity=_memory_entity_item(record),
        summary={"event_type": "contradiction", "amount": payload.amount},
    )
