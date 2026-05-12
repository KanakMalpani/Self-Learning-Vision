export type FaceBox = {
  x: number;
  y: number;
  width: number;
  height: number;
  score: number;
};

export type Fact = {
  title: string;
  detail: string;
  confidence?: number;
  citations?: string[];
  support_count?: number;
  tentative?: boolean;
};

export type TimelineEvent = {
  title: string;
  date: string;
  description: string;
  confidence?: number;
  citations?: string[];
  support_count?: number;
  tentative?: boolean;
};

export type MemoryReportConfidence = {
  overall: number;
  photo?: number;
  per_claim?: Record<string, number>;
};

export type FaceAssessment = {
  face_index: number;
  detector_confidence: number;
  blur_score: number;
  box_size_ratio: number;
  pose_score: number;
  occlusion_score: number;
  face_quality_score: number;
  face_quality_flags: string[];
};

export type IdentityCandidate = {
  name_or_alias: string;
  provider: string;
  raw_confidence: number;
  calibrated_confidence: number;
  match_reason: string;
  profile_url?: string;
  recognition_score: number;
  recognition_decision: "accepted" | "tentative" | "rejected";
};

export type MemoryAnalytics = {
  frequency?: {
    raw_reference_count?: number;
    total_references?: number;
    raw_seen_count?: number;
    total_seen_count?: number;
    average_seen_count?: number;
    top_referenced_identities?: Array<{
      name_or_alias: string;
      seen_count: number;
      tags: string[];
      last_seen_at?: string | null;
      variant_count?: number;
    }>;
  };
  tags?: {
    unique_tags?: string[];
    tag_counts?: Array<{ tag: string; count: number }>;
    top_tag_pairs?: Array<{ tags: string[]; count: number }>;
  };
  temporal?: {
    seen_today_count?: number;
    seen_7d_count?: number;
    seen_30d_count?: number;
    never_seen_count?: number;
    future_seen_count?: number;
    oldest_last_seen_at?: string | null;
    newest_last_seen_at?: string | null;
    active_identity_count?: number;
  };
};

export type MemoryReport = {
  subject: {
    name_or_alias: string;
    possible_profiles: string[];
  };
  executive_summary: string;
  key_facts: Fact[];
  timeline: TimelineEvent[];
  profile_links: string[];
  confidence: MemoryReportConfidence;
  source_notes: string[];
  caveats: string[];
  face_assessments?: FaceAssessment[];
  identity_candidates?: IdentityCandidate[];
  recognition_summary?: Record<string, unknown>;
  decision_trace?: Record<string, unknown>;
  identity_explanation?: string[];
  memory_analytics?: MemoryAnalytics;
  recognition_source?: string | null;
  generated_at: string;
};

export type MemoryRunStatus = "queued" | "detecting" | "matching" | "synthesizing" | "done" | "failed";

export type ActivityEntry = {
  stage: string;
  message: string;
  created_at: string;
};

export type UploadResponse = {
  upload_id: string;
  face_boxes: FaceBox[];
};

export type UploadRecognitionResult = {
  selected_face_index: number;
  status: "matched" | "tentative" | "unknown";
  confidence: number;
  reference_id?: string | null;
  top_candidate_name?: string | null;
  top_candidate_provider?: string | null;
  memory_summary?: string | null;
  notes?: string | null;
  tags: string[];
  seen_count?: number | null;
  last_seen_at?: string | null;
  unknown_sample_id?: string | null;
  unknown_sample_stored: boolean;
  unknown_cluster_id?: string | null;
  unknown_cluster_sighting_count: number;
  unknown_cluster_suggested_for_enrollment: boolean;
  quality_score?: number | null;
  reason: string;
  embedding_dimensions: number;
  candidate_count: number;
};

export type MemoryRunResponse = {
  id: string;
  status: MemoryRunStatus;
  memory_report?: MemoryReport | null;
  activities: ActivityEntry[];
};

export type MemoryRunCreateResponse = {
  memory_run_id: string;
  recognition_result?: UploadRecognitionResult | null;
};

export type MemoryRunHistoryItem = {
  memory_run_id: string;
  status: MemoryRunStatus;
  created_at: string;
  last_updated?: string | null;
};

export type MemoryRunHistoryResponse = {
  memory_runs: MemoryRunHistoryItem[];
};

export type FaceReferenceEnrollRequest = {
  name_or_alias: string;
  notes?: string | null;
  tags?: string[];
  selected_face_index?: number;
  unknown_cluster_id?: string | null;
};

export type FaceReferenceItem = {
  reference_id: string;
  name_or_alias: string;
  provider: string;
  source_image_path?: string | null;
  face_index: number;
  notes?: string | null;
  tags?: string[];
  seen_count?: number;
  last_seen_at?: string | null;
  created_at: string;
};

export type FaceReferenceEnrollResponse = {
  reference: FaceReferenceItem;
  total_references: number;
  embedding_dimensions: number;
};

export type MemoryObservationItem = {
  observation_id: string;
  source: string;
  source_id?: string | null;
  modality: string;
  confidence?: number | null;
  notes?: string | null;
  observed_at: string;
};

export type MemoryLifecycleEventItem = {
  event_id: string;
  event_type: string;
  from_state: string;
  to_state: string;
  confidence_before: number;
  confidence_after: number;
  reason?: string | null;
  created_at: string;
};

export type MemoryEntityItem = {
  entity_id: string;
  domain_type: string;
  label: string;
  attributes: Record<string, unknown>;
  schema_version: string;
  user_schema: Record<string, unknown>;
  aliases: string[];
  tags: string[];
  notes?: string | null;
  confidence: number;
  lifecycle_state: string;
  observations: MemoryObservationItem[];
  lifecycle_events: MemoryLifecycleEventItem[];
  source_reference_ids: string[];
  created_at: string;
  updated_at: string;
};

export type MemoryEntityCreateRequest = {
  domain_type: string;
  label: string;
  attributes?: Record<string, unknown>;
  user_schema?: Record<string, unknown>;
  aliases?: string[];
  tags?: string[];
  notes?: string | null;
  confidence?: number;
  lifecycle_state?: string;
};

export type MemoryEntityUpdateRequest = {
  attributes?: Record<string, unknown> | null;
  user_schema?: Record<string, unknown> | null;
  aliases?: string[] | null;
  tags?: string[] | null;
  notes?: string | null;
  confidence?: number | null;
  lifecycle_state?: string | null;
};

export type MemoryEntityCreateResponse = {
  entity: MemoryEntityItem;
  total_entities: number;
};

export type MemorySearchResultItem = {
  entity_id: string;
  domain_type: string;
  label: string;
  lifecycle_state: string;
  confidence: number;
  score: number;
  matched_fields: string[];
  tags: string[];
};

export type MemorySearchResponse = {
  query: string;
  results: MemorySearchResultItem[];
  result_count: number;
  total_candidates: number;
};

export type MemoryDomainTemplateItem = {
  template_id: string;
  domain_type: string;
  display_name: string;
  description: string;
  fields: Record<string, string>;
  default_attributes: Record<string, unknown>;
  recommended_tags: string[];
  observation_modality: string;
  lifecycle_state: string;
  confidence: number;
  prompts: string[];
};

export type MemoryDomainTemplateListResponse = {
  templates: MemoryDomainTemplateItem[];
};

export type MemoryEntityCreateFromTemplateRequest = {
  label: string;
  attributes?: Record<string, unknown>;
  aliases?: string[];
  tags?: string[];
  notes?: string | null;
  confidence?: number | null;
  lifecycle_state?: string | null;
};

export type MemoryEntityRenameRequest = {
  label: string;
  aliases?: string[];
  notes?: string | null;
};

export type MemoryEntityForgetRequest = {
  mode?: "archived" | "forgotten";
  notes?: string | null;
};

export type MemoryEntityNotThisRequest = {
  rejected_label?: string | null;
  notes?: string | null;
};

export type MemoryEntityMergeRequest = {
  source_entity_ids: string[];
  notes?: string | null;
};

export type MemoryEntitySplitRequest = {
  new_label: string;
  observation_ids: string[];
  notes?: string | null;
};

export type CorrectionLogItem = {
  correction_id: string;
  operation_type: string;
  target_entity_id: string;
  summary: string;
  metadata: Record<string, unknown>;
  undone: boolean;
  undone_at?: string | null;
  created_at: string;
};

export type CorrectionListResponse = {
  corrections: CorrectionLogItem[];
};

export type CorrectionResponse = {
  correction: CorrectionLogItem;
  entity?: MemoryEntityItem | null;
  related_entities: MemoryEntityItem[];
};

export type MemoryLifecycleReinforceRequest = {
  amount?: number;
  reason?: string | null;
};

export type MemoryLifecycleContradictionRequest = {
  rejected_label?: string | null;
  amount?: number;
  reason?: string | null;
};

export type MemoryLifecycleDecayRequest = {
  stale_after_days?: number;
  amount?: number;
};

export type MemoryLifecycleSummaryResponse = {
  total_entities: number;
  by_state: Record<string, number>;
  by_domain: Record<string, number>;
  average_confidence: number;
  contradictions: number;
  lifecycle_events: number;
};

export type MemoryLifecycleOperationResponse = {
  entity?: MemoryEntityItem | null;
  affected_entities: MemoryEntityItem[];
  summary: Record<string, unknown>;
};

export type PrivacySettingsItem = {
  local_only_mode: boolean;
  allow_hosted_providers: boolean;
  export_include_biometric_embeddings: boolean;
  export_include_upload_paths: boolean;
  data_retention_days?: number | null;
  domain_visibility: Record<string, string>;
  updated_at: string;
};

export type PrivacySettingsUpdateRequest = {
  local_only_mode?: boolean;
  allow_hosted_providers?: boolean;
  export_include_biometric_embeddings?: boolean;
  export_include_upload_paths?: boolean;
  data_retention_days?: number | null;
  domain_visibility?: Record<string, string>;
};

export type VaultExportRequest = {
  encrypt?: boolean;
  passphrase?: string | null;
};

export type VaultImportRequest = {
  vault: Record<string, unknown>;
  passphrase?: string | null;
  replace_memory_entities?: boolean;
};

export type VaultImportResponse = {
  imported_entities: number;
  encrypted: boolean;
  format: string;
};

export type ProviderCardItem = {
  provider_id: string;
  display_name: string;
  mode: string;
  capabilities: string[];
  status: string;
  images_leave_device: boolean;
  embeddings_stored_locally: boolean;
  enabled_by_default: boolean;
  recommended_for: string[];
  env_vars: string[];
  expected_dimensions?: number | null;
  latency_profile: string;
  cost_model: string;
  setup: string;
  privacy_notes: string;
  entrypoint?: string | null;
  manifest_path?: string | null;
  plugin_source: string;
};

export type ProviderMarketplaceResponse = {
  providers: ProviderCardItem[];
  capabilities: string[];
  selections: Record<string, string>;
};

export type ProviderSelectionRequest = {
  capability: string;
  provider_id: string;
};

export type ProviderSelectionResponse = {
  selections: Record<string, string>;
  updated_at: string;
  provider: ProviderCardItem;
};

export type ProviderPluginListResponse = {
  plugins: ProviderCardItem[];
  manifest_dirs: string[];
};

export type ProviderConformanceCheckItem = {
  check_id: string;
  label: string;
  passed: boolean;
  severity: string;
  detail: string;
};

export type ProviderConformanceReportItem = {
  provider_id: string;
  display_name: string;
  passed: boolean;
  checks: ProviderConformanceCheckItem[];
  summary: Record<string, number>;
};

export type ProviderConformanceListResponse = {
  providers: ProviderConformanceReportItem[];
  provider_count: number;
  passing_count: number;
};

export type EvaluationMetricsResponse = {
  memory_runs: number;
  recognition_decisions: Record<string, number>;
  average_recognition_confidence?: number | null;
  active_learning_questions: number;
  active_learning_pending: number;
  active_learning_answered: number;
  active_learning_actions: Record<string, number>;
  corrections: number;
  corrections_by_type: Record<string, number>;
  memory_entities: number;
  memory_lifecycle: Record<string, unknown>;
  passive_signal_count: number;
  auto_reinforcement_count: number;
  review_inbox_pending_count: number;
  contradiction_rate: number;
  memory_health_distribution: Record<string, number>;
  replay_applied_count: number;
  false_match_signals: number;
  missed_match_signals: number;
  uncertainty_rate: number;
  correction_rate: number;
  active_learning_completion_rate: number;
  estimated_precision?: number | null;
  estimated_recall?: number | null;
  memory_growth_per_run: number;
  notes: string[];
};

export type EvaluationDatasetExample = {
  example_id: string;
  source: string;
  task: string;
  domain_type?: string | null;
  status?: string | null;
  action?: string | null;
  label?: string | null;
  candidate_label?: string | null;
  memory_run_id?: string | null;
  upload_id?: string | null;
  selected_face_index?: number | null;
  unknown_cluster_id?: string | null;
  confidence?: number | null;
  target_entity_id?: string | null;
  summary?: string | null;
  undone?: boolean | null;
  lifecycle_state?: string | null;
  observation_count?: number | null;
  lifecycle_event_count?: number | null;
  created_at?: string | null;
  answered_at?: string | null;
  updated_at?: string | null;
};

export type EvaluationDatasetResponse = {
  schema_version: string;
  examples: EvaluationDatasetExample[];
  example_count: number;
  redaction: Record<string, string>;
};

export type ProviderScorecardProviderItem = {
  provider_id: string;
  display_name?: string | null;
  mode?: string | null;
  status?: string | null;
  capabilities: string[];
  cost_model?: string | null;
  images_leave_device: boolean;
  privacy_notes?: string | null;
  selected_for: string[];
};

export type ProviderScorecardResponse = {
  schema_version: string;
  provider_selections: Record<string, string>;
  providers: ProviderScorecardProviderItem[];
  metrics: Record<string, unknown>;
  benchmark_guidance: string[];
};

export type BenchmarkCaseItem = {
  case_id: string;
  domain_type: string;
  task: string;
  description: string;
  expected_signals: string[];
  privacy_level: string;
};

export type BenchmarkPackResponse = {
  schema_version: string;
  name: string;
  description: string;
  cases: BenchmarkCaseItem[];
  case_count: number;
  redaction: Record<string, string>;
  usage: string[];
};

export type ConfidenceLedgerEntryItem = {
  entry_id: string;
  source: string;
  event_type: string;
  confidence_before?: number | null;
  confidence_after?: number | null;
  delta: number;
  reason: string;
  created_at: string;
};

export type ConfidenceLedgerResponse = {
  entity_id: string;
  label: string;
  current_confidence: number;
  entries: ConfidenceLedgerEntryItem[];
  summary: Record<string, number>;
};

export type LearningSignalItem = {
  signal_id: string;
  signal_type: string;
  source: string;
  summary: string;
  domain_type: string;
  entity_id?: string | null;
  question_id?: string | null;
  source_id?: string | null;
  status: string;
  confidence: number;
  learning_value: number;
  risk_level: string;
  evidence: string[];
  metadata: Record<string, unknown>;
  resolution?: string | null;
  created_at: string;
  updated_at: string;
  resolved_at?: string | null;
};

export type LearningSignalListResponse = {
  signals: LearningSignalItem[];
  signal_count: number;
  pending_count: number;
};

export type LearningSignalDismissRequest = {
  reason?: string | null;
};

export type MemoryHealthItem = {
  entity_id: string;
  score: number;
  state: string;
  reasons: string[];
  confidence: number;
  observation_count: number;
  evidence_count: number;
  contradiction_count: number;
  correction_count: number;
  pending_question_count: number;
  last_updated_at: string;
};

export type MemoryEvidenceBundleItem = {
  bundle_id: string;
  title: string;
  summary: string;
  source: string;
  event_count: number;
  confidence_delta: number;
  risk_level: string;
  created_at: string;
  items: Record<string, unknown>[];
};

export type LearningReplaySuggestionItem = {
  suggestion_id: string;
  title: string;
  summary: string;
  action: string;
  risk_level: string;
  source_signal_ids: string[];
};

export type LearningTimelineItem = {
  timeline_id: string;
  event_type: string;
  title: string;
  summary: string;
  source: string;
  confidence?: number | null;
  created_at: string;
};

export type LearningPolicyItem = {
  preset: string;
  auto_reinforcement_enabled: boolean;
  high_confidence_threshold: number;
  min_reinforcement_signals: number;
  max_reinforcement_amount: number;
  review_budget_per_session: number;
  updated_at: string;
};

export type LearningPolicyUpdateRequest = {
  preset: "conservative" | "balanced" | "experimental";
};

export type LearningPolicySimulationResponse = {
  preset: string;
  auto_reinforcement_enabled: boolean;
  auto_reinforce_count: number;
  needs_review_count: number;
  blocked_count: number;
  review_budget_per_session: number;
  auto_reinforce: Record<string, unknown>[];
  needs_review: Record<string, unknown>[];
  blocked: Record<string, unknown>[];
};

export type MemoryEntityDetailResponse = {
  entity: MemoryEntityItem;
  confidence_ledger: ConfidenceLedgerResponse;
  active_learning_questions: ActiveLearningQuestionItem[];
  corrections: CorrectionLogItem[];
  evidence_bundles: MemoryEvidenceBundleItem[];
  health?: MemoryHealthItem | null;
  related_conflicts: Record<string, unknown>[];
  replay_suggestions: LearningReplaySuggestionItem[];
  learning_timeline: LearningTimelineItem[];
  summary: Record<string, number>;
};

export type LearningReviewMemoryItem = {
  entity: MemoryEntityItem;
  health: MemoryHealthItem;
};

export type LearningReviewInboxResponse = {
  questions: ActiveLearningQuestionItem[];
  contradictions: LearningSignalItem[];
  candidate_memories: LearningReviewMemoryItem[];
  low_health_memories: LearningReviewMemoryItem[];
  replay_suggestions: LearningReplaySuggestionItem[];
  signals: LearningSignalItem[];
  summary: Record<string, number>;
};

export type LearningReplayResponse = {
  applied: boolean;
  entity?: MemoryEntityItem | null;
  affected_signal_ids: string[];
  queued_question_ids: string[];
  suggestions: LearningReplaySuggestionItem[];
  summary: Record<string, unknown>;
};

export type BenchmarkRunCreateRequest = {
  label?: string;
  notes?: string | null;
  benchmark_case_ids?: string[];
};

export type BenchmarkRunItem = {
  run_id: string;
  label: string;
  notes?: string | null;
  benchmark_case_ids: string[];
  provider_selections: Record<string, string>;
  metrics: Record<string, unknown>;
  created_at: string;
};

export type BenchmarkRunListResponse = {
  runs: BenchmarkRunItem[];
  run_count: number;
};

export type MemoryEntityListResponse = {
  entities: MemoryEntityItem[];
};

export type MemoryDomainItem = {
  domain_type: string;
  entity_count: number;
  built_in: boolean;
};

export type MemoryDomainListResponse = {
  domains: MemoryDomainItem[];
};

export type ActiveLearningResponseItem = {
  action: string;
  label?: string | null;
  notes?: string | null;
  tags: string[];
  answered_at: string;
};

export type ActiveLearningQuestionItem = {
  question_id: string;
  question_type: string;
  prompt: string;
  domain_type: string;
  status: string;
  priority: number;
  priority_reason: string;
  confidence: number;
  source_signal_ids: string[];
  learning_value: number;
  risk_level: string;
  cooldown_until?: string | null;
  suggested_action: string;
  memory_run_id?: string | null;
  upload_id?: string | null;
  selected_face_index?: number | null;
  candidate_label?: string | null;
  candidate_reference_id?: string | null;
  unknown_cluster_id?: string | null;
  context: Record<string, unknown>;
  response?: ActiveLearningResponseItem | null;
  created_at: string;
  updated_at: string;
};

export type ActiveLearningQuestionListResponse = {
  questions: ActiveLearningQuestionItem[];
  pending_count: number;
};

export type ActiveLearningQuestionResponseRequest = {
  action: "confirm" | "reject" | "dismiss" | "label" | "skip";
  label?: string | null;
  notes?: string | null;
  tags?: string[];
};

export type ActiveLearningQuestionResponse = {
  question: ActiveLearningQuestionItem;
  applied: boolean;
  result: Record<string, unknown>;
};

export type MemoryRunRealtimeEventType =
  | "detection_complete"
  | "recognition_strategy_used"
  | "synthesis_started"
  | "synthesis_completed"
  | "memory_run_status"
  | "ping";

export type MemoryRunRealtimeEventPayload = {
  timestamp?: string;
  memory_run_id?: string | null;
  session_id?: string | null;
  payload?: Record<string, unknown>;
};
