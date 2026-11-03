/**
 * Configurator wizard state machine — pure, React-free, fully unit-testable.
 * The reducer owns all transitions; the ConfiguratorWizard component performs the
 * async API calls and dispatches their results here (Dev Notes "pure logic in lib/").
 *
 * Backend-driven flow (API_SPEC #1, Critical Gap #3): each step is persisted via
 * POST /configurator; the response threads `pipeline_id` + `next_step`. Step 1's
 * document upload goes to POST /ingest first (sets `upload.result.document_id`).
 */

import type { ChunkStrategy, IngestResponse, LLMProvider } from "@/types";

// ── Step metadata (SOT §9 — 6-step layout) ────────────────────────────────────

export interface WizardStepMeta {
  id: number;
  key: string;
  title: string;
}

export const WIZARD_STEPS: readonly WizardStepMeta[] = [
  { id: 1, key: "upload", title: "Upload" },
  { id: 2, key: "chunking", title: "Chunking" },
  { id: 3, key: "retrieval", title: "Retrieval" },
  { id: 4, key: "generation", title: "Generation" },
  { id: 5, key: "evaluation", title: "Evaluation" },
  { id: 6, key: "deploy", title: "Review & Deploy" },
] as const;

export const FIRST_STEP = 1;
export const LAST_STEP = WIZARD_STEPS.length; // 6

// ── Per-step config slices ────────────────────────────────────────────────────

export type UploadStatus = "idle" | "uploading" | "done" | "error";

export interface UploadSlice {
  status: UploadStatus;
  fileName: string | null;
  result: IngestResponse | null;
  error: string | null;
}

export interface RetrievalConfig {
  dense_weight: number; // 0..1
  hybrid_ratio: number; // 0..1
  reranker_enabled: boolean;
  retrieval_k: number; // 1..50 integer
}

export interface GenerationConfig {
  provider: LLMProvider;
  max_tokens: number; // 1..8192
  temperature: number; // 0..2
}

/** Unified Score weights — mirrors CLAUDE.md §9 default weighting. */
export interface ScoringWeights {
  recall: number;
  quality: number;
  faithfulness: number;
  latency: number;
  cost: number;
}

export interface EvaluationConfig {
  unified_score_gate: number; // 0..1, default 0.85
  scoring_weights: ScoringWeights;
}

export interface WizardState {
  currentStep: number;
  pipelineId: string | null;
  upload: UploadSlice;
  chunkStrategy: ChunkStrategy;
  retrieval: RetrievalConfig;
  generation: GenerationConfig;
  evaluation: EvaluationConfig;
  yamlPreview: string | null;
  /** A /configurator (or /ingest) request is in flight. */
  submitting: boolean;
  /** Last submit/transition error, surfaced inline by WizardShell. */
  error: string | null;
  /** Set once the final step (6) is persisted successfully. */
  complete: boolean;
}

// ── Initial state ─────────────────────────────────────────────────────────────

export const DEFAULT_SCORING_WEIGHTS: ScoringWeights = {
  recall: 0.25,
  quality: 0.35,
  faithfulness: 0.25,
  latency: 0.1,
  cost: 0.05,
};

export const DEFAULT_DEPLOY_GATE = 0.85;

export function initialWizardState(): WizardState {
  return {
    currentStep: FIRST_STEP,
    pipelineId: null,
    upload: { status: "idle", fileName: null, result: null, error: null },
    chunkStrategy: "semantic",
    retrieval: {
      dense_weight: 0.5,
      hybrid_ratio: 0.5,
      reranker_enabled: true,
      retrieval_k: 5,
    },
    generation: { provider: "gemini-flash-3.5", max_tokens: 1024, temperature: 0.2 },
    evaluation: {
      unified_score_gate: DEFAULT_DEPLOY_GATE,
      scoring_weights: { ...DEFAULT_SCORING_WEIGHTS },
    },
    yamlPreview: null,
    submitting: false,
    error: null,
    complete: false,
  };
}

// ── Actions ───────────────────────────────────────────────────────────────────

export type WizardAction =
  | { type: "UPLOAD_START"; fileName: string }
  | { type: "UPLOAD_SUCCESS"; result: IngestResponse }
  | { type: "UPLOAD_ERROR"; error: string }
  | { type: "SET_CHUNK_STRATEGY"; value: ChunkStrategy }
  | { type: "SET_RETRIEVAL"; patch: Partial<RetrievalConfig> }
  | { type: "SET_GENERATION"; patch: Partial<GenerationConfig> }
  | { type: "SET_GATE"; value: number }
  | { type: "SET_WEIGHT"; key: keyof ScoringWeights; value: number }
  | { type: "SUBMIT_START" }
  | { type: "SUBMIT_SUCCESS"; pipelineId: string; nextStep: number | null; yamlPreview: string }
  | { type: "SUBMIT_ERROR"; error: string }
  | { type: "GO_TO_STEP"; step: number };

// ── Reducer ───────────────────────────────────────────────────────────────────

export function wizardReducer(state: WizardState, action: WizardAction): WizardState {
  switch (action.type) {
    case "UPLOAD_START":
      return {
        ...state,
        upload: { status: "uploading", fileName: action.fileName, result: null, error: null },
      };
    case "UPLOAD_SUCCESS":
      return {
        ...state,
        upload: { ...state.upload, status: "done", result: action.result, error: null },
      };
    case "UPLOAD_ERROR":
      return {
        ...state,
        upload: { ...state.upload, status: "error", error: action.error },
      };
    case "SET_CHUNK_STRATEGY":
      return { ...state, chunkStrategy: action.value };
    case "SET_RETRIEVAL":
      return { ...state, retrieval: { ...state.retrieval, ...action.patch } };
    case "SET_GENERATION":
      return { ...state, generation: { ...state.generation, ...action.patch } };
    case "SET_GATE":
      return { ...state, evaluation: { ...state.evaluation, unified_score_gate: action.value } };
    case "SET_WEIGHT":
      return {
        ...state,
        evaluation: {
          ...state.evaluation,
          scoring_weights: { ...state.evaluation.scoring_weights, [action.key]: action.value },
        },
      };
    case "SUBMIT_START":
      return { ...state, submitting: true, error: null };
    case "SUBMIT_SUCCESS": {
      const isFinal = action.nextStep === null;
      return {
        ...state,
        submitting: false,
        error: null,
        pipelineId: action.pipelineId,
        yamlPreview: action.yamlPreview,
        complete: isFinal,
        currentStep: isFinal
          ? state.currentStep
          : clampStep(action.nextStep ?? state.currentStep + 1),
      };
    }
    case "SUBMIT_ERROR":
      return { ...state, submitting: false, error: action.error };
    case "GO_TO_STEP":
      // Back-navigation only — never jump forward past validation gates.
      return { ...state, currentStep: clampStep(Math.min(action.step, state.currentStep)), error: null };
    default:
      return state;
  }
}

function clampStep(step: number): number {
  if (step < FIRST_STEP) return FIRST_STEP;
  if (step > LAST_STEP) return LAST_STEP;
  return step;
}

// ── Validation (per-step gating) ──────────────────────────────────────────────

const WEIGHT_SUM_EPSILON = 0.001;

export function weightsSum(weights: ScoringWeights): number {
  return (
    weights.recall + weights.quality + weights.faithfulness + weights.latency + weights.cost
  );
}

function inRange(value: number, min: number, max: number): boolean {
  return Number.isFinite(value) && value >= min && value <= max;
}

/** True when the given step's required inputs are valid (advance is gated on this). */
export function isStepValid(state: WizardState, step: number = state.currentStep): boolean {
  switch (step) {
    case 1:
      return state.upload.status === "done" && state.upload.result !== null;
    case 2:
      return ["semantic", "hierarchical", "late"].includes(state.chunkStrategy);
    case 3: {
      const r = state.retrieval;
      return (
        inRange(r.dense_weight, 0, 1) &&
        inRange(r.hybrid_ratio, 0, 1) &&
        Number.isInteger(r.retrieval_k) &&
        inRange(r.retrieval_k, 1, 50)
      );
    }
    case 4: {
      const g = state.generation;
      return inRange(g.max_tokens, 1, 8192) && inRange(g.temperature, 0, 2);
    }
    case 5: {
      const e = state.evaluation;
      const weightsInRange = (Object.values(e.scoring_weights) as number[]).every((w) =>
        inRange(w, 0, 1),
      );
      const sumOk = Math.abs(weightsSum(e.scoring_weights) - 1) <= WEIGHT_SUM_EPSILON;
      return inRange(e.unified_score_gate, 0, 1) && weightsInRange && sumOk;
    }
    case 6:
      return true; // review step — always advanceable to Finish
    default:
      return false;
  }
}

/** Whether the current step may advance (Next/Finish enabled). */
export function canAdvance(state: WizardState): boolean {
  return !state.submitting && isStepValid(state, state.currentStep);
}

// ── Step payload builder (sent as `data` in POST /configurator) ────────────────

/** Pure mapping of the current step's slice → the `data` object for /configurator. */
export function stepPayload(state: WizardState, step: number = state.currentStep): Record<string, unknown> {
  switch (step) {
    case 1:
      return {
        document_id: state.upload.result?.document_id ?? null,
        chunk_count: state.upload.result?.chunk_count ?? 0,
      };
    case 2:
      return { chunk_strategy: state.chunkStrategy };
    case 3:
      return { retrieval_config: { ...state.retrieval } };
    case 4:
      return { generation_config: { ...state.generation } };
    case 5:
      return {
        unified_score_gate: state.evaluation.unified_score_gate,
        scoring_weights: { ...state.evaluation.scoring_weights },
      };
    case 6:
      return { finalize: true };
    default:
      return {};
  }
}
