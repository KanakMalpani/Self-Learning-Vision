"""HTTP routes for memory."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import get_current_user
from app.api.support import (
    _active_learning_question_item,
    _correction_log_item,
    _domain_template_item,
    _memory_entity_item,
    _record_correction,
    _replay_suggestion_item,
    _sync_face_references_to_memory_entities,
    active_learning_priority_scorer,
    domain_active_learning_planner,
    domain_template_catalog,
    get_active_learning_registry,
    get_correction_log_registry,
    get_learning_signal_registry,
    get_memory_entity_registry,
)
from app.models import User
from app.schemas import (
    ActiveLearningQuestionListResponse,
    ConfidenceLedgerResponse,
    CorrectionResponse,
    MemoryDomainItem,
    MemoryDomainListResponse,
    MemoryDomainTemplateItem,
    MemoryDomainTemplateListResponse,
    MemoryEntityCreateFromTemplateRequest,
    MemoryEntityCreateRequest,
    MemoryEntityCreateResponse,
    MemoryEntityDetailResponse,
    MemoryEntityItem,
    MemoryEntityListResponse,
    MemoryEntityUpdateRequest,
    MemorySearchResponse,
)
from app.services.confidence_ledger import build_confidence_ledger
from app.services.memory_detail import build_memory_entity_detail
from app.services.memory_entity_registry import (
    RESERVED_DOMAIN_TYPES,
    MemoryObservation,
)
from app.services.memory_search import search_memory_entities

router = APIRouter(tags=["memory"])


@router.get("/api/v1/memory-domains", response_model=MemoryDomainListResponse)
def list_memory_domains(current_user: User = Depends(get_current_user)) -> MemoryDomainListResponse:
    _sync_face_references_to_memory_entities(str(current_user.id))
    registry = get_memory_entity_registry(str(current_user.id))
    domains = [
        MemoryDomainItem(
            domain_type=domain_type,
            entity_count=registry.entity_count(domain_type),
            built_in=domain_type in RESERVED_DOMAIN_TYPES,
        )
        for domain_type in registry.list_domain_types()
    ]
    return MemoryDomainListResponse(domains=domains)


@router.get("/api/v1/memory-domain-templates", response_model=MemoryDomainTemplateListResponse)
def list_memory_domain_templates() -> MemoryDomainTemplateListResponse:
    return MemoryDomainTemplateListResponse(
        templates=[
            _domain_template_item(template) for template in domain_template_catalog.list_templates()
        ]
    )


@router.get(
    "/api/v1/memory-domain-templates/{template_id}", response_model=MemoryDomainTemplateItem
)
def get_memory_domain_template(template_id: str) -> MemoryDomainTemplateItem:
    template = domain_template_catalog.find(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Memory domain template not found")
    return _domain_template_item(template)


@router.post(
    "/api/v1/memory-domain-templates/{template_id}/entities",
    response_model=MemoryEntityCreateResponse,
    status_code=201,
)
def create_memory_entity_from_template(
    template_id: str,
    payload: MemoryEntityCreateFromTemplateRequest,
    current_user: User = Depends(get_current_user),
) -> MemoryEntityCreateResponse:
    try:
        entity_payload = domain_template_catalog.build_entity_payload(
            template_id=template_id,
            label=payload.label,
            attributes=payload.attributes,
            aliases=payload.aliases,
            tags=payload.tags,
            notes=payload.notes,
            confidence=payload.confidence,
            lifecycle_state=payload.lifecycle_state,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    registry = get_memory_entity_registry(str(current_user.id))
    confidence = float(entity_payload["confidence"])
    record = registry.upsert_entity(
        domain_type=str(entity_payload["domain_type"]),
        label=str(entity_payload["label"]),
        attributes=entity_payload["attributes"],
        user_schema=entity_payload["user_schema"],
        aliases=entity_payload["aliases"],
        tags=entity_payload["tags"],
        notes=payload.notes,
        confidence=confidence,
        lifecycle_state=str(entity_payload["lifecycle_state"]),
        observation=MemoryObservation(
            observation_id=f"template-{template_id}-{datetime.now(UTC).timestamp()}",
            source="template",
            modality=str(entity_payload["observation_modality"]),
            confidence=confidence,
            notes=payload.notes,
            observed_at=datetime.now(UTC).isoformat(),
        ),
    )
    return MemoryEntityCreateResponse(
        entity=_memory_entity_item(record),
        total_entities=registry.entity_count(),
    )


@router.get("/api/v1/memory-entities", response_model=MemoryEntityListResponse)
def list_memory_entities(
    domain_type: str | None = None,
    current_user: User = Depends(get_current_user),
) -> MemoryEntityListResponse:
    _sync_face_references_to_memory_entities(str(current_user.id))
    registry = get_memory_entity_registry(str(current_user.id))
    return MemoryEntityListResponse(
        entities=[_memory_entity_item(record) for record in registry.list_entities(domain_type)]
    )


@router.get("/api/v1/memory-entities/search", response_model=MemorySearchResponse)
def search_memory_entities_endpoint(
    q: str = "",
    domain_type: str | None = None,
    lifecycle_state: str | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
) -> MemorySearchResponse:
    user_id = str(current_user.id)
    _sync_face_references_to_memory_entities(user_id)
    registry = get_memory_entity_registry(user_id)
    return MemorySearchResponse(
        **search_memory_entities(
            entities=registry.list_entities(),
            query=q,
            domain_type=domain_type,
            lifecycle_state=lifecycle_state,
            limit=limit,
        )
    )


@router.post("/api/v1/memory-entities", response_model=MemoryEntityCreateResponse, status_code=201)
def create_memory_entity(
    payload: MemoryEntityCreateRequest,
    current_user: User = Depends(get_current_user),
) -> MemoryEntityCreateResponse:
    registry = get_memory_entity_registry(str(current_user.id))
    try:
        record = registry.upsert_entity(
            domain_type=payload.domain_type,
            label=payload.label,
            attributes=payload.attributes,
            user_schema=payload.user_schema,
            aliases=payload.aliases,
            tags=payload.tags,
            notes=payload.notes,
            confidence=payload.confidence,
            lifecycle_state=payload.lifecycle_state,
            observation=MemoryObservation(
                observation_id=f"manual-{datetime.now(UTC).timestamp()}",
                source="manual",
                modality="vision",
                confidence=payload.confidence,
                notes=payload.notes,
                observed_at=datetime.now(UTC).isoformat(),
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return MemoryEntityCreateResponse(
        entity=_memory_entity_item(record),
        total_entities=registry.entity_count(),
    )


@router.get("/api/v1/memory-entities/{entity_id}", response_model=MemoryEntityItem)
def get_memory_entity(
    entity_id: str,
    current_user: User = Depends(get_current_user),
) -> MemoryEntityItem:
    _sync_face_references_to_memory_entities(str(current_user.id))
    record = get_memory_entity_registry(str(current_user.id)).find(entity_id)
    if not record:
        raise HTTPException(status_code=404, detail="Memory entity not found")
    return _memory_entity_item(record)


@router.patch("/api/v1/memory-entities/{entity_id}", response_model=CorrectionResponse)
def update_memory_entity(
    entity_id: str,
    payload: MemoryEntityUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> CorrectionResponse:
    user_id = str(current_user.id)
    registry = get_memory_entity_registry(user_id)
    before = registry.snapshot()
    record = registry.update_entity(
        entity_id=entity_id,
        attributes=payload.attributes,
        user_schema=payload.user_schema,
        aliases=payload.aliases,
        tags=payload.tags,
        notes=payload.notes,
        confidence=payload.confidence,
        lifecycle_state=payload.lifecycle_state,
    )
    if not record:
        raise HTTPException(status_code=404, detail="Memory entity not found")
    after = registry.snapshot()
    correction = _record_correction(
        user_id=user_id,
        operation_type="edit",
        target_entity_id=entity_id,
        summary=f"Edited memory entity {record.label}",
        before_entities=before,
        after_entities=after,
        metadata={
            "updated_fields": [
                key
                for key, value in payload.model_dump(exclude_unset=True).items()
                if value is not None
            ],
        },
    )
    return CorrectionResponse(
        correction=_correction_log_item(correction), entity=_memory_entity_item(record)
    )


@router.get("/api/v1/memory-entities/{entity_id}/detail", response_model=MemoryEntityDetailResponse)
def get_memory_entity_detail(
    entity_id: str,
    current_user: User = Depends(get_current_user),
) -> MemoryEntityDetailResponse:
    user_id = str(current_user.id)
    _sync_face_references_to_memory_entities(user_id)
    entity_registry = get_memory_entity_registry(user_id)
    record = entity_registry.find(entity_id)
    if not record:
        raise HTTPException(status_code=404, detail="Memory entity not found")
    questions = get_active_learning_registry(user_id).list_questions(status=None)
    corrections = get_correction_log_registry(user_id).list_records()
    learning_signals = get_learning_signal_registry(user_id).list_signals()
    detail = build_memory_entity_detail(
        entity=record,
        corrections=corrections,
        active_learning_questions=questions,
        learning_signals=learning_signals,
        all_entities=entity_registry.list_entities(),
    )
    return MemoryEntityDetailResponse(
        entity=_memory_entity_item(record),
        confidence_ledger=ConfidenceLedgerResponse(**detail["confidence_ledger"]),
        active_learning_questions=[
            _active_learning_question_item(question)
            for question in questions
            if question.context.get("entity_id") == entity_id
        ],
        corrections=[
            _correction_log_item(correction)
            for correction in corrections
            if correction.target_entity_id == entity_id
        ],
        evidence_bundles=detail["evidence_bundles"],
        health=detail["health"],
        related_conflicts=detail["related_conflicts"],
        replay_suggestions=[_replay_suggestion_item(item) for item in detail["replay_suggestions"]],
        learning_timeline=detail["learning_timeline"],
        summary=detail["summary"],
    )


@router.get(
    "/api/v1/memory-entities/{entity_id}/confidence-ledger", response_model=ConfidenceLedgerResponse
)
def get_memory_entity_confidence_ledger(
    entity_id: str,
    current_user: User = Depends(get_current_user),
) -> ConfidenceLedgerResponse:
    user_id = str(current_user.id)
    _sync_face_references_to_memory_entities(user_id)
    record = get_memory_entity_registry(user_id).find(entity_id)
    if not record:
        raise HTTPException(status_code=404, detail="Memory entity not found")
    return ConfidenceLedgerResponse(
        **build_confidence_ledger(
            entity=record,
            corrections=get_correction_log_registry(user_id).list_records(),
        )
    )


@router.post(
    "/api/v1/memory-entities/{entity_id}/active-learning/domain-review",
    response_model=ActiveLearningQuestionListResponse,
)
def queue_memory_entity_domain_review_questions(
    entity_id: str,
    current_user: User = Depends(get_current_user),
) -> ActiveLearningQuestionListResponse:
    user_id = str(current_user.id)
    registry = get_memory_entity_registry(user_id)
    record = registry.find(entity_id)
    if not record:
        raise HTTPException(status_code=404, detail="Memory entity not found")
    active_learning = get_active_learning_registry(user_id)
    signal_registry = get_learning_signal_registry(user_id)
    questions = []
    for draft in domain_active_learning_planner.draft_questions(record):
        signal = signal_registry.upsert_signal(
            signal_type=(
                "candidate_review" if record.lifecycle_state == "candidate" else "domain_review"
            ),
            source="domain_active_learning",
            source_id=record.entity_id,
            entity_id=record.entity_id,
            domain_type=record.domain_type,
            summary=draft.prompt,
            dedupe_key=f"domain_review_signal:{draft.dedupe_key}",
            confidence=draft.confidence,
            learning_value=0.7 if record.lifecycle_state in {"candidate", "uncertain"} else 0.5,
            risk_level="high" if record.lifecycle_state == "uncertain" else "medium",
            evidence=[draft.suggested_action],
            metadata={"suggested_action": draft.suggested_action},
        )
        score = active_learning_priority_scorer.score(
            question_type=draft.question_type,
            confidence=draft.confidence,
            domain_type=draft.domain_type,
            suggested_action=draft.suggested_action,
            context=draft.context,
            signals=signal_registry.list_signals(),
        )
        questions.append(
            active_learning.upsert_question(
                question_type=draft.question_type,
                prompt=draft.prompt,
                dedupe_key=draft.dedupe_key,
                domain_type=draft.domain_type,
                priority=score.priority,
                priority_reason=score.priority_reason,
                confidence=draft.confidence,
                source_signal_ids=[signal.signal_id, *score.source_signal_ids],
                learning_value=score.learning_value,
                risk_level=score.risk_level,
                cooldown_until=score.cooldown_until,
                suggested_action=draft.suggested_action,
                context=draft.context,
            )
        )
    return ActiveLearningQuestionListResponse(
        questions=[_active_learning_question_item(question) for question in questions],
        pending_count=active_learning.pending_count(),
    )
