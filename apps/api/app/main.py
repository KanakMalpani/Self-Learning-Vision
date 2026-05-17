from __future__ import annotations

import asyncio
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, List
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.auth import get_current_user, router as auth_router
from app.core.config import settings
from app.core.db import get_db, init_db
from app.middleware import RequestIDMiddleware
from app.models import Activity, MemoryRun, MemoryRunStatus, Upload, User
from app.schemas import (
    ActiveLearningQuestionItem,
    ActiveLearningQuestionListResponse,
    ActiveLearningQuestionResponse,
    ActiveLearningQuestionResponseRequest,
    ActiveLearningResponseItem,
    ActivityEntry,
    BenchmarkPackResponse,
    BenchmarkRunCreateRequest,
    BenchmarkRunItem,
    BenchmarkRunListResponse,
    ConfidenceLedgerResponse,
    CorrectionListResponse,
    CorrectionLogItem,
    CorrectionResponse,
    EvaluationDatasetResponse,
    EvaluationMetricsResponse,
    FaceReferenceEnrollRequest,
    FaceReferenceEnrollResponse,
    FaceReferenceItem,
    HealthResponse,
    LearningReplayResponse,
    LearningReplaySuggestionItem,
    LearningPolicyItem,
    LearningPolicySimulationResponse,
    LearningPolicyUpdateRequest,
    LearningReviewInboxResponse,
    LearningReviewMemoryItem,
    LearningSignalDismissRequest,
    LearningSignalItem,
    LearningSignalListResponse,
    MemoryDomainItem,
    MemoryDomainListResponse,
    MemoryDomainTemplateItem,
    MemoryDomainTemplateListResponse,
    MemoryEntityCreateRequest,
    MemoryEntityCreateFromTemplateRequest,
    MemoryEntityCreateResponse,
    MemoryEntityDetailResponse,
    MemoryEntityForgetRequest,
    MemoryEntityItem,
    MemoryEntityListResponse,
    MemoryEntityMergeRequest,
    MemoryEntityNotThisRequest,
    MemoryEntityRenameRequest,
    MemoryEntitySplitRequest,
    MemoryEntityUpdateRequest,
    MemoryLifecycleContradictionRequest,
    MemoryLifecycleDecayRequest,
    MemoryLifecycleEventItem,
    MemoryLifecycleOperationResponse,
    MemoryLifecycleReinforceRequest,
    MemoryLifecycleSummaryResponse,
    MemoryObservationItem,
    MemorySearchResponse,
    MemoryRunCreateResponse,
    MemoryRunHistoryItem,
    MemoryRunHistoryResponse,
    MemoryRunRequest,
    MemoryRunResponse,
    PrivacySettingsItem,
    PrivacySettingsUpdateRequest,
    ProviderCardItem,
    ProviderConformanceListResponse,
    ProviderHealthItem,
    ProviderHealthResponse,
    ProviderMarketplaceResponse,
    ProviderPluginListResponse,
    ProviderScorecardResponse,
    ProviderSelectionRequest,
    ProviderSelectionResponse,
    ReadinessResponse,
    UploadRecognitionResult,
    UploadResponse,
    VaultExportRequest,
    VaultImportRequest,
    VaultImportResponse,
)
from app.schemas.memory_report import MemoryReport, MemoryReportConfidence, Fact, Subject
from app.services.benchmark_pack import build_benchmark_pack
from app.services.benchmark_run_registry import BenchmarkRunRecord, BenchmarkRunRegistry
from app.services.confidence_ledger import build_confidence_ledger
from app.services.active_learning_priority import ActiveLearningPriorityScorer
from app.services.core_engine import RecognitionCoreService
from app.services.active_learning_registry import (
    ActiveLearningQuestion,
    ActiveLearningRegistry,
    ActiveLearningResponse,
)
from app.services.correction_log_registry import CorrectionLogRecord, CorrectionLogRegistry
from app.services.domain_templates import DomainTemplateCatalog, MemoryDomainTemplate
from app.services.domain_active_learning import DomainActiveLearningPlanner
from app.services.evaluation import (
    build_evaluation_dataset,
    build_evaluation_metrics,
    build_provider_scorecard,
)
from app.services.face_detection import FaceDetectionService
from app.services.face_reference_registry import FaceReferenceRegistry
from app.services.learning_replay import apply_learning_replay
from app.services.learning_policy_registry import LearningPolicyRecord, LearningPolicyRegistry
from app.services.learning_policy_simulator import simulate_learning_policy
from app.services.learning_signal_registry import LearningSignalRecord, LearningSignalRegistry
from app.services.memory_health import build_memory_health_distribution
from app.services.memory_lifecycle_policy import MemoryLifecyclePolicy
from app.services.memory_entity_registry import (
    RESERVED_DOMAIN_TYPES,
    MemoryEntityRecord,
    MemoryEntityRegistry,
    MemoryLifecycleEvent,
    MemoryObservation,
)
from app.services.memory_detail import build_memory_entity_detail
from app.services.memory_search import search_memory_entities
from app.services.privacy_settings_registry import PrivacySettingsRecord, PrivacySettingsRegistry
from app.services.privacy_vault import PrivacyVaultService, VaultEncryptionUnavailable
from app.services.provider_conformance import evaluate_provider_catalog
from app.services.model_assets import provider_health
from app.services.provider_marketplace import (
    PROVIDER_CAPABILITIES,
    ProviderCard,
    ProviderMarketplace,
    ProviderSelectionRecord,
    ProviderSelectionRegistry,
)
from app.services.review_inbox import build_learning_review_inbox
from app.services.recognition import select_embedding_provider
from app.services.storage import StorageService
from app.services.unknown_face_registry import UnknownFaceRegistry
from app.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(title=settings.app_name)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)

storage_service = StorageService(settings.storage_dir)
face_service = FaceDetectionService()
privacy_vault_service = PrivacyVaultService()
provider_marketplace = ProviderMarketplace()
domain_template_catalog = DomainTemplateCatalog()
domain_active_learning_planner = DomainActiveLearningPlanner(domain_template_catalog)
active_learning_priority_scorer = ActiveLearningPriorityScorer()
memory_lifecycle_policy = MemoryLifecyclePolicy()


def get_face_reference_registry(user_id: str) -> FaceReferenceRegistry:
    user_storage = Path(settings.storage_dir) / "face-references" / str(user_id)
    user_storage.mkdir(parents=True, exist_ok=True)
    return FaceReferenceRegistry(user_storage / "registry.json")


def get_unknown_face_registry(user_id: str) -> UnknownFaceRegistry:
    user_storage = Path(settings.storage_dir) / "unknown-faces" / str(user_id)
    user_storage.mkdir(parents=True, exist_ok=True)
    return UnknownFaceRegistry(
        user_storage / "samples.json",
        cluster_similarity_threshold=settings.unknown_cluster_similarity_threshold,
        familiarity_min_samples=settings.unknown_cluster_familiarity_min_samples,
    )


def get_memory_entity_registry(user_id: str) -> MemoryEntityRegistry:
    user_storage = Path(settings.storage_dir) / "memory-entities" / str(user_id)
    user_storage.mkdir(parents=True, exist_ok=True)
    return MemoryEntityRegistry(user_storage / "entities.json")


def get_active_learning_registry(user_id: str) -> ActiveLearningRegistry:
    user_storage = Path(settings.storage_dir) / "active-learning" / str(user_id)
    user_storage.mkdir(parents=True, exist_ok=True)
    return ActiveLearningRegistry(user_storage / "questions.json")


def get_learning_signal_registry(user_id: str) -> LearningSignalRegistry:
    user_storage = Path(settings.storage_dir) / "learning-signals" / str(user_id)
    user_storage.mkdir(parents=True, exist_ok=True)
    return LearningSignalRegistry(user_storage / "signals.json")


def get_learning_policy_registry(user_id: str) -> LearningPolicyRegistry:
    user_storage = Path(settings.storage_dir) / "learning-policy" / str(user_id)
    user_storage.mkdir(parents=True, exist_ok=True)
    return LearningPolicyRegistry(user_storage / "policy.json")


def get_correction_log_registry(user_id: str) -> CorrectionLogRegistry:
    user_storage = Path(settings.storage_dir) / "corrections" / str(user_id)
    user_storage.mkdir(parents=True, exist_ok=True)
    return CorrectionLogRegistry(user_storage / "corrections.json")


def get_privacy_settings_registry(user_id: str) -> PrivacySettingsRegistry:
    user_storage = Path(settings.storage_dir) / "privacy-settings" / str(user_id)
    user_storage.mkdir(parents=True, exist_ok=True)
    return PrivacySettingsRegistry(user_storage / "settings.json")


def get_provider_selection_registry(user_id: str) -> ProviderSelectionRegistry:
    user_storage = Path(settings.storage_dir) / "provider-selections" / str(user_id)
    user_storage.mkdir(parents=True, exist_ok=True)
    return ProviderSelectionRegistry(user_storage / "providers.json")


def get_benchmark_run_registry(user_id: str) -> BenchmarkRunRegistry:
    user_storage = Path(settings.storage_dir) / "benchmark-runs" / str(user_id)
    user_storage.mkdir(parents=True, exist_ok=True)
    return BenchmarkRunRegistry(user_storage / "runs.json")


def _build_embedding_provider(registry: FaceReferenceRegistry | None = None, user_id: str | None = None):
    _ = registry
    if not settings.enable_face_matching:
        return None
    requested_provider = settings.embedding_provider
    if user_id:
        selected = get_provider_selection_registry(user_id).selected_provider_for("face_embedding")
        if selected:
            requested_provider = selected
    hosted_requested = settings.embedding_provider == "paid" or settings.paid_provider_enabled
    if requested_provider in {"template-paid-provider", "custom-http-provider"}:
        hosted_requested = True
    if user_id:
        local_only, allow_hosted = _provider_privacy_flags(user_id)
        selected_card = provider_marketplace.find_card(
            requested_provider,
            privacy_local_only=local_only,
            allow_hosted=allow_hosted,
        )
        if selected_card is not None:
            hosted_requested = hosted_requested or selected_card.images_leave_device or selected_card.mode in {
                "hosted_paid",
                "hosted_or_internal",
            }
            if selected_card.status == "blocked_by_privacy_policy":
                logger.warning("Selected embedding provider blocked by privacy settings")
                return None
    if hosted_requested and (settings.privacy_local_only_mode or not settings.privacy_allow_hosted_providers):
        logger.warning("Hosted embedding provider blocked by privacy settings")
        return None
    plugin_provider = provider_marketplace.build_face_embedding_provider(requested_provider)
    if plugin_provider is not None:
        return plugin_provider
    provider_aliases = {
        "local-face-embedding": "local",
        "template-paid-provider": "paid",
        "custom-http-provider": "paid",
    }
    return select_embedding_provider(
        provider_aliases.get(requested_provider, requested_provider),
        paid_provider_enabled=settings.paid_provider_enabled,
    )


def get_core_recognition_service(user_id: str) -> RecognitionCoreService:
    registry = get_face_reference_registry(user_id)
    return RecognitionCoreService(
        detection_service=face_service,
        reference_registry=registry,
        reference_registry_factory=lambda: registry,
        embedding_provider_factory=lambda: _build_embedding_provider(registry, user_id=user_id),
    )


def _reference_item(record) -> FaceReferenceItem:
    return FaceReferenceItem(
        reference_id=record.reference_id,
        name_or_alias=record.name_or_alias,
        provider=record.provider,
        source_image_path=record.source_image_path,
        face_index=record.face_index,
        notes=record.notes,
        tags=record.tags or [],
        seen_count=record.seen_count,
        last_seen_at=datetime.fromisoformat(record.last_seen_at) if record.last_seen_at else None,
        created_at=datetime.fromisoformat(record.created_at),
    )


def _memory_observation_item(observation: MemoryObservation) -> MemoryObservationItem:
    return MemoryObservationItem(
        observation_id=observation.observation_id,
        source=observation.source,
        source_id=observation.source_id,
        modality=observation.modality,
        confidence=observation.confidence,
        notes=observation.notes,
        observed_at=datetime.fromisoformat(observation.observed_at),
    )


def _memory_lifecycle_event_item(event: MemoryLifecycleEvent) -> MemoryLifecycleEventItem:
    return MemoryLifecycleEventItem(
        event_id=event.event_id,
        event_type=event.event_type,
        from_state=event.from_state,
        to_state=event.to_state,
        confidence_before=event.confidence_before,
        confidence_after=event.confidence_after,
        reason=event.reason,
        created_at=datetime.fromisoformat(event.created_at),
    )


def _memory_entity_item(record: MemoryEntityRecord) -> MemoryEntityItem:
    return MemoryEntityItem(
        entity_id=record.entity_id,
        domain_type=record.domain_type,
        label=record.label,
        attributes=record.attributes,
        schema_version=record.schema_version,
        user_schema=record.user_schema,
        aliases=record.aliases,
        tags=record.tags,
        notes=record.notes,
        confidence=record.confidence,
        lifecycle_state=record.lifecycle_state,
        observations=[_memory_observation_item(item) for item in record.observations],
        lifecycle_events=[_memory_lifecycle_event_item(item) for item in record.lifecycle_events],
        source_reference_ids=record.source_reference_ids,
        created_at=datetime.fromisoformat(record.created_at),
        updated_at=datetime.fromisoformat(record.updated_at),
    )


def _active_learning_response_item(response: ActiveLearningResponse | None) -> ActiveLearningResponseItem | None:
    if response is None:
        return None
    return ActiveLearningResponseItem(
        action=response.action,
        label=response.label,
        notes=response.notes,
        tags=response.tags,
        answered_at=datetime.fromisoformat(response.answered_at),
    )


def _active_learning_question_item(question: ActiveLearningQuestion) -> ActiveLearningQuestionItem:
    return ActiveLearningQuestionItem(
        question_id=question.question_id,
        question_type=question.question_type,
        prompt=question.prompt,
        domain_type=question.domain_type,
        status=question.status,
        priority=question.priority,
        priority_reason=question.priority_reason,
        confidence=question.confidence,
        source_signal_ids=question.source_signal_ids,
        learning_value=question.learning_value,
        risk_level=question.risk_level,
        cooldown_until=question.cooldown_until,
        suggested_action=question.suggested_action,
        memory_run_id=question.memory_run_id,
        upload_id=question.upload_id,
        selected_face_index=question.selected_face_index,
        candidate_label=question.candidate_label,
        candidate_reference_id=question.candidate_reference_id,
        unknown_cluster_id=question.unknown_cluster_id,
        context=question.context,
        response=_active_learning_response_item(question.response),
        created_at=datetime.fromisoformat(question.created_at),
        updated_at=datetime.fromisoformat(question.updated_at),
    )


def _learning_signal_item(record: LearningSignalRecord) -> LearningSignalItem:
    return LearningSignalItem(
        signal_id=record.signal_id,
        signal_type=record.signal_type,
        source=record.source,
        summary=record.summary,
        domain_type=record.domain_type,
        entity_id=record.entity_id,
        question_id=record.question_id,
        source_id=record.source_id,
        status=record.status,
        confidence=record.confidence,
        learning_value=record.learning_value,
        risk_level=record.risk_level,
        evidence=record.evidence,
        metadata=record.metadata,
        resolution=record.resolution,
        created_at=datetime.fromisoformat(record.created_at),
        updated_at=datetime.fromisoformat(record.updated_at),
        resolved_at=datetime.fromisoformat(record.resolved_at) if record.resolved_at else None,
    )


def _memory_health_item(payload: dict[str, object]) -> dict[str, object]:
    return payload


def _replay_suggestion_item(payload: dict[str, object]) -> LearningReplaySuggestionItem:
    return LearningReplaySuggestionItem(**payload)


def _learning_policy_item(record: LearningPolicyRecord) -> LearningPolicyItem:
    return LearningPolicyItem(
        preset=record.preset,
        auto_reinforcement_enabled=record.auto_reinforcement_enabled,
        high_confidence_threshold=record.high_confidence_threshold,
        min_reinforcement_signals=record.min_reinforcement_signals,
        max_reinforcement_amount=record.max_reinforcement_amount,
        review_budget_per_session=record.review_budget_per_session,
        updated_at=datetime.fromisoformat(record.updated_at),
    )


def _memory_lifecycle_policy_for(user_id: str) -> MemoryLifecyclePolicy:
    policy = get_learning_policy_registry(user_id).get()
    if not policy.auto_reinforcement_enabled:
        return MemoryLifecyclePolicy(high_confidence_threshold=1.01, min_reinforcement_signals=999999)
    return MemoryLifecyclePolicy(
        high_confidence_threshold=policy.high_confidence_threshold,
        min_reinforcement_signals=policy.min_reinforcement_signals,
        max_reinforcement_amount=policy.max_reinforcement_amount,
    )


def _correction_log_item(record: CorrectionLogRecord) -> CorrectionLogItem:
    return CorrectionLogItem(
        correction_id=record.correction_id,
        operation_type=record.operation_type,
        target_entity_id=record.target_entity_id,
        summary=record.summary,
        metadata=record.metadata,
        undone=record.undone,
        undone_at=datetime.fromisoformat(record.undone_at) if record.undone_at else None,
        created_at=datetime.fromisoformat(record.created_at),
    )


def _privacy_settings_item(record: PrivacySettingsRecord) -> PrivacySettingsItem:
    return PrivacySettingsItem(
        local_only_mode=record.local_only_mode,
        allow_hosted_providers=record.allow_hosted_providers,
        export_include_biometric_embeddings=False,
        export_include_upload_paths=record.export_include_upload_paths,
        data_retention_days=record.data_retention_days,
        domain_visibility=record.domain_visibility,
        updated_at=datetime.fromisoformat(record.updated_at),
    )


def _provider_card_item(card: ProviderCard) -> ProviderCardItem:
    return ProviderCardItem(
        provider_id=card.provider_id,
        display_name=card.display_name,
        mode=card.mode,
        capabilities=card.capabilities,
        status=card.status,
        images_leave_device=card.images_leave_device,
        embeddings_stored_locally=card.embeddings_stored_locally,
        enabled_by_default=card.enabled_by_default,
        recommended_for=card.recommended_for,
        env_vars=card.env_vars,
        expected_dimensions=card.expected_dimensions,
        latency_profile=card.latency_profile,
        cost_model=card.cost_model,
        setup=card.setup,
        privacy_notes=card.privacy_notes,
        entrypoint=card.entrypoint,
        manifest_path=card.manifest_path,
        plugin_source=card.plugin_source,
    )


def _domain_template_item(template: MemoryDomainTemplate) -> MemoryDomainTemplateItem:
    return MemoryDomainTemplateItem(**template.to_schema())


def _benchmark_run_item(record: BenchmarkRunRecord) -> BenchmarkRunItem:
    return BenchmarkRunItem(
        run_id=record.run_id,
        label=record.label,
        notes=record.notes,
        benchmark_case_ids=record.benchmark_case_ids,
        provider_selections=record.provider_selections,
        metrics=record.metrics,
        created_at=datetime.fromisoformat(record.created_at),
    )


def _provider_privacy_flags(user_id: str) -> tuple[bool, bool]:
    privacy_settings = get_privacy_settings_registry(user_id).get()
    provider_selections = get_provider_selection_registry(user_id).get()
    local_only = privacy_settings.local_only_mode or settings.privacy_local_only_mode
    allow_hosted = privacy_settings.allow_hosted_providers and settings.privacy_allow_hosted_providers
    return local_only, allow_hosted


def _record_correction(
    *,
    user_id: str,
    operation_type: str,
    target_entity_id: str,
    summary: str,
    before_entities: list[dict[str, object]],
    after_entities: list[dict[str, object]],
    metadata: dict[str, object] | None = None,
) -> CorrectionLogRecord:
    record = get_correction_log_registry(user_id).add_record(
        operation_type=operation_type,
        target_entity_id=target_entity_id,
        summary=summary,
        before_entities=before_entities,
        after_entities=after_entities,
        metadata=metadata,
    )
    entity_payload = _find_entity_payload(target_entity_id, after_entities) or _find_entity_payload(
        target_entity_id,
        before_entities,
    )
    risk_level = "high" if operation_type in {"not_this", "split", "forget"} else "medium"
    signal_type = "contradiction" if operation_type in {"not_this", "split"} else "correction"
    get_learning_signal_registry(user_id).upsert_signal(
        signal_type=signal_type,
        source="correction_log",
        source_id=record.correction_id,
        entity_id=target_entity_id,
        domain_type=str(entity_payload.get("domain_type") or "custom") if entity_payload else "custom",
        summary=summary,
        dedupe_key=f"correction:{record.correction_id}",
        confidence=float(entity_payload.get("confidence") or 0.0) if entity_payload else 0.0,
        learning_value=0.9 if signal_type == "contradiction" else 0.55,
        risk_level=risk_level,
        evidence=[operation_type],
        metadata={"operation_type": operation_type, "label": entity_payload.get("label") if entity_payload else None},
    )
    return record


def _find_entity_payload(entity_id: str, entities: list[dict[str, object]]) -> dict[str, object] | None:
    for item in entities:
        if str(item.get("entity_id") or "") == entity_id:
            return item
    return None


def _sync_person_entity_from_reference(
    *,
    user_id: str,
    reference,
    confidence: float,
    source_upload_id: str | None = None,
) -> MemoryEntityRecord:
    observation = MemoryObservation(
        observation_id=f"face-reference-{reference.reference_id}",
        source="face_reference",
        source_id=source_upload_id,
        modality="face",
        confidence=max(0.0, min(1.0, float(confidence or 0.0))),
        notes=reference.notes,
        observed_at=datetime.now(timezone.utc).isoformat(),
    )
    registry = get_memory_entity_registry(user_id)
    record = registry.upsert_entity(
        domain_type="person",
        label=reference.name_or_alias,
        attributes={
            "default_recognition_domain": "face",
            "provider": reference.provider,
            "face_index": reference.face_index,
            "seen_count": reference.seen_count,
            "last_seen_at": reference.last_seen_at,
        },
        user_schema={
            "label": "Person",
            "fields": {
                "default_recognition_domain": "string",
                "provider": "string",
                "face_index": "integer",
                "seen_count": "integer",
                "last_seen_at": "datetime",
            },
        },
        tags=reference.tags,
        notes=reference.notes,
        confidence=confidence,
        lifecycle_state="confirmed",
        source_reference_id=reference.reference_id,
        observation=observation,
    )
    signal_registry = get_learning_signal_registry(user_id)
    signal_registry.upsert_signal(
        signal_type="positive_observation" if confidence >= 0.85 else "passive_observation",
        source="face_reference",
        source_id=source_upload_id or reference.reference_id,
        entity_id=record.entity_id,
        domain_type=record.domain_type,
        summary=f"Face reference evidence updated {record.label}",
        dedupe_key=f"face_reference:{reference.reference_id}:{source_upload_id or reference.seen_count}",
        confidence=confidence,
        learning_value=0.72 if confidence >= 0.85 else 0.45,
        risk_level="low" if confidence >= 0.85 else "medium",
        evidence=["face_reference", f"seen_count:{reference.seen_count}"],
        metadata={
            "provider": reference.provider,
            "seen_count": reference.seen_count,
            "face_index": reference.face_index,
        },
    )
    _memory_lifecycle_policy_for(user_id).apply_balanced_auto_reinforcement(
        entity=record,
        entity_registry=registry,
        signal_registry=signal_registry,
    )
    return registry.find(record.entity_id) or record


def _sync_face_references_to_memory_entities(user_id: str) -> None:
    for reference in get_face_reference_registry(user_id).list_records():
        _sync_person_entity_from_reference(
            user_id=user_id,
            reference=reference,
            confidence=1.0 if reference.seen_count > 0 else 0.8,
        )


def _upload_recognition_response(
    result,
    *,
    unknown_sample_id: str | None = None,
    unknown_cluster_id: str | None = None,
    unknown_cluster_sighting_count: int = 0,
    unknown_cluster_suggested_for_enrollment: bool = False,
) -> UploadRecognitionResult:
    return UploadRecognitionResult(
        selected_face_index=int(result.face_index or 0),
        status=result.status,
        confidence=round(float(result.confidence or 0.0), 6),
        reference_id=result.reference_id,
        top_candidate_name=result.top_candidate_name,
        top_candidate_provider=result.top_candidate_provider,
        memory_summary=result.memory_summary,
        notes=result.notes,
        tags=list(result.tags or []),
        seen_count=result.seen_count,
        last_seen_at=datetime.fromisoformat(result.last_seen_at) if result.last_seen_at else None,
        unknown_sample_id=unknown_sample_id,
        unknown_sample_stored=unknown_sample_id is not None,
        unknown_cluster_id=unknown_cluster_id,
        unknown_cluster_sighting_count=unknown_cluster_sighting_count,
        unknown_cluster_suggested_for_enrollment=unknown_cluster_suggested_for_enrollment,
        quality_score=result.quality_score,
        reason=result.reason,
        embedding_dimensions=result.embedding_dimensions,
        candidate_count=len(result.candidates or []),
    )


def _local_memory_report(result: UploadRecognitionResult, notes: str | None = None) -> MemoryReport:
    name = result.top_candidate_name or "Unknown"
    if result.status == "matched":
        executive_summary = result.memory_summary or f"Matched {name} from local memory."
    elif result.status == "tentative":
        executive_summary = f"Possible local match: {name}. Review before trusting this memory."
    else:
        executive_summary = "No trusted local identity matched this face."

    key_facts: list[Fact] = [
        Fact(title="Recognition status", detail=result.status, confidence=result.confidence),
        Fact(title="Recognition reason", detail=result.reason or "Local recognition completed"),
    ]
    if result.memory_summary:
        key_facts.append(Fact(title="Memory", detail=result.memory_summary, confidence=result.confidence))
    if result.seen_count is not None:
        key_facts.append(Fact(title="Seen count", detail=str(result.seen_count), confidence=result.confidence))
    if result.last_seen_at is not None:
        key_facts.append(Fact(title="Last seen", detail=result.last_seen_at.isoformat(), confidence=result.confidence))
    if notes:
        key_facts.append(Fact(title="User note", detail=notes, confidence=1.0))

    recognition_summary = {
        "recognition_decision": result.status,
        "final_verdict_decision": result.status,
        "final_verdict_name": name,
        "confidence": result.confidence,
        "memory_summary": result.memory_summary,
        "unknown_sample_stored": result.unknown_sample_stored,
        "unknown_cluster_id": result.unknown_cluster_id,
        "unknown_cluster_sighting_count": result.unknown_cluster_sighting_count,
        "unknown_cluster_suggested_for_enrollment": result.unknown_cluster_suggested_for_enrollment,
    }

    return MemoryReport(
        subject=Subject(name_or_alias=name),
        executive_summary=executive_summary,
        key_facts=key_facts,
        timeline=[],
        profile_links=[],
        confidence=MemoryReportConfidence(overall=max(0.0, min(1.0, result.confidence))),
        source_notes=["Local vision memory recognition only."],
        caveats=["Unknown and tentative results should be reviewed before relying on them."],
        recognition_summary=recognition_summary,
        decision_trace={"final_verdict_decision": result.status, "final_verdict_name": name},
        recognition_source="local_memory",
    )


def _store_unknown_sample_if_useful(*, user_id: str, upload_id: UUID, result) -> dict[str, object]:
    if result.status != "unknown" or not result.embedding or not result.embedding_provider:
        return {}
    if result.quality_score is None or result.quality_score < settings.face_quality_min_threshold:
        return {}

    registry = get_unknown_face_registry(user_id)
    sample = registry.add_sample(
        embedding=result.embedding,
        source_upload_id=str(upload_id),
        face_index=int(result.face_index or 0),
        quality_score=float(result.quality_score),
        provider=result.embedding_provider,
    )
    cluster = registry.find_cluster_for_sample(sample.unknown_sample_id)
    return {
        "unknown_sample_id": sample.unknown_sample_id,
        "unknown_cluster_id": cluster.unknown_cluster_id if cluster else None,
        "unknown_cluster_sighting_count": cluster.sighting_count if cluster else 0,
        "unknown_cluster_suggested_for_enrollment": bool(cluster.suggested_for_enrollment) if cluster else False,
    }


def _provider_privacy_status(privacy_settings: PrivacySettingsRecord) -> dict[str, object]:
    hosted_requested = settings.embedding_provider == "paid" or settings.paid_provider_enabled
    blocked_by_local_only = (privacy_settings.local_only_mode or settings.privacy_local_only_mode) and hosted_requested
    return {
        "local_only_mode": privacy_settings.local_only_mode,
        "allow_hosted_providers": privacy_settings.allow_hosted_providers and settings.privacy_allow_hosted_providers,
        "active_embedding_provider": settings.embedding_provider,
        "paid_provider_enabled": settings.paid_provider_enabled,
        "hosted_provider_requested": hosted_requested,
        "hosted_provider_blocked_by_policy": blocked_by_local_only
        or not privacy_settings.allow_hosted_providers
        or not settings.privacy_allow_hosted_providers,
    }


def _redacted_memory_entity_payload(entity: MemoryEntityRecord) -> dict[str, object]:
    payload = _memory_entity_item(entity).model_dump(mode="json")
    payload["source_reference_ids"] = list(entity.source_reference_ids)
    return payload


def _build_user_export_payload(*, db: Session, current_user: User) -> dict[str, object]:
    user_id = str(current_user.id)
    _sync_face_references_to_memory_entities(user_id)
    privacy_settings = get_privacy_settings_registry(user_id).get()
    references = get_face_reference_registry(user_id).list_records()
    unknown_registry = get_unknown_face_registry(user_id)
    entity_registry = get_memory_entity_registry(user_id)
    active_learning_registry = get_active_learning_registry(user_id)
    learning_signal_registry = get_learning_signal_registry(user_id)
    correction_registry = get_correction_log_registry(user_id)
    provider_selections = get_provider_selection_registry(user_id).get()
    hidden_domains = {
        domain
        for domain, visibility in privacy_settings.domain_visibility.items()
        if visibility == "hidden"
    }
    memory_runs = (
        db.query(MemoryRun)
        .filter(MemoryRun.user_id == current_user.id)
        .order_by(MemoryRun.created_at.desc())
        .all()
    )
    uploads = (
        db.query(Upload)
        .filter(Upload.user_id == current_user.id)
        .order_by(Upload.created_at.desc())
        .all()
    )
    upload_items: list[dict[str, object]] = []
    for item in uploads:
        upload_payload: dict[str, object] = {
            "upload_id": str(item.id),
            "original_filename": item.original_filename,
            "content_type": item.content_type,
            "face_count": len(item.face_boxes or []),
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        if privacy_settings.export_include_upload_paths:
            upload_payload["file_path"] = item.file_path
        upload_items.append(upload_payload)

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "privacy_settings": _privacy_settings_item(privacy_settings).model_dump(mode="json"),
        "provider_privacy": _provider_privacy_status(privacy_settings),
        "provider_selections": provider_selections.selections,
        "learning_policy": _learning_policy_item(get_learning_policy_registry(user_id).get()).model_dump(mode="json"),
        "redaction": {
            "biometric_embeddings_included": False,
            "unknown_cluster_centroids_included": False,
            "upload_paths_included": privacy_settings.export_include_upload_paths,
            "hidden_domains": sorted(hidden_domains),
        },
        "identity_references": [
            {
                "reference_id": item.reference_id,
                "name_or_alias": item.name_or_alias,
                "provider": item.provider,
                "face_index": item.face_index,
                "notes": item.notes,
                "tags": item.tags or [],
                "seen_count": item.seen_count,
                "last_seen_at": item.last_seen_at,
                "created_at": item.created_at,
            }
            for item in references
        ],
        "memory_entities": [
            _redacted_memory_entity_payload(entity)
            for entity in entity_registry.list_entities()
            if entity.domain_type not in hidden_domains
        ],
        "active_learning_questions": [
            _active_learning_question_item(question).model_dump(mode="json")
            for question in active_learning_registry.list_questions()
        ],
        "learning_signals": [
            _learning_signal_item(signal).model_dump(mode="json")
            for signal in learning_signal_registry.list_signals(status=None)
        ],
        "corrections": [
            _correction_log_item(correction).model_dump(mode="json")
            for correction in correction_registry.list_records()
        ],
        "unknown_clusters": [
            {
                "unknown_cluster_id": cluster.unknown_cluster_id,
                "sample_count": len(cluster.sample_ids),
                "sighting_count": cluster.sighting_count,
                "first_seen_at": cluster.first_seen_at,
                "last_seen_at": cluster.last_seen_at,
                "familiarity_state": cluster.familiarity_state,
                "suggested_for_enrollment": cluster.suggested_for_enrollment,
                "promoted": cluster.promoted,
            }
            for cluster in unknown_registry.list_clusters()
        ],
        "memory_runs": [
            {
                "memory_run_id": str(item.id),
                "upload_id": str(item.upload_id),
                "selected_face_index": item.selected_face_index,
                "status": item.status.value,
                "notes": item.notes,
                "memory_report": item.memory_report,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            }
            for item in memory_runs
        ],
        "uploads": upload_items,
    }


def _create_active_learning_questions(
    *,
    user_id: str,
    memory_run_id: UUID,
    upload_id: UUID,
    result: UploadRecognitionResult,
) -> list[ActiveLearningQuestion]:
    registry = get_active_learning_registry(user_id)
    signal_registry = get_learning_signal_registry(user_id)
    questions: list[ActiveLearningQuestion] = []

    if result.status == "tentative" and result.top_candidate_name:
        signal = signal_registry.upsert_signal(
            signal_type="tentative_match",
            source="memory_run",
            source_id=str(memory_run_id),
            summary=f"Tentative match needs review: {result.top_candidate_name}",
            dedupe_key=f"tentative_match:{memory_run_id}:{result.selected_face_index}",
            domain_type="person",
            confidence=result.confidence,
            learning_value=0.82,
            risk_level="medium",
            evidence=["tentative_match", result.reason or "local recognition"],
            metadata={
                "candidate_label": result.top_candidate_name,
                "candidate_count": result.candidate_count,
                "quality_score": result.quality_score,
            },
        )
        context = {
            "reason": result.reason,
            "provider": result.top_candidate_provider,
            "candidate_count": result.candidate_count,
            "quality_score": result.quality_score,
            "memory_run_id": str(memory_run_id),
        }
        score = active_learning_priority_scorer.score(
            question_type="confirm_match",
            confidence=result.confidence,
            domain_type="person",
            suggested_action="confirm_or_reject_match",
            context=context,
            signals=signal_registry.list_signals(),
        )
        questions.append(
            registry.upsert_question(
                question_type="confirm_match",
                prompt=f"Is this {result.top_candidate_name}?",
                dedupe_key=(
                    f"confirm_match:{upload_id}:{result.selected_face_index}:"
                    f"{result.top_candidate_name.strip().lower()}"
                ),
                domain_type="person",
                priority=score.priority,
                priority_reason=score.priority_reason,
                confidence=result.confidence,
                source_signal_ids=[signal.signal_id, *score.source_signal_ids],
                learning_value=score.learning_value,
                risk_level=score.risk_level,
                cooldown_until=score.cooldown_until,
                suggested_action="confirm_or_reject_match",
                memory_run_id=str(memory_run_id),
                upload_id=str(upload_id),
                selected_face_index=result.selected_face_index,
                candidate_label=result.top_candidate_name,
                candidate_reference_id=result.reference_id,
                context=context,
            )
        )

    if (
        result.status == "unknown"
        and result.unknown_cluster_id
        and result.unknown_cluster_suggested_for_enrollment
    ):
        signal = signal_registry.upsert_signal(
            signal_type="familiar_unknown",
            source="unknown_face_cluster",
            source_id=result.unknown_cluster_id,
            summary="Familiar unknown person is ready for review",
            dedupe_key=f"familiar_unknown:{result.unknown_cluster_id}",
            domain_type="person",
            confidence=result.confidence,
            learning_value=0.78,
            risk_level="medium",
            evidence=[f"sighting_count:{result.unknown_cluster_sighting_count}"],
            metadata={
                "unknown_cluster_id": result.unknown_cluster_id,
                "sighting_count": result.unknown_cluster_sighting_count,
                "quality_score": result.quality_score,
            },
        )
        context = {
            "unknown_sample_id": result.unknown_sample_id,
            "unknown_cluster_id": result.unknown_cluster_id,
            "sighting_count": result.unknown_cluster_sighting_count,
            "quality_score": result.quality_score,
            "reason": result.reason,
            "memory_run_id": str(memory_run_id),
        }
        score = active_learning_priority_scorer.score(
            question_type="label_unknown_cluster",
            confidence=result.confidence,
            domain_type="person",
            suggested_action="label_or_dismiss_unknown_cluster",
            context=context,
            signals=signal_registry.list_signals(),
        )
        questions.append(
            registry.upsert_question(
                question_type="label_unknown_cluster",
                prompt="Who is this familiar unknown person?",
                dedupe_key=f"label_unknown_cluster:{result.unknown_cluster_id}",
                domain_type="person",
                priority=score.priority,
                priority_reason=score.priority_reason,
                confidence=result.confidence,
                source_signal_ids=[signal.signal_id, *score.source_signal_ids],
                learning_value=score.learning_value,
                risk_level=score.risk_level,
                cooldown_until=score.cooldown_until,
                suggested_action="label_or_dismiss_unknown_cluster",
                memory_run_id=str(memory_run_id),
                upload_id=str(upload_id),
                selected_face_index=result.selected_face_index,
                unknown_cluster_id=result.unknown_cluster_id,
                context=context,
            )
        )

    return questions


def _promote_unknown_cluster_from_question(
    *,
    user_id: str,
    question: ActiveLearningQuestion,
    label: str,
    notes: str | None,
    tags: list[str],
    db: Session,
) -> dict[str, object]:
    if not question.unknown_cluster_id:
        raise HTTPException(status_code=400, detail="Question is not linked to an unknown cluster")
    unknown_registry = get_unknown_face_registry(user_id)
    cluster = unknown_registry.find_cluster(question.unknown_cluster_id)
    if cluster is None or cluster.promoted:
        raise HTTPException(status_code=404, detail="Unknown cluster not found")
    samples = unknown_registry.samples_for_cluster(question.unknown_cluster_id)
    if not samples:
        raise HTTPException(status_code=400, detail="Unknown cluster has no usable samples")

    user_registry = get_face_reference_registry(user_id)
    records = []
    for sample in samples:
        source_upload = db.get(Upload, UUID(sample.source_upload_id))
        records.append(
            user_registry.add_reference(
                name_or_alias=label,
                embedding=sample.embedding,
                provider=sample.provider,
                source_image_path=source_upload.file_path if source_upload else None,
                face_index=sample.face_index,
                notes=notes,
                tags=tags,
            )
        )
    unknown_registry.mark_cluster_promoted(question.unknown_cluster_id)
    _sync_person_entity_from_reference(
        user_id=user_id,
        reference=records[0],
        confidence=1.0,
        source_upload_id=samples[0].source_upload_id,
    )
    return {
        "created_references": len(records),
        "reference_id": records[0].reference_id,
        "entity_domain": "person",
        "label": label,
    }


def _safe_remove_tree(path: Path, root: Path) -> None:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_path == resolved_root or resolved_root not in resolved_path.parents:
        raise RuntimeError(f"Refusing to delete outside storage root: {resolved_path}")
    if resolved_path.exists():
        shutil.rmtree(resolved_path)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    logger.info("Database initialized")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/ready", response_model=ReadinessResponse)
def readiness(db: Session = Depends(get_db)) -> ReadinessResponse | Response:
    dependencies = {"database": False}
    try:
        db.execute(text("SELECT 1"))
        dependencies["database"] = True
    except Exception:
        pass

    status = "ok" if all(dependencies.values()) else "not ready"
    health_items = provider_health(settings.model_cache_dir)
    payload = ReadinessResponse(
        status=status,
        dependencies=dependencies,
        optional_features={
            "embedding_provider": settings.embedding_provider,
            "vector_store": settings.vector_store,
            "job_backend": settings.job_backend,
            "providers": [
                {
                    "provider_id": item.provider_id,
                    "ready": item.ready,
                    "status": item.status,
                }
                for item in health_items
            ],
        },
    )
    if status != "ok":
        return Response(content=payload.model_dump_json(), media_type="application/json", status_code=503)
    return payload


@app.post("/api/v1/upload", response_model=UploadResponse)
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


@app.post("/api/v1/identity/references", response_model=FaceReferenceEnrollResponse, status_code=201)
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


@app.post("/api/v1/memory-runs/{memory_run_id}/reference", response_model=FaceReferenceEnrollResponse, status_code=201)
def enroll_memory_run_face_reference(
    memory_run_id: UUID,
    payload: FaceReferenceEnrollRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FaceReferenceEnrollResponse:
    memory_run = db.query(MemoryRun).filter(
        MemoryRun.id == memory_run_id,
        MemoryRun.user_id == current_user.id,
    ).first()
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


@app.get("/api/v1/memory-domains", response_model=MemoryDomainListResponse)
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


@app.get("/api/v1/memory-domain-templates", response_model=MemoryDomainTemplateListResponse)
def list_memory_domain_templates() -> MemoryDomainTemplateListResponse:
    return MemoryDomainTemplateListResponse(
        templates=[_domain_template_item(template) for template in domain_template_catalog.list_templates()]
    )


@app.get("/api/v1/memory-domain-templates/{template_id}", response_model=MemoryDomainTemplateItem)
def get_memory_domain_template(template_id: str) -> MemoryDomainTemplateItem:
    template = domain_template_catalog.find(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Memory domain template not found")
    return _domain_template_item(template)


@app.post(
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
            observation_id=f"template-{template_id}-{datetime.now(timezone.utc).timestamp()}",
            source="template",
            modality=str(entity_payload["observation_modality"]),
            confidence=confidence,
            notes=payload.notes,
            observed_at=datetime.now(timezone.utc).isoformat(),
        ),
    )
    return MemoryEntityCreateResponse(
        entity=_memory_entity_item(record),
        total_entities=registry.entity_count(),
    )


@app.get("/api/v1/memory-entities", response_model=MemoryEntityListResponse)
def list_memory_entities(
    domain_type: str | None = None,
    current_user: User = Depends(get_current_user),
) -> MemoryEntityListResponse:
    _sync_face_references_to_memory_entities(str(current_user.id))
    registry = get_memory_entity_registry(str(current_user.id))
    return MemoryEntityListResponse(
        entities=[_memory_entity_item(record) for record in registry.list_entities(domain_type)]
    )


@app.get("/api/v1/memory-entities/search", response_model=MemorySearchResponse)
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


@app.post("/api/v1/memory-entities", response_model=MemoryEntityCreateResponse, status_code=201)
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
                observation_id=f"manual-{datetime.now(timezone.utc).timestamp()}",
                source="manual",
                modality="vision",
                confidence=payload.confidence,
                notes=payload.notes,
                observed_at=datetime.now(timezone.utc).isoformat(),
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return MemoryEntityCreateResponse(
        entity=_memory_entity_item(record),
        total_entities=registry.entity_count(),
    )


@app.get("/api/v1/memory-entities/{entity_id}", response_model=MemoryEntityItem)
def get_memory_entity(
    entity_id: str,
    current_user: User = Depends(get_current_user),
) -> MemoryEntityItem:
    _sync_face_references_to_memory_entities(str(current_user.id))
    record = get_memory_entity_registry(str(current_user.id)).find(entity_id)
    if not record:
        raise HTTPException(status_code=404, detail="Memory entity not found")
    return _memory_entity_item(record)


@app.patch("/api/v1/memory-entities/{entity_id}", response_model=CorrectionResponse)
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
    return CorrectionResponse(correction=_correction_log_item(correction), entity=_memory_entity_item(record))


@app.get("/api/v1/memory-entities/{entity_id}/detail", response_model=MemoryEntityDetailResponse)
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
        replay_suggestions=[
            _replay_suggestion_item(item)
            for item in detail["replay_suggestions"]
        ],
        learning_timeline=detail["learning_timeline"],
        summary=detail["summary"],
    )


@app.get("/api/v1/memory-entities/{entity_id}/confidence-ledger", response_model=ConfidenceLedgerResponse)
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


@app.post(
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
            signal_type="candidate_review" if record.lifecycle_state == "candidate" else "domain_review",
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


@app.get("/api/v1/learning/signals", response_model=LearningSignalListResponse)
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


@app.get("/api/v1/learning/policy", response_model=LearningPolicyItem)
def get_learning_policy(current_user: User = Depends(get_current_user)) -> LearningPolicyItem:
    return _learning_policy_item(get_learning_policy_registry(str(current_user.id)).get())


@app.put("/api/v1/learning/policy", response_model=LearningPolicyItem)
def update_learning_policy(
    payload: LearningPolicyUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> LearningPolicyItem:
    return _learning_policy_item(get_learning_policy_registry(str(current_user.id)).set_preset(payload.preset))


@app.get("/api/v1/learning/policy/simulation", response_model=LearningPolicySimulationResponse)
def simulate_current_learning_policy(current_user: User = Depends(get_current_user)) -> LearningPolicySimulationResponse:
    user_id = str(current_user.id)
    entity_registry = get_memory_entity_registry(user_id)
    return LearningPolicySimulationResponse(
        **simulate_learning_policy(
            policy=get_learning_policy_registry(user_id).get(),
            entities=entity_registry.list_entities(),
            learning_signals=get_learning_signal_registry(user_id).list_signals(status=None),
            corrections=get_correction_log_registry(user_id).list_records(),
            active_learning_questions=get_active_learning_registry(user_id).list_questions(status=None),
        )
    )


@app.post("/api/v1/learning/signals/{signal_id}/dismiss", response_model=LearningSignalItem)
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


@app.get("/api/v1/learning/review-inbox", response_model=LearningReviewInboxResponse)
def get_learning_review_inbox(current_user: User = Depends(get_current_user)) -> LearningReviewInboxResponse:
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
            LearningReviewMemoryItem(entity=_memory_entity_item(row["entity"]), health=row["health"])
            for row in inbox["candidate_memories"]
        ],
        low_health_memories=[
            LearningReviewMemoryItem(entity=_memory_entity_item(row["entity"]), health=row["health"])
            for row in inbox["low_health_memories"]
        ],
        replay_suggestions=[_replay_suggestion_item(item) for item in inbox["replay_suggestions"]],
        signals=[_learning_signal_item(signal) for signal in inbox["signals"]],
        summary=inbox["summary"],
    )


@app.post("/api/v1/memory-entities/{entity_id}/learning/replay", response_model=LearningReplayResponse)
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


@app.get("/api/v1/privacy/settings", response_model=PrivacySettingsItem)
def get_privacy_settings(current_user: User = Depends(get_current_user)) -> PrivacySettingsItem:
    return _privacy_settings_item(get_privacy_settings_registry(str(current_user.id)).get())


@app.put("/api/v1/privacy/settings", response_model=PrivacySettingsItem)
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


@app.get("/api/v1/providers", response_model=ProviderMarketplaceResponse)
def list_providers(current_user: User = Depends(get_current_user)) -> ProviderMarketplaceResponse:
    user_id = str(current_user.id)
    local_only, allow_hosted = _provider_privacy_flags(user_id)
    cards = provider_marketplace.list_cards(privacy_local_only=local_only, allow_hosted=allow_hosted)
    selections = get_provider_selection_registry(user_id).get().selections
    return ProviderMarketplaceResponse(
        providers=[_provider_card_item(card) for card in cards],
        capabilities=sorted(PROVIDER_CAPABILITIES),
        selections=selections,
    )


@app.get("/api/v1/provider-plugins", response_model=ProviderPluginListResponse)
def list_provider_plugins(current_user: User = Depends(get_current_user)) -> ProviderPluginListResponse:
    user_id = str(current_user.id)
    local_only, allow_hosted = _provider_privacy_flags(user_id)
    plugin_cards = [
        provider_marketplace._card_with_policy_status(
            card,
            privacy_local_only=local_only,
            allow_hosted=allow_hosted,
        )
        for card in provider_marketplace.plugin_registry.list_cards()
    ]
    return ProviderPluginListResponse(
        plugins=[_provider_card_item(card) for card in plugin_cards],
        manifest_dirs=[path.name for path in provider_marketplace.plugin_registry.manifest_dirs],
    )


@app.get("/api/v1/provider-conformance", response_model=ProviderConformanceListResponse)
def list_provider_conformance(current_user: User = Depends(get_current_user)) -> ProviderConformanceListResponse:
    user_id = str(current_user.id)
    local_only, allow_hosted = _provider_privacy_flags(user_id)
    cards = provider_marketplace.list_cards(privacy_local_only=local_only, allow_hosted=allow_hosted)
    return ProviderConformanceListResponse(**evaluate_provider_catalog(cards))


@app.get("/api/v1/providers/health", response_model=ProviderHealthResponse)
def list_provider_health(current_user: User = Depends(get_current_user)) -> ProviderHealthResponse:
    _ = current_user
    return ProviderHealthResponse(
        providers=[
            ProviderHealthItem(
                provider_id=item.provider_id,
                ready=item.ready,
                status=item.status,
                detail=item.detail,
                model_cache_dir=item.model_cache_dir,
                optional_dependencies=item.optional_dependencies,
            )
            for item in provider_health(settings.model_cache_dir)
        ]
    )


@app.get("/api/v1/providers/selection", response_model=ProviderSelectionResponse)
def get_provider_selection(current_user: User = Depends(get_current_user)) -> ProviderSelectionResponse:
    user_id = str(current_user.id)
    local_only, allow_hosted = _provider_privacy_flags(user_id)
    record = get_provider_selection_registry(user_id).get()
    provider_id = record.selections.get("face_embedding") or "local-face-embedding"
    card = provider_marketplace.find_card(provider_id, privacy_local_only=local_only, allow_hosted=allow_hosted)
    if card is None:
        card = provider_marketplace.find_card(
            "local-face-embedding",
            privacy_local_only=local_only,
            allow_hosted=allow_hosted,
        )
    assert card is not None
    return ProviderSelectionResponse(
        selections=record.selections,
        updated_at=datetime.fromisoformat(record.updated_at),
        provider=_provider_card_item(card),
    )


@app.put("/api/v1/providers/selection", response_model=ProviderSelectionResponse)
def update_provider_selection(
    payload: ProviderSelectionRequest,
    current_user: User = Depends(get_current_user),
) -> ProviderSelectionResponse:
    user_id = str(current_user.id)
    local_only, allow_hosted = _provider_privacy_flags(user_id)
    capability = ProviderSelectionRegistry.normalize_capability(payload.capability)
    if capability not in PROVIDER_CAPABILITIES:
        raise HTTPException(status_code=400, detail="Unsupported provider capability")
    card = provider_marketplace.find_card(
        payload.provider_id,
        privacy_local_only=local_only,
        allow_hosted=allow_hosted,
    )
    if card is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    if capability not in card.capabilities:
        raise HTTPException(status_code=400, detail="Provider does not support requested capability")
    if card.status == "blocked_by_privacy_policy":
        raise HTTPException(status_code=403, detail="Provider is blocked by privacy settings")
    record = get_provider_selection_registry(user_id).set_selection(
        capability=capability,
        provider_id=card.provider_id,
    )
    return ProviderSelectionResponse(
        selections=record.selections,
        updated_at=datetime.fromisoformat(record.updated_at),
        provider=_provider_card_item(card),
    )


@app.get("/api/v1/memory-lifecycle/summary", response_model=MemoryLifecycleSummaryResponse)
def memory_lifecycle_summary(current_user: User = Depends(get_current_user)) -> MemoryLifecycleSummaryResponse:
    summary = get_memory_entity_registry(str(current_user.id)).lifecycle_summary()
    return MemoryLifecycleSummaryResponse(**summary)


@app.post("/api/v1/memory-lifecycle/decay-stale", response_model=MemoryLifecycleOperationResponse)
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


@app.post("/api/v1/memory-entities/{entity_id}/lifecycle/reinforce", response_model=MemoryLifecycleOperationResponse)
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


@app.post("/api/v1/memory-entities/{entity_id}/lifecycle/contradiction", response_model=MemoryLifecycleOperationResponse)
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
        signal_type="active_learning_confirmation" if payload.reason and "confirm" in payload.reason.lower() else "positive_observation",
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


@app.get("/api/v1/corrections", response_model=CorrectionListResponse)
def list_corrections(current_user: User = Depends(get_current_user)) -> CorrectionListResponse:
    corrections = get_correction_log_registry(str(current_user.id)).list_records()
    return CorrectionListResponse(corrections=[_correction_log_item(item) for item in corrections])


@app.post("/api/v1/corrections/{correction_id}/undo", response_model=CorrectionResponse)
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


@app.post("/api/v1/memory-entities/{entity_id}/corrections/rename", response_model=CorrectionResponse)
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
    return CorrectionResponse(correction=_correction_log_item(correction), entity=_memory_entity_item(record))


@app.post("/api/v1/memory-entities/{entity_id}/corrections/forget", response_model=CorrectionResponse)
def forget_memory_entity(
    entity_id: str,
    payload: MemoryEntityForgetRequest,
    current_user: User = Depends(get_current_user),
) -> CorrectionResponse:
    user_id = str(current_user.id)
    registry = get_memory_entity_registry(user_id)
    before = registry.snapshot()
    record = registry.set_lifecycle(entity_id=entity_id, lifecycle_state=payload.mode, notes=payload.notes)
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
    return CorrectionResponse(correction=_correction_log_item(correction), entity=_memory_entity_item(record))


@app.post("/api/v1/memory-entities/{entity_id}/corrections/not-this", response_model=CorrectionResponse)
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
    return CorrectionResponse(correction=_correction_log_item(correction), entity=_memory_entity_item(record))


@app.post("/api/v1/memory-entities/{entity_id}/corrections/merge", response_model=CorrectionResponse)
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


@app.post("/api/v1/memory-entities/{entity_id}/corrections/split", response_model=CorrectionResponse)
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
        metadata={"new_entity_id": new_entity.entity_id, "observation_ids": payload.observation_ids},
    )
    return CorrectionResponse(
        correction=_correction_log_item(correction),
        entity=_memory_entity_item(original),
        related_entities=[_memory_entity_item(new_entity)],
    )


@app.get("/api/v1/active-learning/questions", response_model=ActiveLearningQuestionListResponse)
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


@app.post(
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
            raise HTTPException(status_code=400, detail="Question has no candidate label to confirm")
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
            raise HTTPException(status_code=400, detail="A label is required for this active-learning response")
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
    linked_entity_id = answered.context.get("entity_id") if isinstance(answered.context, dict) else None
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
        signal_type="active_learning_confirmation" if action in {"confirm", "label"} else "active_learning_response",
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


@app.post("/api/v1/memory-runs", response_model=MemoryRunCreateResponse)
def create_memory_run(
    payload: MemoryRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MemoryRunCreateResponse:
    upload = db.query(Upload).filter(Upload.id == payload.upload_id, Upload.user_id == current_user.id).first()
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
    unknown_payload = _store_unknown_sample_if_useful(user_id=str(current_user.id), upload_id=upload.id, result=result)
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

    memory_report_payload = _local_memory_report(recognition_result, payload.notes).model_dump(mode="json")
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
    db.add(Activity(memory_run_id=memory_run.id, stage="done", message="Local vision memory run complete"))
    db.commit()
    db.refresh(memory_run)
    return MemoryRunCreateResponse(memory_run_id=memory_run.id, recognition_result=recognition_result)


@app.get("/api/v1/memory-runs/{memory_run_id}", response_model=MemoryRunResponse)
def get_memory_run(
    memory_run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MemoryRunResponse:
    memory_run = db.query(MemoryRun).filter(
        MemoryRun.id == memory_run_id,
        MemoryRun.user_id == current_user.id,
    ).first()
    if not memory_run:
        raise HTTPException(status_code=404, detail="Memory run not found")

    activities: List[ActivityEntry] = [
        ActivityEntry(stage=activity.stage, message=activity.message, created_at=activity.created_at)
        for activity in memory_run.activities
    ]
    memory_report = MemoryReport.model_validate(memory_run.memory_report) if memory_run.memory_report else None
    return MemoryRunResponse(
        id=memory_run.id,
        status=memory_run.status,
        memory_report=memory_report,
        activities=activities,
    )


@app.get("/api/v1/memory-runs", response_model=MemoryRunHistoryResponse)
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


@app.get("/api/v1/memory-run-events/stream")
def memory_run_stream() -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        while True:
            yield ": keep-alive\n\n"
            await asyncio.sleep(15)

    return StreamingResponse(events(), media_type="text/event-stream")


@app.delete("/api/v1/upload/{upload_id}", status_code=204)
def delete_upload(
    upload_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    upload = db.query(Upload).filter(Upload.id == upload_id, Upload.user_id == current_user.id).first()
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


@app.delete("/api/v1/memory-runs/{memory_run_id}", status_code=204)
def delete_memory_run(
    memory_run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    memory_run = db.query(MemoryRun).filter(
        MemoryRun.id == memory_run_id,
        MemoryRun.user_id == current_user.id,
    ).first()
    if not memory_run:
        raise HTTPException(status_code=404, detail="Memory run not found")
    db.delete(memory_run)
    db.commit()
    return Response(status_code=204)


@app.get("/api/v1/data/export")
def export_user_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    return JSONResponse(_build_user_export_payload(db=db, current_user=current_user))

@app.post("/api/v1/data/vault/export")
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


@app.post("/api/v1/data/vault/import", response_model=VaultImportResponse)
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


def _evaluation_context(*, db: Session, current_user: User) -> dict[str, object]:
    user_id = str(current_user.id)
    _sync_face_references_to_memory_entities(user_id)
    entity_registry = get_memory_entity_registry(user_id)
    active_learning_registry = get_active_learning_registry(user_id)
    learning_signal_registry = get_learning_signal_registry(user_id)
    correction_registry = get_correction_log_registry(user_id)
    privacy_settings = get_privacy_settings_registry(user_id).get()
    provider_selection = get_provider_selection_registry(user_id).get()
    local_only, allow_hosted = _provider_privacy_flags(user_id)
    memory_runs = db.query(MemoryRun).filter(MemoryRun.user_id == current_user.id).all()
    memory_entities = entity_registry.list_entities()
    active_learning_questions = active_learning_registry.list_questions(status=None)
    corrections = correction_registry.list_records()
    learning_signals = learning_signal_registry.list_signals(status=None)
    return {
        "user_id": user_id,
        "references": get_face_reference_registry(user_id),
        "unknown_registry": get_unknown_face_registry(user_id),
        "entity_registry": entity_registry,
        "active_learning_registry": active_learning_registry,
        "learning_signal_registry": learning_signal_registry,
        "correction_registry": correction_registry,
        "privacy_settings": privacy_settings,
        "provider_selection": provider_selection,
        "provider_cards": provider_marketplace.list_cards(
            privacy_local_only=local_only,
            allow_hosted=allow_hosted,
        ),
        "memory_runs": memory_runs,
        "memory_entities": memory_entities,
        "active_learning_questions": active_learning_questions,
        "learning_signals": learning_signals,
        "corrections": corrections,
        "lifecycle_summary": entity_registry.lifecycle_summary(),
        "memory_health_distribution": build_memory_health_distribution(
            entities=memory_entities,
            corrections=corrections,
            active_learning_questions=active_learning_questions,
            learning_signals=learning_signals,
        ),
    }


@app.get("/api/v1/evaluation/summary")
def evaluation_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    context = _evaluation_context(db=db, current_user=current_user)
    references = context["references"]
    unknown_registry = context["unknown_registry"]
    entity_registry = context["entity_registry"]
    active_learning_registry = context["active_learning_registry"]
    correction_registry = context["correction_registry"]
    privacy_settings = context["privacy_settings"]
    provider_selection = context["provider_selection"]
    memory_run_count = db.query(MemoryRun).filter(MemoryRun.user_id == current_user.id).count()
    upload_count = db.query(Upload).filter(Upload.user_id == current_user.id).count()
    clusters = unknown_registry.list_clusters()
    domain_counts = {
        domain_type: entity_registry.entity_count(domain_type)
        for domain_type in entity_registry.list_domain_types()
    }
    lifecycle_summary = context["lifecycle_summary"]
    metrics = build_evaluation_metrics(
        memory_runs=context["memory_runs"],
        active_learning_questions=context["active_learning_questions"],
        corrections=context["corrections"],
        memory_entities=context["memory_entities"],
        learning_signals=context["learning_signals"],
        memory_health_distribution=context["memory_health_distribution"],
        review_inbox_pending_count=active_learning_registry.pending_count()
        + context["learning_signal_registry"].pending_count(),
        lifecycle_summary=lifecycle_summary,
    )

    return JSONResponse(
        {
            "memory_runs": memory_run_count,
            "uploads": upload_count,
            "memory_entities": entity_registry.entity_count(),
            "memory_domains": domain_counts,
            "memory_lifecycle": lifecycle_summary,
            "active_learning_pending_questions": active_learning_registry.pending_count(),
            "corrections": correction_registry.count(),
            "privacy": {
                "local_only_mode": privacy_settings.local_only_mode,
                "allow_hosted_providers": privacy_settings.allow_hosted_providers,
                "export_include_biometric_embeddings": False,
                "export_include_upload_paths": privacy_settings.export_include_upload_paths,
            },
            "provider_selections": provider_selection.selections,
            "identity_references": references.reference_count(),
            "unknown_samples": unknown_registry.sample_count(),
            "unknown_clusters": len(clusters),
            "suggested_clusters": len([cluster for cluster in clusters if cluster.suggested_for_enrollment]),
            "provider": references.provider_name() or settings.embedding_provider,
            "evaluation_metrics": metrics,
        }
    )


@app.get("/api/v1/evaluation/metrics", response_model=EvaluationMetricsResponse)
def evaluation_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EvaluationMetricsResponse:
    context = _evaluation_context(db=db, current_user=current_user)
    return EvaluationMetricsResponse(
        **build_evaluation_metrics(
            memory_runs=context["memory_runs"],
            active_learning_questions=context["active_learning_questions"],
            corrections=context["corrections"],
            memory_entities=context["memory_entities"],
            learning_signals=context["learning_signals"],
            memory_health_distribution=context["memory_health_distribution"],
            review_inbox_pending_count=context["active_learning_registry"].pending_count()
            + context["learning_signal_registry"].pending_count(),
            lifecycle_summary=context["lifecycle_summary"],
        )
    )


@app.get("/api/v1/evaluation/dataset", response_model=EvaluationDatasetResponse)
def evaluation_dataset(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EvaluationDatasetResponse:
    context = _evaluation_context(db=db, current_user=current_user)
    return EvaluationDatasetResponse(
        **build_evaluation_dataset(
            active_learning_questions=context["active_learning_questions"],
            corrections=context["corrections"],
            memory_entities=context["memory_entities"],
        )
    )


@app.get("/api/v1/evaluation/provider-scorecard", response_model=ProviderScorecardResponse)
def evaluation_provider_scorecard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProviderScorecardResponse:
    context = _evaluation_context(db=db, current_user=current_user)
    metrics = build_evaluation_metrics(
        memory_runs=context["memory_runs"],
        active_learning_questions=context["active_learning_questions"],
        corrections=context["corrections"],
        memory_entities=context["memory_entities"],
        learning_signals=context["learning_signals"],
        memory_health_distribution=context["memory_health_distribution"],
        review_inbox_pending_count=context["active_learning_registry"].pending_count()
        + context["learning_signal_registry"].pending_count(),
        lifecycle_summary=context["lifecycle_summary"],
    )
    provider_selection = context["provider_selection"]
    return ProviderScorecardResponse(
        **build_provider_scorecard(
            provider_cards=context["provider_cards"],
            provider_selections=provider_selection.selections,
            evaluation_metrics=metrics,
        )
    )


@app.get("/api/v1/evaluation/benchmark-pack", response_model=BenchmarkPackResponse)
def evaluation_benchmark_pack() -> BenchmarkPackResponse:
    return BenchmarkPackResponse(**build_benchmark_pack())


@app.get("/api/v1/evaluation/benchmark-runs", response_model=BenchmarkRunListResponse)
def list_evaluation_benchmark_runs(
    current_user: User = Depends(get_current_user),
) -> BenchmarkRunListResponse:
    records = get_benchmark_run_registry(str(current_user.id)).list_runs()
    return BenchmarkRunListResponse(
        runs=[_benchmark_run_item(record) for record in records],
        run_count=len(records),
    )


@app.post("/api/v1/evaluation/benchmark-runs", response_model=BenchmarkRunItem, status_code=201)
def create_evaluation_benchmark_run(
    payload: BenchmarkRunCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BenchmarkRunItem:
    context = _evaluation_context(db=db, current_user=current_user)
    metrics = build_evaluation_metrics(
        memory_runs=context["memory_runs"],
        active_learning_questions=context["active_learning_questions"],
        corrections=context["corrections"],
        memory_entities=context["memory_entities"],
        learning_signals=context["learning_signals"],
        memory_health_distribution=context["memory_health_distribution"],
        review_inbox_pending_count=context["active_learning_registry"].pending_count()
        + context["learning_signal_registry"].pending_count(),
        lifecycle_summary=context["lifecycle_summary"],
    )
    provider_selection = context["provider_selection"]
    record = get_benchmark_run_registry(str(current_user.id)).add_run(
        label=payload.label,
        notes=payload.notes,
        benchmark_case_ids=payload.benchmark_case_ids,
        provider_selections=provider_selection.selections,
        metrics=metrics,
    )
    return _benchmark_run_item(record)


@app.delete("/api/v1/data/purge", status_code=204)
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
    _safe_remove_tree(storage_root / "face-references" / str(current_user.id), storage_root)
    _safe_remove_tree(storage_root / "unknown-faces" / str(current_user.id), storage_root)
    _safe_remove_tree(storage_root / "memory-entities" / str(current_user.id), storage_root)
    _safe_remove_tree(storage_root / "active-learning" / str(current_user.id), storage_root)
    _safe_remove_tree(storage_root / "learning-signals" / str(current_user.id), storage_root)
    _safe_remove_tree(storage_root / "learning-policy" / str(current_user.id), storage_root)
    _safe_remove_tree(storage_root / "corrections" / str(current_user.id), storage_root)
    _safe_remove_tree(storage_root / "privacy-settings" / str(current_user.id), storage_root)
    _safe_remove_tree(storage_root / "provider-selections" / str(current_user.id), storage_root)
    _safe_remove_tree(storage_root / "benchmark-runs" / str(current_user.id), storage_root)
    db.commit()
    return Response(status_code=204)
