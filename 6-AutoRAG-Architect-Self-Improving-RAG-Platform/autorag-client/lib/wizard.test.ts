import { describe, expect, it } from "vitest";

import type { IngestResponse } from "@/types";
import {
  canAdvance,
  initialWizardState,
  isStepValid,
  stepPayload,
  weightsSum,
  wizardReducer,
  type WizardState,
} from "@/lib/wizard";

const INGEST: IngestResponse = {
  document_id: "doc-123",
  document_ids: ["doc-123"],
  chunk_count: 42,
  pii_detected: ["email"],
  job_id: "job-1",
  status: "completed",
};

function uploaded(base: WizardState = initialWizardState()): WizardState {
  return wizardReducer(base, { type: "UPLOAD_SUCCESS", result: INGEST });
}

describe("wizardReducer — transitions", () => {
  it("starts at step 1 with an idle upload", () => {
    const s = initialWizardState();
    expect(s.currentStep).toBe(1);
    expect(s.upload.status).toBe("idle");
    expect(s.complete).toBe(false);
  });

  it("records upload lifecycle", () => {
    let s = wizardReducer(initialWizardState(), { type: "UPLOAD_START", fileName: "a.pdf" });
    expect(s.upload.status).toBe("uploading");
    s = wizardReducer(s, { type: "UPLOAD_SUCCESS", result: INGEST });
    expect(s.upload.status).toBe("done");
    expect(s.upload.result?.document_id).toBe("doc-123");
  });

  it("advances to next_step from the backend on SUBMIT_SUCCESS", () => {
    const s = wizardReducer(uploaded(), {
      type: "SUBMIT_SUCCESS",
      pipelineId: "pipe-9",
      nextStep: 2,
      yamlPreview: "name: x",
    });
    expect(s.currentStep).toBe(2);
    expect(s.pipelineId).toBe("pipe-9");
    expect(s.complete).toBe(false);
  });

  it("marks complete when next_step is null (final step)", () => {
    const at6 = { ...uploaded(), currentStep: 6 };
    const s = wizardReducer(at6, {
      type: "SUBMIT_SUCCESS",
      pipelineId: "pipe-9",
      nextStep: null,
      yamlPreview: "name: x",
    });
    expect(s.complete).toBe(true);
    expect(s.currentStep).toBe(6);
  });

  it("GO_TO_STEP only navigates backward, never forward", () => {
    const at3 = { ...uploaded(), currentStep: 3 };
    expect(wizardReducer(at3, { type: "GO_TO_STEP", step: 2 }).currentStep).toBe(2);
    // Forward jump is clamped to the current step.
    expect(wizardReducer(at3, { type: "GO_TO_STEP", step: 5 }).currentStep).toBe(3);
  });

  it("captures and clears submit errors", () => {
    let s = wizardReducer(uploaded(), { type: "SUBMIT_ERROR", error: "boom" });
    expect(s.error).toBe("boom");
    s = wizardReducer(s, { type: "SUBMIT_START" });
    expect(s.error).toBeNull();
    expect(s.submitting).toBe(true);
  });
});

describe("isStepValid — gating", () => {
  it("blocks step 1 until upload succeeds", () => {
    expect(isStepValid(initialWizardState(), 1)).toBe(false);
    expect(isStepValid(uploaded(), 1)).toBe(true);
  });

  it("validates retrieval_k bounds and integrality (step 3)", () => {
    const base = uploaded();
    const good = wizardReducer(base, { type: "SET_RETRIEVAL", patch: { retrieval_k: 5 } });
    expect(isStepValid(good, 3)).toBe(true);
    const tooBig = wizardReducer(base, { type: "SET_RETRIEVAL", patch: { retrieval_k: 99 } });
    expect(isStepValid(tooBig, 3)).toBe(false);
    const fractional = wizardReducer(base, { type: "SET_RETRIEVAL", patch: { retrieval_k: 3.5 } });
    expect(isStepValid(fractional, 3)).toBe(false);
  });

  it("requires scoring weights to sum to 1.00 (step 5)", () => {
    const base = uploaded();
    expect(isStepValid(base, 5)).toBe(true); // defaults sum to 1.0
    const broken = wizardReducer(base, { type: "SET_WEIGHT", key: "recall", value: 0.9 });
    expect(weightsSum(broken.evaluation.scoring_weights)).toBeGreaterThan(1);
    expect(isStepValid(broken, 5)).toBe(false);
  });

  it("rejects out-of-range gate (step 5)", () => {
    const bad = wizardReducer(uploaded(), { type: "SET_GATE", value: 1.5 });
    expect(isStepValid(bad, 5)).toBe(false);
  });
});

describe("canAdvance", () => {
  it("is false while submitting even when the step is valid", () => {
    const submitting = wizardReducer(uploaded(), { type: "SUBMIT_START" });
    expect(isStepValid(submitting, 1)).toBe(true);
    expect(canAdvance(submitting)).toBe(false);
  });
});

describe("stepPayload", () => {
  it("emits the document_id for step 1", () => {
    expect(stepPayload(uploaded(), 1)).toEqual({ document_id: "doc-123", chunk_count: 42 });
  });

  it("emits scoring weights + gate for step 5", () => {
    const payload = stepPayload(uploaded(), 5);
    expect(payload).toHaveProperty("unified_score_gate");
    expect(payload).toHaveProperty("scoring_weights");
  });
});
