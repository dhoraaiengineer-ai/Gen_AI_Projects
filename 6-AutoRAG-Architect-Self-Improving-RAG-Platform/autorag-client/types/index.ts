/**
 * Shared TypeScript types for AutoRAG Architect v3.0 frontend.
 * Aligned to the FROZEN API contract: .claude/docs/API_SPEC.md (v1.0).
 * Monorepo rule: shared DTOs live here only — never duplicated in components.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Enums (verbatim from API_SPEC.md § Enums)
// ─────────────────────────────────────────────────────────────────────────────

/** Matches backend's real JobStatus values (jobs.py) — includes pending/blocked, not queued/cancelled. */
// pending_approval (P0.5, 12-Jul-2026): HITL-band score paused at the `hitl`
// node awaiting POST /approve/{run_id} -- see ScoreResult.status for detail.
export type JobStatus =
  | "pending"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "blocked"
  | "cancelled"
  | "pending_approval";
/** Matches app/models/pipeline.py ck_pipelines_status (API_SPEC.md v1.1). */
export type PipelineStatus = "draft" | "pending" | "running" | "ready" | "failed" | "decommissioned";
export type ApprovalStatus = "pending" | "approved" | "rejected";
/** Decision sent to POST /approve. */
export type ApprovalDecision = "auto" | "approve" | "reject";
/** PipelineRun lifecycle (from GRAPH_STATE.md). */
export type RunStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "blocked"
  | "rolled_back"
  | "pending_approval";
export type ChunkStrategy = "semantic" | "hierarchical" | "late";
/** LLM generation provider — failover chain order (CLAUDE.md §1). */
export type LLMProvider = "gemini-flash-3.5" | "kimi-k2.6" | "gemini-3.5";

// ─────────────────────────────────────────────────────────────────────────────
// Response envelope (API_SPEC.md § Global Requirements)
// ─────────────────────────────────────────────────────────────────────────────

export interface APIResponse<T> {
  status: "success" | "error";
  data: T;
  error: ErrorDetail | null;
  request_id: string;
}

export interface ErrorDetail {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Core domain schemas (from DB_SCHEMA.md / GRAPH_STATE.md via API_SPEC.md)
// ─────────────────────────────────────────────────────────────────────────────

export interface Project {
  id: string;
  name: string;
  description: string;
  owner_id: string;
  created_by: string;
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
}

/**
 * Pipeline schema — matches the real backend shape (app/services/pipeline_service.py
 * `_pipeline_to_dict`), not the original API_SPEC.md v1.0 draft. There is no separate
 * `projects` table in V3 (pipelines ARE projects — see app/routes/projects.py "V3
 * demo bridge"), and per-pipeline `scoring_weights`/`approval_mode`/`retrieval_config`
 * were never implemented — deployment gating is a single global formula
 * (CLAUDE.md §9), not per-pipeline configurable. See API_SPEC.md v1.1.
 */
export interface Pipeline {
  id: string;
  organization_id: string;
  name: string;
  status: PipelineStatus;
  chunk_strategy: ChunkStrategy | null;
  embedding_model: string;
  unified_score: number | null;
  current_version: number;
  created_at: string;
  updated_at: string;
}

/** Latest evaluation run summary, returned by GET /pipelines/{id}. */
export interface PipelineRunSummary {
  id: string;
  // Nullable (13-Jul-2026 fix, same root cause as ScoreResult.unified_score):
  // app/routes/pipelines.py:115 returns null whenever the run's score was
  // never measured (e.g. failed before Evaluator ran) -- this type
  // previously lied about that, letting `computeDashboardKpis` silently sum
  // null as 0 into the fleet average (lib/kpi.ts).
  unified_score: number | null;
  // Nullable (13-Jul-2026 fix): app/routes/pipelines.py:116 returns null from
  // the same nullable `evaluation_run.faithfulness` column as
  // ScoreResult.faithfulness. Previously bare `number` let `null < 0.5`
  // coerce to `true` in isHardBlock(), silently mislabeling every
  // never-evaluated run as "Hard Block" on the dashboard.
  faithfulness_score: number | null;
  status: RunStatus;
  finished_at: string | null;
}

/** GET /pipelines/{id} response payload. */
export interface PipelineDetail {
  pipeline: Pipeline;
  latest_run: PipelineRunSummary | null;
  version_count: number;
}

/** A pipeline enriched with its latest run — the dashboard's display row. */
export interface PipelineWithRun extends Pipeline {
  latest_run: PipelineRunSummary | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Paginated list envelopes (API_SPEC.md § list endpoints)
// ─────────────────────────────────────────────────────────────────────────────

export interface Paginated {
  total: number;
  limit: number;
  offset: number;
}

/** 26-Jul-2026: GET /pipelines now includes latest_run per row (batch-fetched
 * server-side via one query), so the frontend no longer needs to fan out a
 * GET /pipelines/{id} per pipeline just to display it -- see hooks/use-pipelines.ts. */
export interface PaginatedPipelines extends Paginated {
  pipelines: PipelineWithRun[];
}

export interface PaginatedProjects extends Paginated {
  projects: Project[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Action payloads
// ─────────────────────────────────────────────────────────────────────────────

/** POST /approve response (API_SPEC.md #11). */
export interface ApproveResponse {
  run_id: string;
  approval_status: "approved" | "rejected" | "pending_hitl";
  next_step: "deploy" | "improve" | string;
}

/** GET /health — minimal, NON-enveloped container health (API_SPEC.md § Health). */
export interface HealthResponse {
  status: string; // "ok"
  service: string;
}

/**
 * GET /health envelope `data` payload (F-19). The backend actually returns an
 * enveloped body — `{ status, data: { service, version, environment, status }, ... }`
 * (autorag-server/app/main.py health_check). `checkHealth` reads it raw for the
 * header dot; the System Health Dashboard unwraps `data` via apiClient.getSystemHealth
 * to surface the real version/environment/status.
 */
export interface SystemHealth {
  service: string;
  version: string;
  environment: string;
  status: string; // "healthy"
}

/** POST /pipelines body — matches app/schemas/pipeline.py PipelineCreateRequest. */
export interface CreatePipelineRequest {
  name: string;
  config_yaml?: string;
  chunk_strategy?: ChunkStrategy;
  /** Only "draft" is accepted by the backend (schema-restricted) -- used by the
   * Configurator wizard to create a real pipeline right after step 1. */
  status?: "draft";
}

// ─────────────────────────────────────────────────────────────────────────────
// Evaluation scorecard (consumed by components/evaluation/CostLatencyPanel)
// ─────────────────────────────────────────────────────────────────────────────

export interface ScoreResult {
  run_id: string;
  // Real field, was missing from this type despite score.py always returning
  // it (app/routes/score.py: "pipeline_id": str(run.pipeline_id)) — added
  // 12-Jul-2026 to power the real evaluation history fetch.
  pipeline_id: string;
  // Real field, was missing from this type despite score.py always returning
  // it — added 12-Jul-2026 while building /dashboard/[id] polling logic.
  // pending_approval (P0.5, 12-Jul-2026): a HITL-band score (0.70-0.84) pauses
  // the graph at the `hitl` node awaiting POST /approve/{run_id} -- Deployer
  // has NOT run yet. Distinct from "completed", which previously covered this
  // case incorrectly (a paused, undeployed run is not actually finished).
  status: "pending" | "running" | "completed" | "blocked" | "failed" | "pending_approval";
  // Nullable (13-Jul-2026 fix): a run that fails before Evaluator ever runs
  // (e.g. an ingestion/embedding error) genuinely has no score yet -- the API
  // returns null, not a fabricated 0. Every consumer must check for null
  // before calling .toFixed()/scoreBand() -- see RootCausePanel.tsx,
  // EvaluationDashboard.tsx for the real crash this caused (Part G/H UI walkthrough).
  unified_score: number | null; // gate: >= 0.85
  // P0.6-3 (13-Jul-2026): nullable — recall/quality are real Numeric columns
  // that stayed unpopulated on every row until this fix; still null on rows
  // from before it shipped, and on runs that failed before Evaluator's
  // Step 6 ever computed them. Never render a null as 0 — check value_types.
  recall: number | null;
  quality: number | null;
  // Nullable (13-Jul-2026 fix, same audit as unified_score): backend column
  // `evaluation_run.faithfulness` is `Numeric(4,3) nullable=True`
  // (app/models/evaluation_run.py), null whenever a run fails before
  // Evaluator's Step 6. Never call .toFixed() without a null check.
  faithfulness: number | null; // < 0.5 = hard block
  // Nullable (13-Jul-2026 fix): backend column is `int | None`
  // (app/models/evaluation_run.py), passed through score.py with no
  // null-coalescing. A null here must render "Not collected", never a
  // literal "nullms" string or silently pass an SLA comparison.
  latency_p95_ms: number | null; // < 3000ms required
  adversarial_passed: boolean;
  // Loosely typed: also carries evaluation_mode (string), recall_at_5_measured
  // (boolean), and score_provenance (object) alongside the numeric RAGAS
  // metrics — see evaluation_mode/score_provenance below for the typed views.
  ragas_metrics: Record<string, unknown>;
  failure_taxonomy: string[];
  // Rule 86 cost fields — populated by LLMService, aggregated by Evaluator.
  // total_tokens/llm_provider_used are null until evaluation_runs gains
  // dedicated columns (currently only cost_usd/cost_per_query_usd are tracked).
  cost_per_query_usd: number | null;
  total_tokens: number | null;
  llm_provider_used: "gemini-flash-3.5" | "kimi-k2.6" | "gemini-3.5" | null;
  // 12-Jul-2026 (Part A/B): real per-node status/timing, absent/null for
  // pre-migration-0010 runs or runs where the graph never invoked a node.
  // Optional (not just nullable) so existing test fixtures built before this
  // field existed don't all need updating to add an explicit null.
  node_trace?: NodeTraceEntry[] | null;
  // P0.6-1 (13-Jul-2026): FULL when the 4 ground-truth-dependent ranking
  // metrics (recall_at_5/recall_at_10/mrr/ndcg) were genuinely measured;
  // DIAGNOSTIC when they're NOT_COLLECTED. Does not gate unified_score —
  // its "Recall" input is RAGAS context_recall, measured every run. null on
  // pre-P0.6 rows. Optional for the same test-fixture reason as node_trace.
  evaluation_mode?: "FULL" | "DIAGNOSTIC" | null;
  // P0.6-3: full evidence trail behind unified_score — null on pre-P0.6 rows.
  score_provenance?: ScoreProvenance | null;
  // P0.6-3: per-field provenance classification — the UI must render this
  // explicitly (a MEASURED/DERIVED badge, or "Unavailable" for
  // NOT_COLLECTED), never silently treat a missing value as 0. Optional for
  // the same pre-P0.6-row/test-fixture reason as node_trace.
  value_types?: Record<string, ValueType>;
  // V4 fast-follow (26-Jul-2026): real GraphState values that were always
  // computed but previously discarded before persistence -- null for rows
  // created before this change. See evaluation_dispatch.py's
  // build_retrieved_context_preview() docstring.
  retrieved_context_preview?: RetrievedContextPreviewChunk[] | null;
  generated_answer?: string | null;
}

/** Safe, truncated preview of a retrieved chunk (evaluation_dispatch.py's
 * build_retrieved_context_preview(), mirrors RetrievedChunkOut's shape). */
export interface RetrievedContextPreviewChunk {
  chunk_id: string | null;
  rank: number;
  retrieval_score: number | null;
  rerank_score: number | null;
  source_uri: string | null;
  page_number: number | null;
  chunk_strategy: "semantic" | "hierarchical" | "late" | null;
  preview: string;
}

/** MEASURED/DERIVED/ESTIMATED/NOT_COLLECTED provenance discipline (P0.6-3). */
export type ValueType = "MEASURED" | "DERIVED" | "ESTIMATED" | "NOT_COLLECTED";

/** evaluation_service.build_score_provenance()'s persisted shape (P0.6-3). */
export interface ScoreProvenance {
  recall_input: number;
  quality_input: number;
  faithfulness_input: number;
  latency_p95_ms_input: number;
  latency_penalty: number;
  cost_usd_input: number;
  cost_penalty: number;
  unified_score: number;
  formula_version: string;
  evaluation_mode: "FULL" | "DIAGNOSTIC";
  weights: {
    recall: number;
    quality: number;
    faithfulness: number;
    latency: number;
    cost: number;
  };
}

/**
 * One GraphState.execution_trace entry, persisted verbatim into
 * evaluation_runs.agent_execution_metadata.node_trace (Part A, 12-Jul-2026).
 * Not every field is present on every node (e.g. cost_usd/provider only on
 * LLM-calling nodes) — treat absent fields as "not collected", never as 0.
 */
export interface NodeTraceEntry {
  node: string;
  status: string;
  timestamp: string;
  latency_ms: number;
  x_trace_id: string;
  retry_count: number;
  cost_usd?: number;
  provider?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  [key: string]: unknown; // node-specific extras (chunks_indexed, retrieval_strategy, etc.)
}

/** GET /observe — real Observer signals (Part B.2, 12-Jul-2026). */
export interface ObserverSignals {
  error_rate: number | null;
  quality_trend: "improving" | "stable" | "degrading" | null;
  alert_triggered: boolean | null;
  observation_flags: {
    latency_breach: boolean;
    score_drop: boolean;
    error_spike: boolean;
    quality_drift: boolean;
  } | null;
}

export interface ObserverHistoryEntry {
  run_id: string;
  unified_score: number | null;
  cost_usd: number | null;
  latency_p95_ms: number | null;
  status: string;
  created_at: string | null;
}

export interface ObserverViewResponse {
  pipeline_id: string;
  latest_run_id: string | null;
  signals: ObserverSignals | null;
  history: ObserverHistoryEntry[];
  history_note: string | null;
}

/**
 * One Improver candidate — all 3 real scored variants, not just the winner
 * (Part A/B.3, 12-Jul-2026). score_type is always "estimated": the Improver's
 * unified_score is a deterministic heuristic, not a live re-evaluation.
 */
export interface ImproverCandidate {
  candidate_id: string;
  config: Record<string, unknown>;
  score: number;
  score_type: "estimated";
  score_delta: number;
  selected: boolean;
  mlflow_run_id: string | null;
}

export interface ImprovementResponse {
  run_id: string;
  pipeline_id: string;
  status: string;
  current_score: number | null;
  variant_id: string | null;
  variant_config: Record<string, unknown> | null;
  improvement_attempt: number;
  score_delta: number | null;
  candidates: ImproverCandidate[] | null;
  message: string;
}

/**
 * POST /pipelines/{id}/apply-improvement (20-Jul-2026, Apply Improvement
 * feature) — applies a real Improver candidate, rebuilds, and dispatches a
 * fresh re-evaluation in the background. new_score is always null on the
 * initial response -- poll GET /jobs/{job_id}, then GET /pipelines/{id}/versions
 * for the real (possibly worse, never fabricated) result.
 */
export interface ConfigDiffEntry {
  field: string;
  from_value: unknown;
  to_value: unknown;
}

export interface ApplyImprovementResponse {
  experiment_run_id: string;
  job_id: string;
  pipeline_id: string;
  new_version: number;
  old_score: number | null;
  config_diff: ConfigDiffEntry[];
  status: string;
}

/** GET /pipelines/{id}/versions — one row per real pipeline_versions entry. */
export interface PipelineVersionSummary {
  version_number: number;
  chunk_strategy: string;
  embedding_model: string;
  config_snapshot: Record<string, unknown> | null;
  unified_score: number | null;
  // Real per-version metrics (20-Jul-2026, migration 0015) -- sourced from
  // the evaluation_runs row linked via the experiment_runs row that applied
  // this version. Null for a version with no completed evaluation yet
  // (e.g. v1, created before any apply-improvement flow existed) -- never
  // a fabricated placeholder.
  recall: number | null;
  latency_p95_ms: number | null;
  cost_usd: number | null;
  score_delta: number | null;
  vector_table_name: string;
  created_at: string | null;
}

/** POST /pipelines/{id}/rollback — points the pipeline back at an earlier
 * version's config. Never touches vector tables (each version's table is
 * isolated) -- a safe, real, reversible manual undo. */
export interface RollbackResponse {
  pipeline_id: string;
  current_version: number;
}

export interface PipelineVersionsResponse {
  pipeline_id: string;
  versions: PipelineVersionSummary[];
}

/** One agent_metrics row — real per-LLM-call data (Part B.0, 12-Jul-2026). */
export interface AgentMetricCall {
  agent_name: string;
  provider: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number | null;
  latency_ms: number;
  created_at: string | null;
}

/**
 * GET /diagnose/{run_id} — real Diagnoser output (Part E rewiring, 12-Jul-2026).
 * confidence/remediation_hint/root_cause_analysis are null until the Diagnoser
 * node actually runs for this evaluation run — never fabricate a value.
 */
export interface DiagnosisResponse {
  run_id: string;
  pipeline_id: string;
  status: string;
  unified_score: number | null;
  failure_type: "F-01" | "F-02" | "F-03" | "F-04" | "F-05" | "F-06" | null;
  failure_description: string | null;
  confidence: number | null;
  remediation_hint: string | null;
  root_cause_analysis: string | null;
  ragas_metrics: Record<string, number>;
}

export interface RunMetricsResponse {
  run_id: string;
  calls: AgentMetricCall[];
  totals: {
    cost_usd: number | null;
    total_tokens: number | null;
    llm_calls: number;
  };
}

/** GET /api/v1/experiments — one row per evaluation_runs row (Part E, 12-Jul-2026). */
export interface ExperimentApiRecord {
  run_id: string;
  pipeline_id: string;
  unified_score: number | null;
  score_delta: number | null;
  recall: number | null;
  faithfulness: number | null;
  quality: number | null;
  latency_p95_ms: number | null;
  cost_usd: number | null;
  status: string;
  created_at: string | null;
}

export interface ExperimentsListResponse {
  experiments: ExperimentApiRecord[];
  total: number;
  limit: number;
  offset: number;
}

/** GET /api/v1/evaluate/history — real per-pipeline evaluation run history. */
export interface EvaluationHistoryItem {
  run_id: string;
  status: string;
  unified_score: number | null;
  faithfulness: number | null;
  adversarial_passed: boolean;
  dataset_version: string | null;
  created_at: string | null;
}

export interface EvaluationHistoryResponse {
  items: EvaluationHistoryItem[];
  limit: number;
  offset: number;
}

export interface AuditEvent {
  id: string;
  event_type: string;
  run_id: string | null;
  organization_id: string | null;
  x_trace_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

/** GET /jobs/{job_id} (API_SPEC.md § Jobs). */
export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  progress?: number;
  result?: Record<string, unknown> | null;
  error?: string | null;
  started_at?: string;
  finished_at?: string | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Configurator wizard (E-5) — API_SPEC.md #1 POST /configurator, #2 POST /ingest
// ─────────────────────────────────────────────────────────────────────────────

/** POST /ingest (multipart) response — Step 1 document upload (API_SPEC #2). */
export interface IngestResponse {
  document_id: string | null;
  document_ids: string[];
  chunk_count: number;
  /** Categories of PII the masker flagged at ingestion (never the raw values). */
  pii_detected: string[];
  job_id: string;
  status: JobStatus;
}

/** POST /configurator request — one step at a time (API_SPEC #1). */
export interface ConfiguratorStepRequest {
  step: number;
  project_id: string;
  data: Record<string, unknown>;
}

/** POST /configurator response — threads pipeline_id + drives next step. */
export interface ConfiguratorStepResponse {
  step: number;
  pipeline_id: string;
  /** Backend-driven next step; null signals the wizard is complete. */
  next_step: number | null;
  yaml_preview: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Retrieval Explorer — POST /api/v1/retrieve (retrieval-only inspection,
// added 13-Jul-2026 to replace the previous type shape, which never matched
// what any real backend route returned — GET /api/v1/query is the
// production answer-generation endpoint and only ever returned
// {answer, citations, retrieval_count, latency_ms}. This shape matches
// app/schemas/retrieval.py's RetrieveRequest/RetrieveResponse verbatim —
// no rewrite_time_ms/search_time_ms/etc breakdown, since the backend never
// computes per-sub-stage timing that granular.
// ─────────────────────────────────────────────────────────────────────────────

/** POST /api/v1/retrieve request body. */
export interface RetrievalRequest {
  pipeline_id: string;
  query: string;
  top_k?: number;
}

/** One stage of the real retrieval pipeline this endpoint actually runs
 * (query rewrite is currently a pass-through — see RetrieveResponse.rewritten_query). */
export interface RetrievalStage {
  stage_name: "rewrite" | "embedding" | "dense_search" | "bm25" | "hybrid_merge" | "reranker";
  status: "completed" | "failed" | "skipped";
  latency_ms: number;
}

/** Safe chunk-level inspection metadata — preview is truncated, never the
 * full persisted chunk text (P0.7 audit-safety discipline extended here). */
export interface RetrievedChunk {
  chunk_id: string;
  /** Derived from a real storage_path/source_uri match against the
   * documents table — null (never fabricated) when no match is found. */
  document_id: string | null;
  rank: number;
  /** Pre-rerank RRF fusion score. */
  retrieval_score: number | null;
  /** Post-rerank cross-encoder score — null only if rerank itself failed
   * (RerankService degrades to passthrough, never fabricates a score). */
  rerank_score: number | null;
  rerank_provider: "cohere" | "bge" | "none" | null;
  source_uri: string;
  page_number?: number | null;
  chunk_strategy: ChunkStrategy | null;
  preview: string;
}

/** POST /api/v1/retrieve response payload — matches app/schemas/retrieval.py's
 * RetrieveResponse. Recall@5 follows the same MEASURED/NOT_COLLECTED
 * discipline as ScoreResult (P0.6-1) — never a fabricated 0.5. */
export interface RetrievalResult {
  raw_query: string;
  rewritten_query: string;
  retrieval_strategy: "hybrid_rrf";
  retrieved_chunks: RetrievedChunk[];
  retrieved_ids: string[];
  /** Only populated when curated ground truth exists (golden-path demo
   * document today) — null (NOT_COLLECTED) otherwise, never guessed. */
  relevant_ids: string[] | null;
  recall_at_5: number | null;
  recall_at_5_measured: boolean;
  evaluation_mode: "FULL" | "DIAGNOSTIC";
  stages: RetrievalStage[];
  total_latency_ms: number;
  x_trace_id: string;
}

/** GET /api/v1/query response — a real LLM-generated grounded answer, never
 * a confidence score, faithfulness, or "chunks used" breakdown (those need
 * a real Evaluator run and don't exist on this endpoint). */
export interface QueryAnswerCitation {
  source: string;
  page: number | null;
}

export interface QueryAnswerResult {
  answer: string;
  citations: QueryAnswerCitation[];
  retrieval_count: number;
  latency_ms: number;
  pipeline_id: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Deployment Center (E-12) — Chapter 24. Mirrors the real `deployments` table
// enum (models/deployment.py ck_deployments_status) — NOT the stale
// queued/deploying/healthy vocabulary in API_SPEC.md, which was never wired up.
// ─────────────────────────────────────────────────────────────────────────────

export type DeploymentStatus = "pending" | "blue_green" | "promoted" | "rolled_back" | "failed";

/** A single deployments-table row, as returned by /api/v1/deploy/{status,history}. */
export interface Deployment {
  id: string;
  pipeline_id: string;
  status: DeploymentStatus;
  task_arn: string;
  rollback_task_arn: string | null;
  unified_score_at_deploy: number | null;
  deployed_at: string | null;
  promoted_at: string | null;
  rolled_back_at: string | null;
  created_at: string;
}

/** POST /api/v1/deploy/{run_id} request body. */
export interface DeployRequest {
  task_arn: string;
  approval_token?: string;
}

/** POST /api/v1/deploy/rollback request body. */
export interface RollbackRequest {
  pipeline_id: string;
  rollback_reason: string;
}

/** POST /api/v1/deploy/promote request body. */
export interface PromoteRequest {
  pipeline_id: string;
}

/** GET /api/v1/deploy/history response payload. */
export interface DeploymentHistoryResponse {
  pipeline_id: string;
  deployments: Deployment[];
}

/** GET /api/v1/deploy/status response payload. */
export interface DeploymentStatusResponse {
  pipeline_id: string;
  deployment: Deployment | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Audit Logs (E-13) — Chapter 25. Mirrors the real `audit_log` table
// (models/audit_log.py APPROVED_EVENT_TYPES) — NOT the richer severity/user/IP
// vocabulary in Chapter 25 or the stale `days` param in API_SPEC.md, neither of
// which the real GET /api/v1/audit-log route supports.
// ─────────────────────────────────────────────────────────────────────────────

/**
 * 14 approved event types, verbatim from `app/models/audit_log.py`.
 * Keep in sync manually — no `/audit/categories` endpoint exists to source this from.
 * pii_redacted added 13-Jul-2026 (P0.7-2, migration 0011) — was previously
 * emitted by the backend but unfilterable/unbadged here (real gap, not a
 * design choice).
 */
export const APPROVED_AUDIT_EVENT_TYPES = [
  "pipeline_created",
  "pipeline_updated",
  "ingest_started",
  "ingest_completed",
  "eval_started",
  "eval_completed",
  "deploy_started",
  "deploy_completed",
  "rollback_triggered",
  "hitl_approved",
  "hitl_rejected",
  "cost_limit_exceeded",
  "guardrail_blocked",
  "pii_redacted",
] as const;

export type AuditEventType = (typeof APPROVED_AUDIT_EVENT_TYPES)[number];

/** GET /api/v1/audit-log query params (route: app/routes/audit_log.py). */
export interface AuditLogListParams {
  event_type?: AuditEventType;
  run_id?: string;
  limit?: number;
  offset?: number;
}

/** GET /api/v1/audit-log response `data` payload. */
export interface AuditLogListResponse {
  items: AuditEvent[];
  limit: number;
  offset: number;
  count: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Diagnoser Workspace (F-14) — Chapter 28. GET /api/v1/diagnose/{run_id} (routes/
// diagnose.py) is real and working since the 12-Jul-2026 Part E fix — apiClient.
// getDiagnosis() calls it for confidence/remediation_hint/root_cause_analysis.
// This feature also cross-references GET /api/v1/score/{run_id} (apiClient.
// getScore), whose `failure_taxonomy` field is the persisted Diagnoser/Evaluator
// output (evaluation_runs.failure_taxonomy).
// ─────────────────────────────────────────────────────────────────────────────

/**
 * 6-code failure taxonomy, transcribed verbatim from the real Diagnoser node
 * (autorag-server/app/graph/nodes/diagnoser.py docstring). F-06 added 12-Jul-2026
 * (was already real in the backend since G-6/Plan v4 but missing here — same
 * class of drift as the now-fixed GraphState.failure_type Literal).
 */
export type FailureCode = "F-01" | "F-02" | "F-03" | "F-04" | "F-05" | "F-06";

export const FAILURE_CODE_INFO: Record<FailureCode, { label: string; description: string }> = {
  "F-01": { label: "Retrieval Miss", description: "Retrieved chunks were empty or all low-relevance." },
  "F-02": { label: "Context Overflow", description: "Compressed context exceeded the token budget." },
  "F-03": { label: "Hallucination", description: "Faithfulness fell below the safety threshold." },
  "F-04": { label: "Answer Incomplete", description: "Low answer quality despite grounded retrieval." },
  "F-05": { label: "Latency Spike", description: "p95 response latency exceeded the 3s SLA." },
  "F-06": { label: "Quality Drift", description: "Sustained multi-run score decline (not a single acute drop)." },
};

/** Type guard — `ScoreResult.failure_taxonomy` is untyped `string[]` at the API boundary. */
export function isFailureCode(value: string): value is FailureCode {
  return value in FAILURE_CODE_INFO;
}

// ─────────────────────────────────────────────────────────────────────────────
// Documents Management (F-17)
// ─────────────────────────────────────────────────────────────────────────────

/** Document processing status. */
export type DocumentStatus =
  | "uploaded"
  | "validating"
  | "chunking"
  | "embedding"
  | "indexed"
  | "failed"
  | "archived";

/** Supported file MIME types. */
export type FileType =
  | "application/pdf"
  | "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
  | "text/plain"
  | "text/markdown"
  | "text/html"
  | "text/csv";

/** Document schema from API_SPEC.md § Document. */
export interface Document {
  id: string;
  project_id: string;
  file_name: string;
  version: number;
  storage_bucket: string;
  storage_path: string;
  mime_type: string;
  file_size: number; // bytes
  uploaded_by: string;
  uploaded_at: string;
  status: DocumentStatus;
  created_at: string;
  // Real per-document ingestion evidence (migration 0012, P0.7 follow-up,
  // 13-Jul-2026) -- persisted by ingestion_node once this document's real
  // pages are parsed/masked, never reconstructed from run history. null
  // page_count/char_count means "not yet measured," never a fabricated 0.
  page_count: number | null;
  char_count: number | null;
  pii_redaction_count: number;
  pii_counts_by_type: Record<string, number>;
}

/** GET /api/v1/documents/{id} detail response. */
export interface DocumentDetail extends Document {
  chunk_count: number;
  indexed_chunks: number;
  failed_chunks: number;
  embedding_status: "pending" | "processing" | "complete" | "failed";
  tags?: string[];
  categories?: string[];
  metadata: Record<string, unknown>;
}

/** GET /api/v1/documents list response (API_SPEC.md § GET /documents). */
export interface DocumentsListResponse {
  documents: Document[];
  total: number;
  limit: number;
  offset: number;
}

/** Upload progress tracking (client-side state). */
export interface UploadProgress {
  /** Unique per upload attempt -- NOT derived from file_name, so re-uploading (or retrying)
   * the same file produces distinct rows instead of colliding on React key / status updates. */
  upload_id: string;
  file_name: string;
  file_size: number;
  progress: number; // 0-100
  status: "pending" | "uploading" | "processing" | "complete" | "failed";
  document_id?: string;
  error?: string;
}

/** Processing pipeline stage (Chapter 31.12). */
export interface ProcessingStage {
  stage: "uploaded" | "validating" | "chunking" | "embedding" | "indexed";
  status: "pending" | "active" | "complete" | "failed";
  started_at?: string;
  completed_at?: string;
  error?: string;
}

/**
 * Document list filters with pagination and sorting support.
 * Phase 4: Added page, page_size, sort_by, sort_order.
 */
export interface DocumentFilters {
  search?: string;
  status?: DocumentStatus;
  mime_type?: FileType;
  uploaded_after?: string;
  uploaded_before?: string;
  min_size?: number;
  max_size?: number;
  // Phase 4: Pagination and sorting
  page?: number;
  page_size?: number;
  sort_by?: "file_name" | "uploaded_at" | "file_size" | "status";
  sort_order?: "asc" | "desc";
}

// ─────────────────────────────────────────────────────────────────────────────
// Phase 2 Types — Processing Status & Bulk Operations (Chapter 31.12, 31.14)
// ─────────────────────────────────────────────────────────────────────────────

/** Detailed processing status response from GET /documents/{id}/status. */
export interface ProcessingStatusResponse {
  document_id: string;
  current_stage: DocumentStatus;
  stages: ProcessingStageDetail[];
  overall_progress: number; // 0-100
  estimated_completion?: string; // ISO timestamp
  error_message?: string;
}

/** Individual stage detail with timing and progress. */
export interface ProcessingStageDetail {
  stage: "uploaded" | "validating" | "chunking" | "embedding" | "indexed" | "failed";
  status: "pending" | "active" | "complete" | "failed";
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
  progress?: number; // 0-100 for current stage
  chunks_processed?: number;
  chunks_total?: number;
  error?: string;
}

/** Bulk operation request payload. */
export interface BulkOperationRequest {
  document_ids: string[];
  operation: "delete" | "archive" | "reprocess" | "assign_tags" | "assign_pipeline";
  metadata?: Record<string, unknown>; // For tags/pipeline assignment
}

/** Bulk operation response. */
export interface BulkOperationResponse {
  job_id: string;
  total_documents: number;
  status: "queued" | "processing" | "completed" | "failed";
  results?: {
    succeeded: string[]; // document IDs
    failed: string[]; // document IDs
  };
  error?: string;
}

/** CSV metadata export structure. */
export interface DocumentMetadataExport {
  id: string;
  file_name: string;
  mime_type: string;
  file_size: number;
  status: DocumentStatus;
  uploaded_at: string;
  uploaded_by: string;
  chunk_count?: number;
  tags?: string[];
  categories?: string[];
  pipeline_id?: string;
}

// ─────────────────────────────────────────────────────────────────────────
// Evaluation Center — Golden Datasets & Batch Evaluation (24-Jul-2026)
// Backend: app/routes/evaluation_datasets.py, app/routes/batch_evaluations.py
// ─────────────────────────────────────────────────────────────────────────

export type DatasetLifecycleStatus = "draft" | "under_review" | "published" | "archived";
export type QuestionReviewStatus = "draft" | "under_review" | "approved" | "rejected" | "archived";
export type ResultReviewStatus = "unreviewed" | "approved" | "rejected" | "corrected";
export type BatchRunStatus = "queued" | "running" | "completed" | "cancelled" | "failed";
export type BatchEvaluationStatus = "pending" | "running" | "completed" | "failed";
export type QuestionDifficulty = "easy" | "medium" | "hard" | "expert";

export interface EvaluationDataset {
  id: string;
  name: string;
  description: string | null;
  domain: string | null;
  tags: string[] | null;
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
}

export interface EvaluationDatasetVersion {
  id: string;
  dataset_id: string;
  version_label: string;
  notes: string | null;
  lifecycle_status: DatasetLifecycleStatus;
  created_at: string;
}

export interface GoldenQuestion {
  id: string;
  dataset_version_id: string;
  question: string;
  purpose: string | null;
  reference_answer: string | null;
  expected_context: string | null;
  reference_document_id: string | null;
  reference_pages: string | null;
  relevant_chunk_ids: string[] | null;
  category: string | null;
  difficulty: QuestionDifficulty | null;
  metric_focus: string | null;
  tags: string[] | null;
  review_status: QuestionReviewStatus;
  reviewer_id: string | null;
  reviewer_notes: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvaluationConfig {
  id: string;
  name: string;
  pipeline_id: string | null;
  retriever_strategy: string | null;
  reranker: string | null;
  embedding_model: string | null;
  top_k: number | null;
  chunk_size: number | null;
  judge_provider: string | null;
  judge_model: string | null;
  temperature: number | null;
  created_at: string;
}

export interface DatasetStatistics {
  question_counts: Partial<Record<QuestionReviewStatus, number>>;
  latest_version_label?: string;
  last_batch_run: {
    counts_by_status: Partial<Record<BatchEvaluationStatus, number>>;
    average_unified_score: number | null;
    low_score_count: number;
  } | null;
}

export interface BatchRun {
  id: string;
  dataset_version_id: string;
  pipeline_id: string;
  config_id: string | null;
  status: BatchRunStatus;
  started_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  created_at: string;
}

export interface BatchEvaluation {
  id: string;
  batch_run_id: string;
  golden_question_id: string;
  evaluation_run_id: string | null;
  status: BatchEvaluationStatus;
  review_status: ResultReviewStatus;
  unified_score: number | null;
  faithfulness: number | null;
  // V4 (26-Jul-2026): real failure reason -- null for rows created before
  // this change or rows that never failed. See migration 0019.
  error_message?: string | null;
  error_type?: string | null;
  failed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BatchRunSummary {
  batch_run: BatchRun;
  summary: {
    counts_by_status: Partial<Record<BatchEvaluationStatus, number>>;
    average_unified_score: number | null;
    low_score_count: number;
    // V4 (26-Jul-2026): per-metric averages across the batch -- optional so
    // pre-this-change callers/fixtures don't need updating. null per key
    // when no row in the batch has that metric (e.g. answer_correctness
    // with no ground truth seeded anywhere).
    metric_averages?: {
      faithfulness: number | null;
      context_recall: number | null;
      answer_relevancy: number | null;
      context_precision: number | null;
      answer_correctness: number | null;
    };
  };
  worst_scoring: BatchEvaluation[];
}

export interface ResultDetail extends BatchEvaluation {
  ragas_metrics?: Record<string, number | null> | null;
  agent_execution_metadata?: Record<string, unknown> | null;
  failure_taxonomy?: Record<string, unknown> | string[] | null;
}
