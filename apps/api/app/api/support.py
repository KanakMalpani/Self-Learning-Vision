"""Shared registries, providers, and response helpers for the HTTP API."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import MemoryRun, Upload, User
from app.schemas import (
    ActiveLearningQuestionItem,
    ActiveLearningResponseItem,
    BenchmarkRunItem,
    CorrectionLogItem,
    FaceReferenceItem,
    LearningPolicyItem,
    LearningReplaySuggestionItem,
    LearningSignalItem,
    MemoryDomainTemplateItem,
    MemoryEntityItem,
    MemoryLifecycleEventItem,
    MemoryObservationItem,
    PrivacySettingsItem,
    ProviderCardItem,
    UploadRecognitionResult,
)
from app.schemas.memory_report import Fact, MemoryReport, MemoryReportConfidence, Subject
from app.services.active_learning_priority import ActiveLearningPriorityScorer
from app.services.active_learning_registry import (
    ActiveLearningQuestion,
    ActiveLearningRegistry,
    ActiveLearningResponse,
)
from app.services.benchmark_run_registry import BenchmarkRunRecord, BenchmarkRunRegistry
from app.services.core_engine import RecognitionCoreService
from app.services.correction_log_registry import CorrectionLogRecord, CorrectionLogRegistry
from app.services.domain_active_learning import DomainActiveLearningPlanner
from app.services.domain_templates import DomainTemplateCatalog, MemoryDomainTemplate
from app.services.face_detection import FaceDetectionService
from app.services.face_reference_registry import FaceReferenceRegistry
from app.services.learning_policy_registry import LearningPolicyRecord, LearningPolicyRegistry
from app.services.learning_signal_registry import LearningSignalRecord, LearningSignalRegistry
from app.services.memory_entity_registry import (
    MemoryEntityRecord,
    MemoryEntityRegistry,
    MemoryLifecycleEvent,
    MemoryObservation,
)
from app.services.memory_health import build_memory_health_distribution
from app.services.memory_lifecycle_policy import MemoryLifecyclePolicy
from app.services.privacy_settings_registry import PrivacySettingsRecord, PrivacySettingsRegistry
from app.services.privacy_vault import PrivacyVaultService
from app.services.provider_marketplace import (
    ProviderCard,
    ProviderMarketplace,
    ProviderSelectionRegistry,
)
from app.services.recognition import select_embedding_provider
from app.services.storage import StorageService
from app.services.unknown_face_registry import UnknownFaceRegistry
from app.utils.logger import get_logger

logger = get_logger(__name__)

storage_service = StorageService(settings.storage_dir)

face_service = FaceDetectionService()

privacy_vault_service = PrivacyVaultService()

provider_marketplace = ProviderMarketplace()

domain_template_catalog = DomainTemplateCatalog()

domain_active_learning_planner = DomainActiveLearningPlanner(domain_template_catalog)

active_learning_priority_scorer = ActiveLearningPriorityScorer()

memory_lifecycle_policy = MemoryLifecyclePolicy()


USER_JSON_REGISTRIES: dict[str, str] = {
    "face-references": "registry.json",
    "unknown-faces": "samples.json",
    "memory-entities": "entities.json",
    "active-learning": "questions.json",
    "learning-signals": "signals.json",
    "learning-policy": "policy.json",
    "corrections": "corrections.json",
    "privacy-settings": "settings.json",
    "provider-selections": "providers.json",
    "benchmark-runs": "runs.json",
}


def _user_registry_file(user_id: str, folder: str) -> Path:
    directory = Path(settings.storage_dir) / folder / str(user_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / USER_JSON_REGISTRIES[folder]


def user_registry_directories(user_id: str) -> list[Path]:
    root = Path(settings.storage_dir)
    return [root / folder / str(user_id) for folder in USER_JSON_REGISTRIES]


def get_face_reference_registry(user_id: str) -> FaceReferenceRegistry:
    return FaceReferenceRegistry(_user_registry_file(user_id, "face-references"))


def get_unknown_face_registry(user_id: str) -> UnknownFaceRegistry:
    return UnknownFaceRegistry(
        _user_registry_file(user_id, "unknown-faces"),
        cluster_similarity_threshold=settings.unknown_cluster_similarity_threshold,
        familiarity_min_samples=settings.unknown_cluster_familiarity_min_samples,
    )


def get_memory_entity_registry(user_id: str) -> MemoryEntityRegistry:
    return MemoryEntityRegistry(_user_registry_file(user_id, "memory-entities"))


def get_active_learning_registry(user_id: str) -> ActiveLearningRegistry:
    return ActiveLearningRegistry(_user_registry_file(user_id, "active-learning"))


def get_learning_signal_registry(user_id: str) -> LearningSignalRegistry:
    return LearningSignalRegistry(_user_registry_file(user_id, "learning-signals"))


def get_learning_policy_registry(user_id: str) -> LearningPolicyRegistry:
    return LearningPolicyRegistry(_user_registry_file(user_id, "learning-policy"))


def get_correction_log_registry(user_id: str) -> CorrectionLogRegistry:
    return CorrectionLogRegistry(_user_registry_file(user_id, "corrections"))


def get_privacy_settings_registry(user_id: str) -> PrivacySettingsRegistry:
    return PrivacySettingsRegistry(_user_registry_file(user_id, "privacy-settings"))


def get_provider_selection_registry(user_id: str) -> ProviderSelectionRegistry:
    return ProviderSelectionRegistry(_user_registry_file(user_id, "provider-selections"))


def get_benchmark_run_registry(user_id: str) -> BenchmarkRunRegistry:
    return BenchmarkRunRegistry(_user_registry_file(user_id, "benchmark-runs"))


def _build_embedding_provider(
    registry: FaceReferenceRegistry | None = None, user_id: str | None = None
):
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
            hosted_requested = (
                hosted_requested
                or selected_card.images_leave_device
                or selected_card.mode
                in {
                    "hosted_paid",
                    "hosted_or_internal",
                }
            )
            if selected_card.status == "blocked_by_privacy_policy":
                logger.warning("Selected embedding provider blocked by privacy settings")
                return None
    if hosted_requested and (
        settings.privacy_local_only_mode or not settings.privacy_allow_hosted_providers
    ):
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


def _active_learning_response_item(
    response: ActiveLearningResponse | None,
) -> ActiveLearningResponseItem | None:
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
        return MemoryLifecyclePolicy(
            high_confidence_threshold=1.01, min_reinforcement_signals=999999
        )
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
    # Initialize the selection file so later provider reads see the same defaults.
    get_provider_selection_registry(user_id).get()
    local_only = privacy_settings.local_only_mode or settings.privacy_local_only_mode
    allow_hosted = (
        privacy_settings.allow_hosted_providers and settings.privacy_allow_hosted_providers
    )
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
        domain_type=(
            str(entity_payload.get("domain_type") or "custom") if entity_payload else "custom"
        ),
        summary=summary,
        dedupe_key=f"correction:{record.correction_id}",
        confidence=float(entity_payload.get("confidence") or 0.0) if entity_payload else 0.0,
        learning_value=0.9 if signal_type == "contradiction" else 0.55,
        risk_level=risk_level,
        evidence=[operation_type],
        metadata={
            "operation_type": operation_type,
            "label": entity_payload.get("label") if entity_payload else None,
        },
    )
    return record


def _find_entity_payload(
    entity_id: str, entities: list[dict[str, object]]
) -> dict[str, object] | None:
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
        observed_at=datetime.now(UTC).isoformat(),
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
        dedupe_key=(
            f"face_reference:{reference.reference_id}:{source_upload_id or reference.seen_count}"
        ),
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
        key_facts.append(
            Fact(title="Memory", detail=result.memory_summary, confidence=result.confidence)
        )
    if result.seen_count is not None:
        key_facts.append(
            Fact(title="Seen count", detail=str(result.seen_count), confidence=result.confidence)
        )
    if result.last_seen_at is not None:
        key_facts.append(
            Fact(
                title="Last seen",
                detail=result.last_seen_at.isoformat(),
                confidence=result.confidence,
            )
        )
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
        "unknown_cluster_suggested_for_enrollment": (
            bool(cluster.suggested_for_enrollment) if cluster else False
        ),
    }


def _provider_privacy_status(privacy_settings: PrivacySettingsRecord) -> dict[str, object]:
    hosted_requested = settings.embedding_provider == "paid" or settings.paid_provider_enabled
    blocked_by_local_only = (
        privacy_settings.local_only_mode or settings.privacy_local_only_mode
    ) and hosted_requested
    return {
        "local_only_mode": privacy_settings.local_only_mode,
        "allow_hosted_providers": privacy_settings.allow_hosted_providers
        and settings.privacy_allow_hosted_providers,
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
        "exported_at": datetime.now(UTC).isoformat(),
        "user_id": user_id,
        "privacy_settings": _privacy_settings_item(privacy_settings).model_dump(mode="json"),
        "provider_privacy": _provider_privacy_status(privacy_settings),
        "provider_selections": provider_selections.selections,
        "learning_policy": _learning_policy_item(
            get_learning_policy_registry(user_id).get()
        ).model_dump(mode="json"),
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
