/**
 * Centralized API client — every backend call goes through here (Rule 35).
 * Contract: .claude/docs/API_SPEC.md (v1.1 FROZEN).
 *
 * - All enveloped calls inject `X-Trace-ID` and unwrap `APIResponse<T>.data`.
 * - `GET /health` is NON-enveloped, so it has a dedicated raw method.
 * - Zero raw `fetch` is allowed in components — import `apiClient` instead.
 */

import type {
  APIResponse,
  ApproveResponse,
  ApprovalDecision,
  AuditLogListParams,
  AuditLogListResponse,
  BatchEvaluation,
  BatchRun,
  BatchRunStatus,
  BatchRunSummary,
  BulkOperationResponse,
  ChunkStrategy,
  ConfiguratorStepRequest,
  ConfiguratorStepResponse,
  CreatePipelineRequest,
  DatasetLifecycleStatus,
  DatasetStatistics,
  DeployRequest,
  DeploymentHistoryResponse,
  DeploymentStatusResponse,
  DiagnosisResponse,
  DocumentDetail,
  DocumentFilters,
  DocumentsListResponse,
  EvaluationConfig,
  EvaluationDataset,
  EvaluationDatasetVersion,
  EvaluationHistoryResponse,
  ExperimentsListResponse,
  GoldenQuestion,
  HealthResponse,
  ImprovementResponse,
  ApplyImprovementResponse,
  PipelineVersionsResponse,
  QuestionReviewStatus,
  ResultDetail,
  ResultReviewStatus,
  RollbackResponse,
  IngestResponse,
  JobStatusResponse,
  ObserverViewResponse,
  PaginatedPipelines,
  PaginatedProjects,
  Pipeline,
  PipelineDetail,
  PipelineWithRun,
  ProcessingStatusResponse,
  Project,
  RetrievalRequest,
  RetrievalResult,
  QueryAnswerResult,
  RunMetricsResponse,
  ScoreResult,
  SystemHealth,
} from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Stopgap tenant ID until real multi-tenant auth lands (no auth context or JWT
 * claim currently carries organization_id anywhere in this app). Every route
 * that depends on `get_organization_id` (app/core/dependencies.py) 422s without
 * this header — that includes E-12's deploy endpoints, not just audit-log.
 */
const DEFAULT_ORG_ID = process.env.NEXT_PUBLIC_DEFAULT_ORG_ID ?? "";

/** Performs an enveloped request and returns the unwrapped `data` payload. */
async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Trace-ID": crypto.randomUUID(),
      "X-Organization-ID": DEFAULT_ORG_ID,
      ...init?.headers,
    },
  });

  const envelope: APIResponse<T> = await res.json();

  if (!res.ok || envelope.status === "error") {
    const msg = envelope.error?.message ?? `HTTP ${res.status}`;
    throw new Error(msg);
  }

  return envelope.data;
}

export const apiClient = {
  // ── Projects ───────────────────────────────────────────────────────────────
  listProjects: async (status?: "active" | "archived"): Promise<Project[]> => {
    const qs = status ? `?status=${status}` : "";
    const data = await apiFetch<PaginatedProjects>(`/api/v1/projects${qs}`);
    return data.projects;
  },

  // ── Pipelines ────────────────────────────────────────────────────────────────
  createPipeline: (body: CreatePipelineRequest): Promise<Pipeline> =>
    apiFetch("/api/v1/pipelines", { method: "POST", body: JSON.stringify(body) }),

  /** PATCH /pipelines/{id} — the only transition exposed: draft -> pending.
   * Fired by the Configurator wizard's step 6 ("Launch Pipeline") once a
   * draft pipeline (created after step 1) is ready to leave draft state. */
  /**
   * chunkStrategy/variantConfig (25-Jul-2026, Configurator wiring): the
   * wizard's real chunking/retrieval/generation settings, made in steps 3-5
   * -- after the draft pipeline already exists from step 1->2. Backend
   * creates a real v2 with these applied (v1's pipeline_versions row is
   * immutable) rather than silently discarding them into config_yaml.
   */
  finalizePipeline: (
    pipelineId: string,
    chunkStrategy?: ChunkStrategy,
    variantConfig?: Record<string, unknown>,
  ): Promise<Pipeline> =>
    apiFetch(`/api/v1/pipelines/${pipelineId}`, {
      method: "PATCH",
      body: JSON.stringify({
        status: "pending",
        ...(chunkStrategy ? { chunk_strategy: chunkStrategy } : {}),
        ...(variantConfig ? { variant_config: variantConfig } : {}),
      }),
    }),

  /** GET /pipelines?project_id= — unwraps the paginated `{ pipelines, ... }` envelope. */
  listPipelines: async (projectId?: string): Promise<PipelineWithRun[]> => {
    const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
    const data = await apiFetch<PaginatedPipelines>(`/api/v1/pipelines${qs}`);
    return data.pipelines;
  },

  /** GET /pipelines/{id} — pipeline + latest_run + version_count. */
  getPipeline: (pipelineId: string): Promise<PipelineDetail> =>
    apiFetch(`/api/v1/pipelines/${pipelineId}`),

  /** DELETE /pipelines/{id} — real soft-delete (sets deleted_at server-side,
   * never hard-deletes; see routes/pipelines.py `soft_delete`). No bulk route
   * exists yet, so multi-select delete fans this out client-side. */
  deletePipeline: (pipelineId: string): Promise<{ pipeline_id: string; deleted: boolean }> =>
    apiFetch(`/api/v1/pipelines/${pipelineId}`, { method: "DELETE" }),

  // ── Configurator wizard (E-5; API_SPEC #1, #2) ───────────────────────────────
  /** POST /configurator — persist one wizard step; returns pipeline_id + next_step. */
  submitConfiguratorStep: (
    body: ConfiguratorStepRequest,
  ): Promise<ConfiguratorStepResponse> =>
    apiFetch("/api/v1/configurator", { method: "POST", body: JSON.stringify(body) }),

  /**
   * POST /ingest — Step 1 document upload as multipart/form-data (API_SPEC #2).
   * Deliberately bypasses `apiFetch`: that helper forces `Content-Type: application/json`
   * + `JSON.stringify`, which corrupts a multipart body. Here the browser sets the
   * multipart boundary itself, so `Content-Type` is intentionally omitted. X-Trace-ID
   * is still injected; the standard envelope is still unwrapped (mirrors `checkHealth`).
   */
  ingestDocument: async (
    file: File,
    pipelineId: string,
    chunkStrategy?: ChunkStrategy,
  ): Promise<IngestResponse> => {
    const form = new FormData();
    form.append("files", file); // backend: files: list[UploadFile]
    if (chunkStrategy) form.append("chunk_strategy", chunkStrategy);

    // pipeline_id goes as URL query param, NOT form field (Rule 35 / ingest.py)
    const res = await fetch(
      `${BASE_URL}/api/v1/ingest?pipeline_id=${encodeURIComponent(pipelineId)}`,
      {
        method: "POST",
        headers: {
          "X-Trace-ID": crypto.randomUUID(), // NO Content-Type — browser sets multipart boundary
          "X-Organization-ID": DEFAULT_ORG_ID,
        },
        body: form,
      },
    );

    const envelope: APIResponse<IngestResponse> = await res.json();
    if (!res.ok || envelope.status === "error") {
      throw new Error(envelope.error?.message ?? `HTTP ${res.status}`);
    }
    return envelope.data;
  },

  // ── Evaluation ──────────────────────────────────────────────────────────────
  /**
   * POST /evaluate — dispatches a full 3-layer evaluation run (Unified Score + RAGAS + Adversarial).
   * Route is mounted at /api/v1/evaluate (prefix="/evaluate" in api.py, NOT /pipelines/{id}/evaluate).
   * Returns job_id for polling via GET /api/v1/jobs/{job_id}.
   *
   * query (P0.5-1, 12-Jul-2026): a real question is required — the backend
   * rejects an empty query with 422 unless the pipeline's ingested document
   * matches the golden-path demo fixture, in which case a curated question
   * is used automatically. Pass a real query for any other document.
   */
  startEvaluation: (pipelineId: string, query?: string): Promise<{ run_id: string; job_id: string }> =>
    apiFetch("/api/v1/evaluate", {
      method: "POST",
      body: JSON.stringify({ pipeline_id: pipelineId, query: query || undefined }),
    }),

  getScore: (runId: string): Promise<ScoreResult> => apiFetch(`/api/v1/score/${runId}`),

  /** GET /evaluate/history — real per-pipeline evaluation run history (12-Jul-2026, replaces MOCK_HISTORY). */
  getEvaluationHistory: (pipelineId: string, limit = 20): Promise<EvaluationHistoryResponse> =>
    apiFetch(`/api/v1/evaluate/history?pipeline_id=${encodeURIComponent(pipelineId)}&limit=${limit}`),

  // ── Real per-run metrics (Part B.0, 12-Jul-2026) ─────────────────────────────
  /** GET /runs/{run_id}/metrics — real agent_metrics rows (cost/tokens/provider per LLM call). */
  getRunMetrics: (runId: string): Promise<RunMetricsResponse> =>
    apiFetch(`/api/v1/runs/${runId}/metrics`),

  // ── Observer (Part B.2, 12-Jul-2026) ─────────────────────────────────────────
  /** GET /observe?pipeline_id= — real Observer signals + real (unpadded) score history. */
  getObserverView: (pipelineId: string): Promise<ObserverViewResponse> =>
    apiFetch(`/api/v1/observe?pipeline_id=${encodeURIComponent(pipelineId)}`),

  // ── Improver (Part B.3, 12-Jul-2026) ─────────────────────────────────────────
  /** GET /improve/{run_id} — real winner + all 3 scored candidates (score_type: "estimated"). */
  getImprovement: (runId: string): Promise<ImprovementResponse> =>
    apiFetch(`/api/v1/improve/${runId}`),

  // ── Optimizer / Apply Improvement (20-Jul-2026) ──────────────────────────────
  /** POST /pipelines/{id}/apply-improvement — applies a real Improver candidate,
   * persists a new version, rebuilds, and dispatches re-evaluation in the
   * background. Poll pollJob(job_id) for completion. */
  applyImprovement: (
    pipelineId: string,
    body: { run_id: string; variant_id: string; query?: string },
  ): Promise<ApplyImprovementResponse> =>
    apiFetch(`/api/v1/pipelines/${pipelineId}/apply-improvement`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  /** GET /pipelines/{id}/versions — real version history + score per version. */
  listPipelineVersions: (pipelineId: string): Promise<PipelineVersionsResponse> =>
    apiFetch(`/api/v1/pipelines/${pipelineId}/versions`),

  /** POST /pipelines/{id}/rollback — real, reversible: points the pipeline
   * back at an earlier version's config, never touches vector tables. */
  rollbackPipeline: (pipelineId: string, versionNumber: number): Promise<RollbackResponse> =>
    apiFetch(`/api/v1/pipelines/${pipelineId}/rollback`, {
      method: "POST",
      body: JSON.stringify({ version_number: versionNumber }),
    }),

  /** POST /pipelines/{id}/retry-indexing — 26-Jul-2026: re-dispatches the
   * same re-index Launch uses, for the pipeline's CURRENT version, only
   * valid when status is "failed". */
  retryIndexing: (pipelineId: string): Promise<{ pipeline_id: string; status: string }> =>
    apiFetch(`/api/v1/pipelines/${pipelineId}/retry-indexing`, { method: "POST" }),

  // ── Diagnoser (Part E rewiring, 12-Jul-2026) ─────────────────────────────────
  /** GET /diagnose/{run_id} — real failure classification, was never called by the frontend before. */
  getDiagnosis: (runId: string): Promise<DiagnosisResponse> =>
    apiFetch(`/api/v1/diagnose/${runId}`),

  // ── Experiments (Part E rewiring, 12-Jul-2026) ───────────────────────────────
  /** GET /experiments — real evaluation-run history with score deltas, was never called by the frontend before. */
  listExperiments: (params?: {
    pipelineId?: string;
    limit?: number;
    offset?: number;
  }): Promise<ExperimentsListResponse> => {
    const qs = new URLSearchParams();
    if (params?.pipelineId) qs.set("pipeline_id", params.pipelineId);
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return apiFetch(`/api/v1/experiments${suffix}`);
  },

  // ── HITL approval (API_SPEC #11) ─────────────────────────────────────────────
  /**
   * POST /hitl/approve (mounted at /api/v1/hitl/approve in api.py).
   * Body field is `reviewer_note` — NOT `notes` — matching ApprovalRequest in approve.py.
   */
  approve: (
    runId: string,
    decision: ApprovalDecision,
    reviewerNote?: string,
  ): Promise<ApproveResponse> =>
    apiFetch("/api/v1/hitl/approve", {
      method: "POST",
      body: JSON.stringify({ run_id: runId, decision, reviewer_note: reviewerNote ?? "" }),
    }),

  // ── Deployment (E-12; Chapter 24) ────────────────────────────────────────────
  /** POST /deploy/{run_id} — body is required: DeployRequest (task_arn, approval_token?). */
  deploy: (runId: string, body: DeployRequest): Promise<{ deploy_status: string; deployment_id: string }> =>
    apiFetch(`/api/v1/deploy/${runId}`, { method: "POST", body: JSON.stringify(body) }),

  /** Canonical frozen endpoint: POST /deploy/rollback (NOT /rollback). */
  rollback: (pipelineId: string, rollbackReason: string): Promise<{ rollback_status: string; deployment_id: string }> =>
    apiFetch("/api/v1/deploy/rollback", {
      method: "POST",
      body: JSON.stringify({ pipeline_id: pipelineId, rollback_reason: rollbackReason }),
    }),

  /** POST /deploy/promote — transitions the active Blue/Green canary to 100% Green. */
  promote: (pipelineId: string): Promise<{ promote_status: string; deployment_id: string }> =>
    apiFetch("/api/v1/deploy/promote", {
      method: "POST",
      body: JSON.stringify({ pipeline_id: pipelineId }),
    }),

  /** GET /deploy/history?pipeline_id= — newest-first deployment history table. */
  getDeploymentHistory: (pipelineId: string, limit?: number, offset?: number): Promise<DeploymentHistoryResponse> => {
    const params = new URLSearchParams({ pipeline_id: pipelineId });
    if (limit !== undefined) params.set("limit", String(limit));
    if (offset !== undefined) params.set("offset", String(offset));
    return apiFetch(`/api/v1/deploy/history?${params.toString()}`);
  },

  /** GET /deploy/status?pipeline_id= — most recent deployment (any status), for live polling. */
  getDeploymentStatus: (pipelineId: string): Promise<DeploymentStatusResponse> => {
    const params = new URLSearchParams({ pipeline_id: pipelineId });
    return apiFetch(`/api/v1/deploy/status?${params.toString()}`);
  },

  // ── Audit log (E-13; Chapter 25) ──────────────────────────────────────────────
  /** GET /audit-log?event_type=&run_id=&limit=&offset= (route: app/routes/audit_log.py). */
  listAuditLog: (params: AuditLogListParams = {}): Promise<AuditLogListResponse> => {
    const qs = new URLSearchParams();
    if (params.event_type) qs.set("event_type", params.event_type);
    if (params.run_id) qs.set("run_id", params.run_id);
    qs.set("limit", String(params.limit ?? 25));
    qs.set("offset", String(params.offset ?? 0));
    return apiFetch(`/api/v1/audit-log?${qs.toString()}`);
  },

  // ── Jobs ──────────────────────────────────────────────────────────────────────
  pollJob: (jobId: string): Promise<JobStatusResponse> => apiFetch(`/api/v1/jobs/${jobId}`),

  // ── Retrieval Explorer ────────────────────────────────────────────────────────
  /**
   * POST /retrieve — retrieval-only inspection (rewrite -> hybrid search ->
   * rerank, no answer generation). Real chunk IDs, real Recall@5 with
   * MEASURED/NOT_COLLECTED provenance (P0.6-1 discipline) -- never a
   * fabricated 0.5. Reuses the same SearchService/RerankService instances
   * as the production GET /query answer-generation endpoint.
   */
  queryRetrieval: (request: RetrievalRequest): Promise<RetrievalResult> =>
    apiFetch("/api/v1/retrieve", { method: "POST", body: JSON.stringify(request) }),

  /**
   * GET /query — production RAG generation (retrieve -> rerank -> LLM
   * generation with a "use only the provided context" prompt constraint).
   * Returns a real grounded answer + real page citations + real latency.
   * No confidence score, faithfulness, or "chunks used vs ignored" field
   * exists on this response — those require a real Evaluator run
   * (Unified Score/RAGAS), never fabricate them client-side.
   */
  queryAnswer: (params: { pipeline_id: string; query: string }): Promise<QueryAnswerResult> =>
    apiFetch(`/api/v1/query?${new URLSearchParams(params).toString()}`),

  // ── Documents Management (F-17; Chapter 31) ───────────────────────────────────
  /**
   * GET /documents — list documents with optional filters (API_SPEC § GET /documents).
   * Phase 4: Returns full paginated response with total count.
   */
  listDocuments: async (filters?: DocumentFilters): Promise<DocumentsListResponse> => {
    const params = new URLSearchParams();
    if (filters?.search) params.set("search", filters.search);
    if (filters?.status) params.set("status", filters.status);
    if (filters?.mime_type) params.set("mime_type", filters.mime_type);
    if (filters?.uploaded_after) params.set("uploaded_after", filters.uploaded_after);
    if (filters?.uploaded_before) params.set("uploaded_before", filters.uploaded_before);
    // Phase 4: Pagination and sorting
    if (filters?.page !== undefined) params.set("page", String(filters.page));
    if (filters?.page_size !== undefined) params.set("page_size", String(filters.page_size));
    if (filters?.sort_by) params.set("sort_by", filters.sort_by);
    if (filters?.sort_order) params.set("sort_order", filters.sort_order);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return await apiFetch<DocumentsListResponse>(`/api/v1/documents${qs}`);
  },

  /** GET /documents/{id} — get document detail with chunk counts. */
  getDocument: (documentId: string): Promise<DocumentDetail> =>
    apiFetch(`/api/v1/documents/${documentId}`),

  /** POST /documents/reprocess — trigger re-chunking and re-embedding. */
  reprocessDocument: (documentId: string): Promise<{ job_id: string }> =>
    apiFetch("/api/v1/documents/reprocess", {
      method: "POST",
      body: JSON.stringify({ document_id: documentId }),
    }),

  /** DELETE /documents/{id} — archive or delete document. */
  deleteDocument: (documentId: string): Promise<void> =>
    apiFetch(`/api/v1/documents/${documentId}`, { method: "DELETE" }),

  /** PUT /documents/{id} — update document metadata (tags, categories). */
  updateDocument: (
    documentId: string,
    updates: { tags?: string[]; categories?: string[] },
  ): Promise<DocumentDetail> =>
    apiFetch(`/api/v1/documents/${documentId}`, {
      method: "PUT",
      body: JSON.stringify(updates),
    }),

  // ── Phase 2: Processing Status & Bulk Operations (F-17 Phase 2) ───────────────
  /** GET /documents/{id}/status — get live processing status with stage details. */
  getProcessingStatus: (documentId: string): Promise<ProcessingStatusResponse> =>
    apiFetch(`/api/v1/documents/${documentId}/status`),

  /** POST /documents/bulk/delete — bulk delete multiple documents. */
  bulkDeleteDocuments: (documentIds: string[]): Promise<BulkOperationResponse> =>
    apiFetch("/api/v1/documents/bulk/delete", {
      method: "POST",
      body: JSON.stringify({ document_ids: documentIds }),
    }),

  /** POST /documents/bulk/archive — bulk archive multiple documents. */
  bulkArchiveDocuments: (documentIds: string[]): Promise<BulkOperationResponse> =>
    apiFetch("/api/v1/documents/bulk/archive", {
      method: "POST",
      body: JSON.stringify({ document_ids: documentIds }),
    }),

  /** POST /documents/bulk/reprocess — bulk reprocess multiple documents. */
  bulkReprocessDocuments: (documentIds: string[]): Promise<BulkOperationResponse> =>
    apiFetch("/api/v1/documents/bulk/reprocess", {
      method: "POST",
      body: JSON.stringify({ document_ids: documentIds }),
    }),

  /** GET /documents/export/metadata — export metadata as CSV. */
  exportDocumentMetadata: async (documentIds?: string[]): Promise<Blob> => {
    const params = new URLSearchParams();
    if (documentIds && documentIds.length > 0) {
      params.set("ids", documentIds.join(","));
    }
    const qs = params.toString() ? `?${params.toString()}` : "";
    const res = await fetch(`${BASE_URL}/api/v1/documents/export/metadata${qs}`, {
      headers: { "X-Trace-ID": crypto.randomUUID() },
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`HTTP ${res.status}: ${text}`);
    }
    return await res.blob();
  },

  // ── Evaluation Center: Golden Datasets (24-Jul-2026) ─────────────────────────
  /** POST /evaluation-datasets — creates the dataset AND its first 'v1' draft version. */
  createDataset: (body: {
    name: string;
    description?: string;
    domain?: string;
    tags?: string[];
  }): Promise<{ dataset: EvaluationDataset; initial_version: EvaluationDatasetVersion }> =>
    apiFetch("/api/v1/evaluation-datasets", { method: "POST", body: JSON.stringify(body) }),

  listDatasets: async (status?: "active" | "archived"): Promise<EvaluationDataset[]> => {
    const qs = status ? `?status=${status}` : "";
    const data = await apiFetch<{ items: EvaluationDataset[] }>(
      `/api/v1/evaluation-datasets${qs}`,
    );
    return data.items;
  },

  getDataset: (datasetId: string): Promise<EvaluationDataset> =>
    apiFetch(`/api/v1/evaluation-datasets/${datasetId}`),

  getDatasetStatistics: (datasetId: string): Promise<DatasetStatistics> =>
    apiFetch(`/api/v1/evaluation-datasets/${datasetId}/statistics`),

  archiveDataset: (datasetId: string): Promise<{ dataset_id: string }> =>
    apiFetch(`/api/v1/evaluation-datasets/${datasetId}/archive`, { method: "POST" }),

  deleteDataset: (datasetId: string): Promise<{ dataset_id: string }> =>
    apiFetch(`/api/v1/evaluation-datasets/${datasetId}`, { method: "DELETE" }),

  listDatasetVersions: async (datasetId: string): Promise<EvaluationDatasetVersion[]> => {
    const data = await apiFetch<{ items: EvaluationDatasetVersion[] }>(
      `/api/v1/evaluation-datasets/${datasetId}/versions`,
    );
    return data.items;
  },

  /** POST /evaluation-datasets/{id}/versions — clones the latest version's
   * questions into a new 'draft' version by default (Rule 55 immutability). */
  publishDatasetVersion: (
    datasetId: string,
    body: { notes?: string; copy_from_latest?: boolean },
  ): Promise<EvaluationDatasetVersion> =>
    apiFetch(`/api/v1/evaluation-datasets/${datasetId}/versions`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  updateDatasetVersionStatus: (
    versionId: string,
    lifecycleStatus: DatasetLifecycleStatus,
  ): Promise<{ version_id: string; lifecycle_status: DatasetLifecycleStatus }> =>
    apiFetch(`/api/v1/evaluation-datasets/versions/${versionId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ lifecycle_status: lifecycleStatus }),
    }),

  createGoldenQuestion: (body: {
    dataset_version_id: string;
    question: string;
    purpose?: string;
    reference_answer?: string;
    expected_context?: string;
    reference_document_id?: string;
    reference_pages?: string;
    relevant_chunk_ids?: string[];
    category?: string;
    difficulty?: string;
    metric_focus?: string;
    tags?: string[];
  }): Promise<GoldenQuestion> =>
    apiFetch("/api/v1/evaluation-datasets/questions", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listGoldenQuestions: async (
    versionId: string,
    filters?: {
      review_status?: QuestionReviewStatus;
      category?: string;
      difficulty?: string;
      metric_focus?: string;
      search?: string;
    },
  ): Promise<GoldenQuestion[]> => {
    const qs = new URLSearchParams();
    if (filters?.review_status) qs.set("review_status", filters.review_status);
    if (filters?.category) qs.set("category", filters.category);
    if (filters?.difficulty) qs.set("difficulty", filters.difficulty);
    if (filters?.metric_focus) qs.set("metric_focus", filters.metric_focus);
    if (filters?.search) qs.set("search", filters.search);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    const data = await apiFetch<{ items: GoldenQuestion[] }>(
      `/api/v1/evaluation-datasets/versions/${versionId}/questions${suffix}`,
    );
    return data.items;
  },

  updateGoldenQuestion: (
    questionId: string,
    updates: Partial<{
      question: string;
      purpose: string;
      reference_answer: string;
      expected_context: string;
      category: string;
      difficulty: string;
      metric_focus: string;
      tags: string[];
    }>,
  ): Promise<{ question_id: string }> =>
    apiFetch(`/api/v1/evaluation-datasets/questions/${questionId}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    }),

  reviewGoldenQuestion: (
    questionId: string,
    reviewStatus: QuestionReviewStatus,
    reviewerNotes?: string,
  ): Promise<{ question_id: string }> =>
    apiFetch(`/api/v1/evaluation-datasets/questions/${questionId}/review`, {
      method: "POST",
      body: JSON.stringify({ review_status: reviewStatus, reviewer_notes: reviewerNotes }),
    }),

  createEvaluationConfig: (body: {
    name: string;
    pipeline_id?: string;
    retriever_strategy?: string;
    reranker?: string;
    embedding_model?: string;
    top_k?: number;
    chunk_size?: number;
    judge_provider?: string;
    judge_model?: string;
    temperature?: number;
  }): Promise<EvaluationConfig> =>
    apiFetch("/api/v1/evaluation-datasets/configs", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listEvaluationConfigs: async (pipelineId?: string): Promise<EvaluationConfig[]> => {
    const qs = pipelineId ? `?pipeline_id=${encodeURIComponent(pipelineId)}` : "";
    const data = await apiFetch<{ items: EvaluationConfig[] }>(
      `/api/v1/evaluation-datasets/configs${qs}`,
    );
    return data.items;
  },

  // ── Evaluation Center: Batch Evaluation (24-Jul-2026) ────────────────────────
  startBatchRun: (body: {
    dataset_version_id: string;
    pipeline_id: string;
    config_id?: string;
  }): Promise<BatchRun> =>
    apiFetch("/api/v1/batch-evaluations", { method: "POST", body: JSON.stringify(body) }),

  listBatchRuns: async (filters?: {
    datasetId?: string;
    pipelineId?: string;
    status?: BatchRunStatus;
  }): Promise<BatchRun[]> => {
    const qs = new URLSearchParams();
    if (filters?.datasetId) qs.set("dataset_id", filters.datasetId);
    if (filters?.pipelineId) qs.set("pipeline_id", filters.pipelineId);
    if (filters?.status) qs.set("status", filters.status);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    const data = await apiFetch<{ items: BatchRun[] }>(`/api/v1/batch-evaluations${suffix}`);
    return data.items;
  },

  getBatchRun: (batchRunId: string): Promise<BatchRunSummary> =>
    apiFetch(`/api/v1/batch-evaluations/${batchRunId}`),

  listBatchRunResults: async (
    batchRunId: string,
    filters?: { status?: string; reviewStatus?: string },
  ): Promise<BatchEvaluation[]> => {
    const qs = new URLSearchParams();
    if (filters?.status) qs.set("status", filters.status);
    if (filters?.reviewStatus) qs.set("review_status", filters.reviewStatus);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    const data = await apiFetch<{ items: BatchEvaluation[] }>(
      `/api/v1/batch-evaluations/${batchRunId}/results${suffix}`,
    );
    return data.items;
  },

  getResultDetail: (batchEvaluationId: string): Promise<ResultDetail> =>
    apiFetch(`/api/v1/batch-evaluations/results/${batchEvaluationId}/detail`),

  resumeBatchRun: (batchRunId: string): Promise<BatchRun> =>
    apiFetch(`/api/v1/batch-evaluations/${batchRunId}/resume`, { method: "POST" }),

  cancelBatchRun: (batchRunId: string): Promise<{ batch_run_id: string }> =>
    apiFetch(`/api/v1/batch-evaluations/${batchRunId}/cancel`, { method: "POST" }),

  reviewBatchResult: (
    batchEvaluationId: string,
    body: { review_status: ResultReviewStatus; reviewer_notes?: string; corrected_answer?: string },
  ): Promise<{ batch_evaluation_id: string }> =>
    apiFetch(`/api/v1/batch-evaluations/results/${batchEvaluationId}/review`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  /** GET /batch-evaluations/{id}/export?format=csv|json — returns a Blob for download. */
  exportBatchRun: async (batchRunId: string, format: "csv" | "json" = "csv"): Promise<Blob> => {
    const res = await fetch(
      `${BASE_URL}/api/v1/batch-evaluations/${batchRunId}/export?format=${format}`,
      { headers: { "X-Trace-ID": crypto.randomUUID(), "X-Organization-ID": DEFAULT_ORG_ID } },
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.blob();
  },

  // ── Health (NON-enveloped; used for the Header connectivity dot) ──────────────
  checkHealth: async (): Promise<HealthResponse> => {
    const res = await fetch(`${BASE_URL}/health`, {
      headers: { "X-Trace-ID": crypto.randomUUID() },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as HealthResponse;
  },

  /**
   * GET /health, unwrapping the standard envelope's `data` (F-19; System Health
   * Dashboard). Unlike `checkHealth` (raw, header dot), this surfaces the real
   * service/version/environment/status the backend already returns. Round-trip
   * latency is measured by the caller (use-system-health), not here.
   */
  getSystemHealth: (): Promise<SystemHealth> => apiFetch("/health"),

  /**
   * POST /api/v1/marketing/chat — public, unauthenticated AIRA assistant on
   * the marketing site. Product Q&A only (no pipeline/document access).
   */
  marketingChat: (message: string): Promise<{ reply: string }> =>
    apiFetch("/api/v1/marketing/chat", {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
};
