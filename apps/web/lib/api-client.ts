import type {
  ActiveLearningQuestionListResponse,
  ActiveLearningQuestionResponse,
  ActiveLearningQuestionResponseRequest,
  BenchmarkPackResponse,
  BenchmarkRunCreateRequest,
  BenchmarkRunItem,
  BenchmarkRunListResponse,
  ConfidenceLedgerResponse,
  CorrectionListResponse,
  CorrectionResponse,
  EvaluationDatasetResponse,
  EvaluationMetricsResponse,
  FaceReferenceEnrollRequest,
  FaceReferenceEnrollResponse,
  LearningPolicyItem,
  LearningPolicySimulationResponse,
  LearningPolicyUpdateRequest,
  LearningReplayResponse,
  LearningReviewInboxResponse,
  LearningSignalDismissRequest,
  LearningSignalItem,
  LearningSignalListResponse,
  MemoryDomainListResponse,
  MemoryDomainTemplateItem,
  MemoryDomainTemplateListResponse,
  MemoryEntityCreateRequest,
  MemoryEntityCreateFromTemplateRequest,
  MemoryEntityCreateResponse,
  MemoryEntityDetailResponse,
  MemoryEntityForgetRequest,
  MemoryEntityListResponse,
  MemoryEntityMergeRequest,
  MemoryEntityNotThisRequest,
  MemoryEntityRenameRequest,
  MemoryEntitySplitRequest,
  MemoryEntityUpdateRequest,
  MemoryLifecycleContradictionRequest,
  MemoryLifecycleDecayRequest,
  MemoryLifecycleOperationResponse,
  MemoryLifecycleReinforceRequest,
  MemoryLifecycleSummaryResponse,
  MemoryRunCreateResponse,
  MemoryRunHistoryResponse,
  MemoryRunResponse,
  MemoryRunStatus,
  MemorySearchResponse,
  PrivacySettingsItem,
  PrivacySettingsUpdateRequest,
  ReadinessResponse,
  ProviderMarketplaceResponse,
  ProviderConformanceListResponse,
  ProviderPluginListResponse,
  ProviderScorecardResponse,
  ProviderSelectionRequest,
  ProviderSelectionResponse,
  UploadResponse,
  VaultExportRequest,
  VaultImportRequest,
  VaultImportResponse,
} from "@/types/memory";
import { clearToken, getToken } from "./auth";
import { getRuntimeConfig } from "./runtime-config";

const AUTH_ENABLED = process.env.NEXT_PUBLIC_AUTH_ENABLED === "true";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public details?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const runtime = await getRuntimeConfig();
  const token = AUTH_ENABLED ? getToken() : null;
  const headers: HeadersInit = token
    ? { ...options?.headers, Authorization: `Bearer ${token}` }
    : options?.headers || {};

  try {
    const response = await fetch(`${runtime.apiBaseUrl}${endpoint}`, { ...options, headers });

    if (response.status === 401) {
      if (AUTH_ENABLED) {
        clearToken();
        throw new ApiError("Session expired. Please log in again.", 401);
      }
      throw new ApiError("Unauthorized", 401);
    }

    if (!response.ok) {
      let errorDetails: any;
      try {
        errorDetails = await response.json();
      } catch {
        errorDetails = await response.text();
      }
      throw new ApiError(
        errorDetails?.detail || `HTTP ${response.status}: ${response.statusText}`,
        response.status,
        errorDetails
      );
    }

    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(error instanceof Error ? error.message : "Network request failed", 0);
  }
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id?: string;
}

export async function register(email: string, password: string): Promise<AuthResponse> {
  return fetchApi<AuthResponse>("/api/v1/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  return fetchApi<AuthResponse>("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function uploadImage(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return fetchApi<UploadResponse>("/api/v1/upload", { method: "POST", body: formData });
}

export async function startMemoryRun(
  uploadId: string,
  selectedFaceIndex: number,
  notes?: string
): Promise<MemoryRunCreateResponse> {
  return fetchApi<MemoryRunCreateResponse>("/api/v1/memory-runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      upload_id: uploadId,
      selected_face_index: selectedFaceIndex,
      notes: notes || null,
    }),
  });
}

export async function fetchMemoryRun(memory_runId: string): Promise<MemoryRunResponse> {
  return fetchApi<MemoryRunResponse>(`/api/v1/memory-runs/${memory_runId}`, { method: "GET" });
}

export async function enrollMemoryRunFaceReference(
  memory_runId: string,
  payload: FaceReferenceEnrollRequest
): Promise<FaceReferenceEnrollResponse> {
  return fetchApi<FaceReferenceEnrollResponse>(`/api/v1/memory-runs/${memory_runId}/reference`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchMemoryRunHistory(
  status?: MemoryRunStatus
): Promise<MemoryRunHistoryResponse> {
  const params = new URLSearchParams();
  if (status) {
    params.set("status", status);
  }
  const query = params.toString();
  return fetchApi<MemoryRunHistoryResponse>(`/api/v1/memory-runs${query ? `?${query}` : ""}`, {
    method: "GET",
  });
}

export async function getMemoryRunStreamUrl(): Promise<string> {
  return getMemoryRunStreamUrlWithCursor();
}

export async function getMemoryRunStreamUrlWithCursor(lastEventId?: string | null): Promise<string> {
  const token = getToken();
  const runtime = await getRuntimeConfig();
  const url = new URL(`${runtime.apiBaseUrl}/api/v1/memory-run-events/stream`);
  if (token) {
    url.searchParams.set("token", token);
  }
  if (lastEventId) {
    url.searchParams.set("last_event_id", lastEventId);
  }
  return url.toString();
}

export async function getMemoryRunStreamUrlWithCursorAsync(lastEventId?: string | null): Promise<string> {
  return getMemoryRunStreamUrlWithCursor(lastEventId);
}

export async function fetchReadiness(refreshRuntime = false): Promise<ReadinessResponse> {
  const runtime = await getRuntimeConfig({ refresh: refreshRuntime });
  const response = await fetch(`${runtime.apiBaseUrl}/ready`, { method: "GET" });
  const payload = (await response.json()) as ReadinessResponse;
  if (!response.ok && !payload) {
    throw new ApiError(`HTTP ${response.status}: ${response.statusText}`, response.status);
  }
  return payload;
}

export async function exportUserData(): Promise<Record<string, unknown>> {
  return fetchApi<Record<string, unknown>>("/api/v1/data/export", { method: "GET" });
}

export async function purgeUserData(): Promise<void> {
  await fetchApi<void>("/api/v1/data/purge", { method: "DELETE" });
}

export async function fetchPrivacySettings(): Promise<PrivacySettingsItem> {
  return fetchApi<PrivacySettingsItem>("/api/v1/privacy/settings", { method: "GET" });
}

export async function updatePrivacySettings(
  payload: PrivacySettingsUpdateRequest
): Promise<PrivacySettingsItem> {
  return fetchApi<PrivacySettingsItem>("/api/v1/privacy/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function exportUserVault(
  payload: VaultExportRequest = {}
): Promise<Record<string, unknown>> {
  return fetchApi<Record<string, unknown>>("/api/v1/data/vault/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function importUserVault(payload: VaultImportRequest): Promise<VaultImportResponse> {
  return fetchApi<VaultImportResponse>("/api/v1/data/vault/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchProviders(): Promise<ProviderMarketplaceResponse> {
  return fetchApi<ProviderMarketplaceResponse>("/api/v1/providers", { method: "GET" });
}

export async function fetchProviderPlugins(): Promise<ProviderPluginListResponse> {
  return fetchApi<ProviderPluginListResponse>("/api/v1/provider-plugins", { method: "GET" });
}

export async function fetchProviderConformance(): Promise<ProviderConformanceListResponse> {
  return fetchApi<ProviderConformanceListResponse>("/api/v1/provider-conformance", { method: "GET" });
}

export async function fetchProviderSelection(): Promise<ProviderSelectionResponse> {
  return fetchApi<ProviderSelectionResponse>("/api/v1/providers/selection", { method: "GET" });
}

export async function updateProviderSelection(
  payload: ProviderSelectionRequest
): Promise<ProviderSelectionResponse> {
  return fetchApi<ProviderSelectionResponse>("/api/v1/providers/selection", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchEvaluationMetrics(): Promise<EvaluationMetricsResponse> {
  return fetchApi<EvaluationMetricsResponse>("/api/v1/evaluation/metrics", { method: "GET" });
}

export async function fetchEvaluationDataset(): Promise<EvaluationDatasetResponse> {
  return fetchApi<EvaluationDatasetResponse>("/api/v1/evaluation/dataset", { method: "GET" });
}

export async function fetchProviderScorecard(): Promise<ProviderScorecardResponse> {
  return fetchApi<ProviderScorecardResponse>("/api/v1/evaluation/provider-scorecard", {
    method: "GET",
  });
}

export async function fetchBenchmarkPack(): Promise<BenchmarkPackResponse> {
  return fetchApi<BenchmarkPackResponse>("/api/v1/evaluation/benchmark-pack", { method: "GET" });
}

export async function fetchBenchmarkRuns(): Promise<BenchmarkRunListResponse> {
  return fetchApi<BenchmarkRunListResponse>("/api/v1/evaluation/benchmark-runs", { method: "GET" });
}

export async function createBenchmarkRun(
  payload: BenchmarkRunCreateRequest = {}
): Promise<BenchmarkRunItem> {
  return fetchApi<BenchmarkRunItem>("/api/v1/evaluation/benchmark-runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchMemoryDomains(): Promise<MemoryDomainListResponse> {
  return fetchApi<MemoryDomainListResponse>("/api/v1/memory-domains", { method: "GET" });
}

export async function fetchMemoryDomainTemplates(): Promise<MemoryDomainTemplateListResponse> {
  return fetchApi<MemoryDomainTemplateListResponse>("/api/v1/memory-domain-templates", {
    method: "GET",
  });
}

export async function fetchMemoryDomainTemplate(templateId: string): Promise<MemoryDomainTemplateItem> {
  return fetchApi<MemoryDomainTemplateItem>(`/api/v1/memory-domain-templates/${templateId}`, {
    method: "GET",
  });
}

export async function createMemoryEntityFromTemplate(
  templateId: string,
  payload: MemoryEntityCreateFromTemplateRequest
): Promise<MemoryEntityCreateResponse> {
  return fetchApi<MemoryEntityCreateResponse>(
    `/api/v1/memory-domain-templates/${templateId}/entities`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
}

export async function fetchMemoryEntities(domainType?: string): Promise<MemoryEntityListResponse> {
  const params = new URLSearchParams();
  if (domainType) {
    params.set("domain_type", domainType);
  }
  const query = params.toString();
  return fetchApi<MemoryEntityListResponse>(`/api/v1/memory-entities${query ? `?${query}` : ""}`, {
    method: "GET",
  });
}

export async function searchMemoryEntities(
  query: string,
  options: { domainType?: string; lifecycleState?: string; limit?: number } = {}
): Promise<MemorySearchResponse> {
  const params = new URLSearchParams();
  if (query) {
    params.set("q", query);
  }
  if (options.domainType) {
    params.set("domain_type", options.domainType);
  }
  if (options.lifecycleState) {
    params.set("lifecycle_state", options.lifecycleState);
  }
  if (options.limit) {
    params.set("limit", String(options.limit));
  }
  return fetchApi<MemorySearchResponse>(`/api/v1/memory-entities/search?${params.toString()}`, {
    method: "GET",
  });
}

export async function createMemoryEntity(
  payload: MemoryEntityCreateRequest
): Promise<MemoryEntityCreateResponse> {
  return fetchApi<MemoryEntityCreateResponse>("/api/v1/memory-entities", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchMemoryEntityDetail(entityId: string): Promise<MemoryEntityDetailResponse> {
  return fetchApi<MemoryEntityDetailResponse>(`/api/v1/memory-entities/${entityId}/detail`, {
    method: "GET",
  });
}

export async function updateMemoryEntity(
  entityId: string,
  payload: MemoryEntityUpdateRequest
): Promise<CorrectionResponse> {
  return fetchApi<CorrectionResponse>(`/api/v1/memory-entities/${entityId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchLearningPolicy(): Promise<LearningPolicyItem> {
  return fetchApi<LearningPolicyItem>("/api/v1/learning/policy", { method: "GET" });
}

export async function updateLearningPolicy(
  payload: LearningPolicyUpdateRequest
): Promise<LearningPolicyItem> {
  return fetchApi<LearningPolicyItem>("/api/v1/learning/policy", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function simulateLearningPolicy(): Promise<LearningPolicySimulationResponse> {
  return fetchApi<LearningPolicySimulationResponse>("/api/v1/learning/policy/simulation", {
    method: "GET",
  });
}

export async function fetchLearningSignals(status = "pending"): Promise<LearningSignalListResponse> {
  const params = new URLSearchParams();
  if (status) {
    params.set("status", status);
  }
  return fetchApi<LearningSignalListResponse>(`/api/v1/learning/signals?${params.toString()}`, {
    method: "GET",
  });
}

export async function dismissLearningSignal(
  signalId: string,
  payload: LearningSignalDismissRequest = {}
): Promise<LearningSignalItem> {
  return fetchApi<LearningSignalItem>(`/api/v1/learning/signals/${signalId}/dismiss`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchLearningReviewInbox(): Promise<LearningReviewInboxResponse> {
  return fetchApi<LearningReviewInboxResponse>("/api/v1/learning/review-inbox", {
    method: "GET",
  });
}

export async function replayMemoryLearning(entityId: string): Promise<LearningReplayResponse> {
  return fetchApi<LearningReplayResponse>(`/api/v1/memory-entities/${entityId}/learning/replay`, {
    method: "POST",
  });
}

export async function fetchMemoryEntityConfidenceLedger(
  entityId: string
): Promise<ConfidenceLedgerResponse> {
  return fetchApi<ConfidenceLedgerResponse>(`/api/v1/memory-entities/${entityId}/confidence-ledger`, {
    method: "GET",
  });
}

export async function queueMemoryEntityDomainReviewQuestions(
  entityId: string
): Promise<ActiveLearningQuestionListResponse> {
  return fetchApi<ActiveLearningQuestionListResponse>(
    `/api/v1/memory-entities/${entityId}/active-learning/domain-review`,
    { method: "POST" }
  );
}

export async function renameMemoryEntity(
  entityId: string,
  payload: MemoryEntityRenameRequest
): Promise<CorrectionResponse> {
  return fetchApi<CorrectionResponse>(`/api/v1/memory-entities/${entityId}/corrections/rename`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function forgetMemoryEntity(
  entityId: string,
  payload: MemoryEntityForgetRequest = {}
): Promise<CorrectionResponse> {
  return fetchApi<CorrectionResponse>(`/api/v1/memory-entities/${entityId}/corrections/forget`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function markMemoryEntityNotThis(
  entityId: string,
  payload: MemoryEntityNotThisRequest = {}
): Promise<CorrectionResponse> {
  return fetchApi<CorrectionResponse>(`/api/v1/memory-entities/${entityId}/corrections/not-this`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function mergeMemoryEntities(
  entityId: string,
  payload: MemoryEntityMergeRequest
): Promise<CorrectionResponse> {
  return fetchApi<CorrectionResponse>(`/api/v1/memory-entities/${entityId}/corrections/merge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function splitMemoryEntity(
  entityId: string,
  payload: MemoryEntitySplitRequest
): Promise<CorrectionResponse> {
  return fetchApi<CorrectionResponse>(`/api/v1/memory-entities/${entityId}/corrections/split`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchCorrections(): Promise<CorrectionListResponse> {
  return fetchApi<CorrectionListResponse>("/api/v1/corrections", { method: "GET" });
}

export async function undoCorrection(correctionId: string): Promise<CorrectionResponse> {
  return fetchApi<CorrectionResponse>(`/api/v1/corrections/${correctionId}/undo`, { method: "POST" });
}

export async function fetchMemoryLifecycleSummary(): Promise<MemoryLifecycleSummaryResponse> {
  return fetchApi<MemoryLifecycleSummaryResponse>("/api/v1/memory-lifecycle/summary", {
    method: "GET",
  });
}

export async function decayStaleMemoryEntities(
  payload: MemoryLifecycleDecayRequest = {}
): Promise<MemoryLifecycleOperationResponse> {
  return fetchApi<MemoryLifecycleOperationResponse>("/api/v1/memory-lifecycle/decay-stale", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function reinforceMemoryEntity(
  entityId: string,
  payload: MemoryLifecycleReinforceRequest = {}
): Promise<MemoryLifecycleOperationResponse> {
  return fetchApi<MemoryLifecycleOperationResponse>(
    `/api/v1/memory-entities/${entityId}/lifecycle/reinforce`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
}

export async function recordMemoryContradiction(
  entityId: string,
  payload: MemoryLifecycleContradictionRequest = {}
): Promise<MemoryLifecycleOperationResponse> {
  return fetchApi<MemoryLifecycleOperationResponse>(
    `/api/v1/memory-entities/${entityId}/lifecycle/contradiction`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
}

export async function fetchActiveLearningQuestions(
  status = "pending"
): Promise<ActiveLearningQuestionListResponse> {
  const params = new URLSearchParams();
  if (status) {
    params.set("status", status);
  }
  return fetchApi<ActiveLearningQuestionListResponse>(
    `/api/v1/active-learning/questions?${params.toString()}`,
    { method: "GET" }
  );
}

export async function respondToActiveLearningQuestion(
  questionId: string,
  payload: ActiveLearningQuestionResponseRequest
): Promise<ActiveLearningQuestionResponse> {
  return fetchApi<ActiveLearningQuestionResponse>(
    `/api/v1/active-learning/questions/${questionId}/response`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
}
