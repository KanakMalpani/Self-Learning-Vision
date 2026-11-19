from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.memory_run import MemoryRunStatus
from app.schemas.memory_report import MemoryReport


class FaceBox(BaseModel):
    x: float
    y: float
    width: float
    height: float
    score: float


class UploadResponse(BaseModel):
    upload_id: UUID
    face_boxes: list[FaceBox]


class FaceReferenceEnrollRequest(BaseModel):
    name_or_alias: str = Field(min_length=1, max_length=200)
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    selected_face_index: int = Field(default=0, ge=0)
    unknown_cluster_id: str | None = None


class FaceReferenceItem(BaseModel):
    reference_id: str
    name_or_alias: str
    provider: str
    source_image_path: str | None = None
    face_index: int = 0
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    seen_count: int = 0
    last_seen_at: datetime | None = None
    created_at: datetime


class FaceReferenceEnrollResponse(BaseModel):
    reference: FaceReferenceItem
    total_references: int = 0
    embedding_dimensions: int = 0


class MemoryObservationItem(BaseModel):
    observation_id: str
    source: str
    source_id: str | None = None
    modality: str = "vision"
    confidence: float | None = None
    notes: str | None = None
    observed_at: datetime


class MemoryLifecycleEventItem(BaseModel):
    event_id: str
    event_type: str
    from_state: str
    to_state: str
    confidence_before: float
    confidence_after: float
    reason: str | None = None
    created_at: datetime


class MemoryEntityItem(BaseModel):
    entity_id: str
    domain_type: str
    label: str
    attributes: dict[str, object] = Field(default_factory=dict)
    schema_version: str = "1.0"
    user_schema: dict[str, object] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    confidence: float = 0.0
    lifecycle_state: str = "candidate"
    observations: list[MemoryObservationItem] = Field(default_factory=list)
    lifecycle_events: list[MemoryLifecycleEventItem] = Field(default_factory=list)
    source_reference_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class MemoryEntityCreateRequest(BaseModel):
    domain_type: str = Field(default="custom", min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=200)
    attributes: dict[str, object] = Field(default_factory=dict)
    user_schema: dict[str, object] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    lifecycle_state: str = "candidate"


class MemoryEntityUpdateRequest(BaseModel):
    attributes: dict[str, object] | None = None
    user_schema: dict[str, object] | None = None
    aliases: list[str] | None = None
    tags: list[str] | None = None
    notes: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    lifecycle_state: str | None = None


class MemoryEntityCreateResponse(BaseModel):
    entity: MemoryEntityItem
    total_entities: int = 0


class MemorySearchResultItem(BaseModel):
    entity_id: str
    domain_type: str
    label: str
    lifecycle_state: str
    confidence: float
    score: float
    matched_fields: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class MemorySearchResponse(BaseModel):
    query: str = ""
    results: list[MemorySearchResultItem] = Field(default_factory=list)
    result_count: int = 0
    total_candidates: int = 0


class MemoryDomainTemplateItem(BaseModel):
    template_id: str
    domain_type: str
    display_name: str
    description: str
    fields: dict[str, str] = Field(default_factory=dict)
    default_attributes: dict[str, object] = Field(default_factory=dict)
    recommended_tags: list[str] = Field(default_factory=list)
    observation_modality: str = "vision"
    lifecycle_state: str = "candidate"
    confidence: float = 0.5
    prompts: list[str] = Field(default_factory=list)


class MemoryDomainTemplateListResponse(BaseModel):
    templates: list[MemoryDomainTemplateItem]


class MemoryEntityCreateFromTemplateRequest(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    attributes: dict[str, object] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    lifecycle_state: str | None = None


class MemoryEntityCorrectionRequest(BaseModel):
    notes: str | None = None


class MemoryEntityRenameRequest(MemoryEntityCorrectionRequest):
    label: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list)


class MemoryEntityForgetRequest(MemoryEntityCorrectionRequest):
    mode: Literal["archived", "forgotten"] = "archived"


class MemoryEntityNotThisRequest(MemoryEntityCorrectionRequest):
    rejected_label: str | None = Field(default=None, max_length=200)


class MemoryEntityMergeRequest(MemoryEntityCorrectionRequest):
    source_entity_ids: list[str] = Field(min_length=1)


class MemoryEntitySplitRequest(MemoryEntityCorrectionRequest):
    new_label: str = Field(min_length=1, max_length=200)
    observation_ids: list[str] = Field(min_length=1)


class CorrectionLogItem(BaseModel):
    correction_id: str
    operation_type: str
    target_entity_id: str
    summary: str
    metadata: dict[str, object] = Field(default_factory=dict)
    undone: bool = False
    undone_at: datetime | None = None
    created_at: datetime


class CorrectionListResponse(BaseModel):
    corrections: list[CorrectionLogItem]


class CorrectionResponse(BaseModel):
    correction: CorrectionLogItem
    entity: MemoryEntityItem | None = None
    related_entities: list[MemoryEntityItem] = Field(default_factory=list)


class MemoryLifecycleReinforceRequest(BaseModel):
    amount: float = Field(default=0.05, ge=0.0, le=1.0)
    reason: str | None = None


class MemoryLifecycleContradictionRequest(BaseModel):
    rejected_label: str | None = Field(default=None, max_length=200)
    amount: float = Field(default=0.15, ge=0.0, le=1.0)
    reason: str | None = None


class MemoryLifecycleDecayRequest(BaseModel):
    stale_after_days: int = Field(default=30, ge=1, le=3650)
    amount: float = Field(default=0.05, ge=0.0, le=1.0)


class MemoryLifecycleOperationResponse(BaseModel):
    entity: MemoryEntityItem | None = None
    affected_entities: list[MemoryEntityItem] = Field(default_factory=list)
    summary: dict[str, object] = Field(default_factory=dict)


class MemoryLifecycleSummaryResponse(BaseModel):
    total_entities: int = 0
    by_state: dict[str, int] = Field(default_factory=dict)
    by_domain: dict[str, int] = Field(default_factory=dict)
    average_confidence: float = 0.0
    contradictions: int = 0
    lifecycle_events: int = 0


class LearningSignalItem(BaseModel):
    signal_id: str
    signal_type: str
    source: str
    summary: str
    domain_type: str = "custom"
    entity_id: str | None = None
    question_id: str | None = None
    source_id: str | None = None
    status: str = "pending"
    confidence: float = 0.0
    learning_value: float = 0.0
    risk_level: str = "medium"
    evidence: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    resolution: str | None = None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None


class LearningSignalListResponse(BaseModel):
    signals: list[LearningSignalItem] = Field(default_factory=list)
    signal_count: int = 0
    pending_count: int = 0


class LearningSignalDismissRequest(BaseModel):
    reason: str | None = None


class MemoryHealthItem(BaseModel):
    entity_id: str
    score: float = 0.0
    state: str = "watch"
    reasons: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    observation_count: int = 0
    evidence_count: int = 0
    contradiction_count: int = 0
    correction_count: int = 0
    pending_question_count: int = 0
    last_updated_at: str = ""


class MemoryEvidenceBundleItem(BaseModel):
    bundle_id: str
    title: str
    summary: str
    source: str
    event_count: int = 0
    confidence_delta: float = 0.0
    risk_level: str = "low"
    created_at: str = ""
    items: list[dict[str, object]] = Field(default_factory=list)


class LearningReplaySuggestionItem(BaseModel):
    suggestion_id: str
    title: str
    summary: str
    action: str
    risk_level: str = "medium"
    source_signal_ids: list[str] = Field(default_factory=list)


class LearningTimelineItem(BaseModel):
    timeline_id: str
    event_type: str
    title: str
    summary: str
    source: str
    confidence: float | None = None
    created_at: str = ""


class LearningPolicyItem(BaseModel):
    preset: str = "balanced"
    auto_reinforcement_enabled: bool = True
    high_confidence_threshold: float = 0.85
    min_reinforcement_signals: int = 2
    max_reinforcement_amount: float = 0.1
    review_budget_per_session: int = 6
    updated_at: datetime


class LearningPolicyUpdateRequest(BaseModel):
    preset: Literal["conservative", "balanced", "experimental"] = "balanced"


class LearningPolicySimulationResponse(BaseModel):
    preset: str
    auto_reinforcement_enabled: bool = True
    auto_reinforce_count: int = 0
    needs_review_count: int = 0
    blocked_count: int = 0
    review_budget_per_session: int = 0
    auto_reinforce: list[dict[str, object]] = Field(default_factory=list)
    needs_review: list[dict[str, object]] = Field(default_factory=list)
    blocked: list[dict[str, object]] = Field(default_factory=list)


class LearningReviewMemoryItem(BaseModel):
    entity: "MemoryEntityItem"
    health: MemoryHealthItem


class LearningReviewInboxResponse(BaseModel):
    questions: list["ActiveLearningQuestionItem"] = Field(default_factory=list)
    contradictions: list[LearningSignalItem] = Field(default_factory=list)
    candidate_memories: list[LearningReviewMemoryItem] = Field(default_factory=list)
    low_health_memories: list[LearningReviewMemoryItem] = Field(default_factory=list)
    replay_suggestions: list[LearningReplaySuggestionItem] = Field(default_factory=list)
    signals: list[LearningSignalItem] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)


class LearningReplayResponse(BaseModel):
    applied: bool = False
    entity: Optional["MemoryEntityItem"] = None
    affected_signal_ids: list[str] = Field(default_factory=list)
    queued_question_ids: list[str] = Field(default_factory=list)
    suggestions: list[LearningReplaySuggestionItem] = Field(default_factory=list)
    summary: dict[str, object] = Field(default_factory=dict)


class PrivacySettingsItem(BaseModel):
    local_only_mode: bool = True
    allow_hosted_providers: bool = False
    export_include_biometric_embeddings: bool = False
    export_include_upload_paths: bool = False
    data_retention_days: int | None = None
    domain_visibility: dict[str, str] = Field(default_factory=dict)
    updated_at: datetime


class PrivacySettingsUpdateRequest(BaseModel):
    local_only_mode: bool | None = None
    allow_hosted_providers: bool | None = None
    export_include_biometric_embeddings: bool | None = None
    export_include_upload_paths: bool | None = None
    data_retention_days: int | None = Field(default=None, ge=1, le=3650)
    domain_visibility: dict[str, str] | None = None


class VaultExportRequest(BaseModel):
    encrypt: bool = False
    passphrase: str | None = Field(default=None, min_length=8)


class VaultImportRequest(BaseModel):
    vault: dict[str, object] = Field(default_factory=dict)
    passphrase: str | None = Field(default=None, min_length=8)
    replace_memory_entities: bool = False


class VaultImportResponse(BaseModel):
    imported_entities: int = 0
    encrypted: bool = False
    format: str = ""


class ProviderCardItem(BaseModel):
    provider_id: str
    display_name: str
    mode: str
    capabilities: list[str] = Field(default_factory=list)
    status: str
    images_leave_device: bool = False
    embeddings_stored_locally: bool = True
    enabled_by_default: bool = False
    recommended_for: list[str] = Field(default_factory=list)
    env_vars: list[str] = Field(default_factory=list)
    expected_dimensions: int | None = None
    latency_profile: str = "unknown"
    cost_model: str = "free"
    setup: str = ""
    privacy_notes: str = ""
    entrypoint: str | None = None
    manifest_path: str | None = None
    plugin_source: str = "built_in"


class ProviderMarketplaceResponse(BaseModel):
    providers: list[ProviderCardItem]
    capabilities: list[str]
    selections: dict[str, str] = Field(default_factory=dict)


class ProviderSelectionRequest(BaseModel):
    capability: str = Field(min_length=1, max_length=80)
    provider_id: str = Field(min_length=1, max_length=120)


class ProviderSelectionResponse(BaseModel):
    selections: dict[str, str] = Field(default_factory=dict)
    updated_at: datetime
    provider: ProviderCardItem


class ProviderPluginListResponse(BaseModel):
    plugins: list[ProviderCardItem]
    manifest_dirs: list[str] = Field(default_factory=list)


class ProviderConformanceCheckItem(BaseModel):
    check_id: str
    label: str
    passed: bool
    severity: str
    detail: str


class ProviderConformanceReportItem(BaseModel):
    provider_id: str
    display_name: str
    passed: bool
    checks: list[ProviderConformanceCheckItem] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)


class ProviderConformanceListResponse(BaseModel):
    providers: list[ProviderConformanceReportItem] = Field(default_factory=list)
    provider_count: int = 0
    passing_count: int = 0


class ProviderHealthItem(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider_id: str
    ready: bool = False
    status: str
    detail: str = ""
    model_cache_dir: str = ""
    optional_dependencies: dict[str, bool] = Field(default_factory=dict)


class ProviderHealthResponse(BaseModel):
    providers: list[ProviderHealthItem] = Field(default_factory=list)


class EvaluationMetricsResponse(BaseModel):
    memory_runs: int = 0
    recognition_decisions: dict[str, int] = Field(default_factory=dict)
    average_recognition_confidence: float | None = None
    active_learning_questions: int = 0
    active_learning_pending: int = 0
    active_learning_answered: int = 0
    active_learning_actions: dict[str, int] = Field(default_factory=dict)
    corrections: int = 0
    corrections_by_type: dict[str, int] = Field(default_factory=dict)
    memory_entities: int = 0
    memory_lifecycle: dict[str, object] = Field(default_factory=dict)
    passive_signal_count: int = 0
    auto_reinforcement_count: int = 0
    review_inbox_pending_count: int = 0
    contradiction_rate: float = 0.0
    memory_health_distribution: dict[str, int] = Field(default_factory=dict)
    replay_applied_count: int = 0
    false_match_signals: int = 0
    missed_match_signals: int = 0
    uncertainty_rate: float = 0.0
    correction_rate: float = 0.0
    active_learning_completion_rate: float = 0.0
    estimated_precision: float | None = None
    estimated_recall: float | None = None
    memory_growth_per_run: float = 0.0
    notes: list[str] = Field(default_factory=list)


class EvaluationDatasetExample(BaseModel):
    example_id: str
    source: str
    task: str
    domain_type: str | None = None
    status: str | None = None
    action: str | None = None
    label: str | None = None
    candidate_label: str | None = None
    memory_run_id: str | None = None
    upload_id: str | None = None
    selected_face_index: int | None = None
    unknown_cluster_id: str | None = None
    confidence: float | None = None
    target_entity_id: str | None = None
    summary: str | None = None
    undone: bool | None = None
    lifecycle_state: str | None = None
    observation_count: int | None = None
    lifecycle_event_count: int | None = None
    created_at: str | None = None
    answered_at: str | None = None
    updated_at: str | None = None


class EvaluationDatasetResponse(BaseModel):
    schema_version: str
    examples: list[EvaluationDatasetExample] = Field(default_factory=list)
    example_count: int = 0
    redaction: dict[str, str] = Field(default_factory=dict)


class ProviderScorecardProviderItem(BaseModel):
    provider_id: str
    display_name: str | None = None
    mode: str | None = None
    status: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    cost_model: str | None = None
    images_leave_device: bool = False
    privacy_notes: str | None = None
    selected_for: list[str] = Field(default_factory=list)


class ProviderScorecardResponse(BaseModel):
    schema_version: str
    provider_selections: dict[str, str] = Field(default_factory=dict)
    providers: list[ProviderScorecardProviderItem] = Field(default_factory=list)
    metrics: dict[str, object] = Field(default_factory=dict)
    benchmark_guidance: list[str] = Field(default_factory=list)


class BenchmarkCaseItem(BaseModel):
    case_id: str
    domain_type: str
    task: str
    description: str
    expected_signals: list[str] = Field(default_factory=list)
    privacy_level: str = "synthetic_metadata_only"


class BenchmarkPackResponse(BaseModel):
    schema_version: str
    name: str
    description: str
    cases: list[BenchmarkCaseItem] = Field(default_factory=list)
    case_count: int = 0
    redaction: dict[str, str] = Field(default_factory=dict)
    usage: list[str] = Field(default_factory=list)


class ConfidenceLedgerEntryItem(BaseModel):
    entry_id: str
    source: str
    event_type: str
    confidence_before: float | None = None
    confidence_after: float | None = None
    delta: float = 0.0
    reason: str
    created_at: str


class ConfidenceLedgerResponse(BaseModel):
    entity_id: str
    label: str
    current_confidence: float
    entries: list[ConfidenceLedgerEntryItem] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)


class MemoryEntityDetailResponse(BaseModel):
    entity: MemoryEntityItem
    confidence_ledger: ConfidenceLedgerResponse
    active_learning_questions: list["ActiveLearningQuestionItem"] = Field(default_factory=list)
    corrections: list[CorrectionLogItem] = Field(default_factory=list)
    evidence_bundles: list[MemoryEvidenceBundleItem] = Field(default_factory=list)
    health: MemoryHealthItem | None = None
    related_conflicts: list[dict[str, object]] = Field(default_factory=list)
    replay_suggestions: list[LearningReplaySuggestionItem] = Field(default_factory=list)
    learning_timeline: list[LearningTimelineItem] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)


class BenchmarkRunCreateRequest(BaseModel):
    label: str = Field(default="", max_length=200)
    notes: str | None = None
    benchmark_case_ids: list[str] = Field(default_factory=list)


class BenchmarkRunItem(BaseModel):
    run_id: str
    label: str
    notes: str | None = None
    benchmark_case_ids: list[str] = Field(default_factory=list)
    provider_selections: dict[str, str] = Field(default_factory=dict)
    metrics: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class BenchmarkRunListResponse(BaseModel):
    runs: list[BenchmarkRunItem] = Field(default_factory=list)
    run_count: int = 0


class MemoryEntityListResponse(BaseModel):
    entities: list[MemoryEntityItem]


class MemoryDomainItem(BaseModel):
    domain_type: str
    entity_count: int = 0
    built_in: bool = False


class MemoryDomainListResponse(BaseModel):
    domains: list[MemoryDomainItem]


class ActiveLearningResponseItem(BaseModel):
    action: str
    label: str | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    answered_at: datetime


class ActiveLearningQuestionItem(BaseModel):
    question_id: str
    question_type: str
    prompt: str
    domain_type: str = "person"
    status: str = "pending"
    priority: int = 50
    priority_reason: str = ""
    confidence: float = 0.0
    source_signal_ids: list[str] = Field(default_factory=list)
    learning_value: float = 0.0
    risk_level: str = "medium"
    cooldown_until: str | None = None
    suggested_action: str = ""
    memory_run_id: str | None = None
    upload_id: str | None = None
    selected_face_index: int | None = None
    candidate_label: str | None = None
    candidate_reference_id: str | None = None
    unknown_cluster_id: str | None = None
    context: dict[str, object] = Field(default_factory=dict)
    response: ActiveLearningResponseItem | None = None
    created_at: datetime
    updated_at: datetime


class ActiveLearningQuestionListResponse(BaseModel):
    questions: list[ActiveLearningQuestionItem]
    pending_count: int = 0


class ActiveLearningQuestionResponseRequest(BaseModel):
    action: Literal["confirm", "reject", "dismiss", "label", "skip"]
    label: str | None = Field(default=None, max_length=200)
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)


class ActiveLearningQuestionResponse(BaseModel):
    question: ActiveLearningQuestionItem
    applied: bool = False
    result: dict[str, object] = Field(default_factory=dict)


class MemoryRunRequest(BaseModel):
    upload_id: UUID
    selected_face_index: int = Field(ge=0)
    notes: str | None = None


class UploadRecognitionResult(BaseModel):
    selected_face_index: int
    status: Literal["matched", "tentative", "unknown"]
    confidence: float = 0.0
    reference_id: str | None = None
    top_candidate_name: str | None = None
    top_candidate_provider: str | None = None
    memory_summary: str | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    seen_count: int | None = None
    last_seen_at: datetime | None = None
    unknown_sample_id: str | None = None
    unknown_sample_stored: bool = False
    unknown_cluster_id: str | None = None
    unknown_cluster_sighting_count: int = 0
    unknown_cluster_suggested_for_enrollment: bool = False
    quality_score: float | None = None
    reason: str = ""
    embedding_dimensions: int = 0
    candidate_count: int = 0


class MemoryRunCreateResponse(BaseModel):
    memory_run_id: UUID
    recognition_result: UploadRecognitionResult | None = None


class ActivityEntry(BaseModel):
    stage: str
    message: str
    created_at: datetime


class MemoryRunResponse(BaseModel):
    id: UUID
    status: MemoryRunStatus
    memory_report: MemoryReport | None = None
    activities: list[ActivityEntry]


class MemoryRunHistoryItem(BaseModel):
    memory_run_id: UUID
    status: MemoryRunStatus
    created_at: datetime
    last_updated: datetime | None = None


class MemoryRunHistoryResponse(BaseModel):
    memory_runs: list[MemoryRunHistoryItem]


class HealthResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    dependencies: dict[str, bool]
    optional_features: dict[str, object] = Field(default_factory=dict)
    diagnostics: dict[str, object] = Field(default_factory=dict)
