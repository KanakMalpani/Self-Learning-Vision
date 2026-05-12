from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

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
    face_boxes: List[FaceBox]


class FaceReferenceEnrollRequest(BaseModel):
    name_or_alias: str = Field(min_length=1, max_length=200)
    notes: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    selected_face_index: int = Field(default=0, ge=0)
    unknown_cluster_id: Optional[str] = None


class FaceReferenceItem(BaseModel):
    reference_id: str
    name_or_alias: str
    provider: str
    source_image_path: Optional[str] = None
    face_index: int = 0
    notes: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    seen_count: int = 0
    last_seen_at: Optional[datetime] = None
    created_at: datetime


class FaceReferenceEnrollResponse(BaseModel):
    reference: FaceReferenceItem
    total_references: int = 0
    embedding_dimensions: int = 0


class MemoryObservationItem(BaseModel):
    observation_id: str
    source: str
    source_id: Optional[str] = None
    modality: str = "vision"
    confidence: Optional[float] = None
    notes: Optional[str] = None
    observed_at: datetime


class MemoryLifecycleEventItem(BaseModel):
    event_id: str
    event_type: str
    from_state: str
    to_state: str
    confidence_before: float
    confidence_after: float
    reason: Optional[str] = None
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
    notes: Optional[str] = None
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
    notes: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    lifecycle_state: str = "candidate"


class MemoryEntityUpdateRequest(BaseModel):
    attributes: Optional[dict[str, object]] = None
    user_schema: Optional[dict[str, object]] = None
    aliases: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    notes: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    lifecycle_state: Optional[str] = None


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
    notes: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    lifecycle_state: Optional[str] = None


class MemoryEntityCorrectionRequest(BaseModel):
    notes: Optional[str] = None


class MemoryEntityRenameRequest(MemoryEntityCorrectionRequest):
    label: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list)


class MemoryEntityForgetRequest(MemoryEntityCorrectionRequest):
    mode: Literal["archived", "forgotten"] = "archived"


class MemoryEntityNotThisRequest(MemoryEntityCorrectionRequest):
    rejected_label: Optional[str] = Field(default=None, max_length=200)


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
    undone_at: Optional[datetime] = None
    created_at: datetime


class CorrectionListResponse(BaseModel):
    corrections: list[CorrectionLogItem]


class CorrectionResponse(BaseModel):
    correction: CorrectionLogItem
    entity: Optional[MemoryEntityItem] = None
    related_entities: list[MemoryEntityItem] = Field(default_factory=list)


class MemoryLifecycleReinforceRequest(BaseModel):
    amount: float = Field(default=0.05, ge=0.0, le=1.0)
    reason: Optional[str] = None


class MemoryLifecycleContradictionRequest(BaseModel):
    rejected_label: Optional[str] = Field(default=None, max_length=200)
    amount: float = Field(default=0.15, ge=0.0, le=1.0)
    reason: Optional[str] = None


class MemoryLifecycleDecayRequest(BaseModel):
    stale_after_days: int = Field(default=30, ge=1, le=3650)
    amount: float = Field(default=0.05, ge=0.0, le=1.0)


class MemoryLifecycleOperationResponse(BaseModel):
    entity: Optional[MemoryEntityItem] = None
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
    entity_id: Optional[str] = None
    question_id: Optional[str] = None
    source_id: Optional[str] = None
    status: str = "pending"
    confidence: float = 0.0
    learning_value: float = 0.0
    risk_level: str = "medium"
    evidence: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    resolution: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None


class LearningSignalListResponse(BaseModel):
    signals: list[LearningSignalItem] = Field(default_factory=list)
    signal_count: int = 0
    pending_count: int = 0


class LearningSignalDismissRequest(BaseModel):
    reason: Optional[str] = None


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
    confidence: Optional[float] = None
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
    data_retention_days: Optional[int] = None
    domain_visibility: dict[str, str] = Field(default_factory=dict)
    updated_at: datetime


class PrivacySettingsUpdateRequest(BaseModel):
    local_only_mode: Optional[bool] = None
    allow_hosted_providers: Optional[bool] = None
    export_include_biometric_embeddings: Optional[bool] = None
    export_include_upload_paths: Optional[bool] = None
    data_retention_days: Optional[int] = Field(default=None, ge=1, le=3650)
    domain_visibility: Optional[dict[str, str]] = None


class VaultExportRequest(BaseModel):
    encrypt: bool = False
    passphrase: Optional[str] = Field(default=None, min_length=8)


class VaultImportRequest(BaseModel):
    vault: dict[str, object] = Field(default_factory=dict)
    passphrase: Optional[str] = Field(default=None, min_length=8)
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
    expected_dimensions: Optional[int] = None
    latency_profile: str = "unknown"
    cost_model: str = "free"
    setup: str = ""
    privacy_notes: str = ""
    entrypoint: Optional[str] = None
    manifest_path: Optional[str] = None
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


class EvaluationMetricsResponse(BaseModel):
    memory_runs: int = 0
    recognition_decisions: dict[str, int] = Field(default_factory=dict)
    average_recognition_confidence: Optional[float] = None
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
    estimated_precision: Optional[float] = None
    estimated_recall: Optional[float] = None
    memory_growth_per_run: float = 0.0
    notes: list[str] = Field(default_factory=list)


class EvaluationDatasetExample(BaseModel):
    example_id: str
    source: str
    task: str
    domain_type: Optional[str] = None
    status: Optional[str] = None
    action: Optional[str] = None
    label: Optional[str] = None
    candidate_label: Optional[str] = None
    memory_run_id: Optional[str] = None
    upload_id: Optional[str] = None
    selected_face_index: Optional[int] = None
    unknown_cluster_id: Optional[str] = None
    confidence: Optional[float] = None
    target_entity_id: Optional[str] = None
    summary: Optional[str] = None
    undone: Optional[bool] = None
    lifecycle_state: Optional[str] = None
    observation_count: Optional[int] = None
    lifecycle_event_count: Optional[int] = None
    created_at: Optional[str] = None
    answered_at: Optional[str] = None
    updated_at: Optional[str] = None


class EvaluationDatasetResponse(BaseModel):
    schema_version: str
    examples: list[EvaluationDatasetExample] = Field(default_factory=list)
    example_count: int = 0
    redaction: dict[str, str] = Field(default_factory=dict)


class ProviderScorecardProviderItem(BaseModel):
    provider_id: str
    display_name: Optional[str] = None
    mode: Optional[str] = None
    status: Optional[str] = None
    capabilities: list[str] = Field(default_factory=list)
    cost_model: Optional[str] = None
    images_leave_device: bool = False
    privacy_notes: Optional[str] = None
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
    confidence_before: Optional[float] = None
    confidence_after: Optional[float] = None
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
    health: Optional[MemoryHealthItem] = None
    related_conflicts: list[dict[str, object]] = Field(default_factory=list)
    replay_suggestions: list[LearningReplaySuggestionItem] = Field(default_factory=list)
    learning_timeline: list[LearningTimelineItem] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)


class BenchmarkRunCreateRequest(BaseModel):
    label: str = Field(default="", max_length=200)
    notes: Optional[str] = None
    benchmark_case_ids: list[str] = Field(default_factory=list)


class BenchmarkRunItem(BaseModel):
    run_id: str
    label: str
    notes: Optional[str] = None
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
    label: Optional[str] = None
    notes: Optional[str] = None
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
    cooldown_until: Optional[str] = None
    suggested_action: str = ""
    memory_run_id: Optional[str] = None
    upload_id: Optional[str] = None
    selected_face_index: Optional[int] = None
    candidate_label: Optional[str] = None
    candidate_reference_id: Optional[str] = None
    unknown_cluster_id: Optional[str] = None
    context: dict[str, object] = Field(default_factory=dict)
    response: Optional[ActiveLearningResponseItem] = None
    created_at: datetime
    updated_at: datetime


class ActiveLearningQuestionListResponse(BaseModel):
    questions: list[ActiveLearningQuestionItem]
    pending_count: int = 0


class ActiveLearningQuestionResponseRequest(BaseModel):
    action: Literal["confirm", "reject", "dismiss", "label", "skip"]
    label: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class ActiveLearningQuestionResponse(BaseModel):
    question: ActiveLearningQuestionItem
    applied: bool = False
    result: dict[str, object] = Field(default_factory=dict)


class MemoryRunRequest(BaseModel):
    upload_id: UUID
    selected_face_index: int = Field(ge=0)
    notes: Optional[str] = None


class UploadRecognitionResult(BaseModel):
    selected_face_index: int
    status: Literal["matched", "tentative", "unknown"]
    confidence: float = 0.0
    reference_id: Optional[str] = None
    top_candidate_name: Optional[str] = None
    top_candidate_provider: Optional[str] = None
    memory_summary: Optional[str] = None
    notes: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    seen_count: Optional[int] = None
    last_seen_at: Optional[datetime] = None
    unknown_sample_id: Optional[str] = None
    unknown_sample_stored: bool = False
    unknown_cluster_id: Optional[str] = None
    unknown_cluster_sighting_count: int = 0
    unknown_cluster_suggested_for_enrollment: bool = False
    quality_score: Optional[float] = None
    reason: str = ""
    embedding_dimensions: int = 0
    candidate_count: int = 0


class MemoryRunCreateResponse(BaseModel):
    memory_run_id: UUID
    recognition_result: Optional[UploadRecognitionResult] = None


class ActivityEntry(BaseModel):
    stage: str
    message: str
    created_at: datetime


class MemoryRunResponse(BaseModel):
    id: UUID
    status: MemoryRunStatus
    memory_report: Optional[MemoryReport] = None
    activities: List[ActivityEntry]


class MemoryRunHistoryItem(BaseModel):
    memory_run_id: UUID
    status: MemoryRunStatus
    created_at: datetime
    last_updated: Optional[datetime] = None


class MemoryRunHistoryResponse(BaseModel):
    memory_runs: List[MemoryRunHistoryItem]


class HealthResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    dependencies: dict[str, bool]
