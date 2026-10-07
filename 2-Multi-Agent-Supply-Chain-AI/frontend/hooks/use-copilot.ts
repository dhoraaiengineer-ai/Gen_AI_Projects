"use client";

import { useCallback, useRef, useState } from "react";
import type { AgentId, AgentRunStatus, ApprovalRequest, PipelineStep, RecommendationReport } from "@/types";
import { ApiError, getApi } from "@/lib/api";

export interface StepState {
  step: PipelineStep;
  status: AgentRunStatus;
  message: string;
  durationMs?: number;
}

/** Streaming quality metrics, measured client-side for every run (also recorded server-side). */
export interface StreamMetrics {
  /** time to first event of any kind — perceived responsiveness */
  ttfeMs?: number;
  /** time to first answer token */
  ttftMs?: number;
  totalMs?: number;
  tokens: number;
  tokensPerSec?: number;
}

export interface CopilotTurn {
  id: string;
  question: string;
  status: "running" | "done" | "error" | "cancelled";
  intent?: string;
  stages: AgentId[][];
  steps: Partial<Record<PipelineStep, StepState>>;
  streamedText: string;
  approval?: ApprovalRequest;
  report?: RecommendationReport;
  error?: { message: string; requestId?: string; retryable: boolean };
  startedAt: number;
  metrics: StreamMetrics;
}

const FIXED_STEPS: PipelineStep[] = ["guard", "classifier", "supervisor"];

/** Drives one Copilot conversation: consumes the event stream and folds it into per-turn state. */
export function useCopilot() {
  const [turns, setTurns] = useState<CopilotTurn[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  const update = useCallback((id: string, fn: (t: CopilotTurn) => CopilotTurn) => {
    setTurns((prev) => prev.map((t) => (t.id === id ? fn(t) : t)));
  }, []);

  const ask = useCallback(
    async (question: string) => {
      const text = question.trim();
      if (!text) return;
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const id = crypto.randomUUID();
      const initialSteps = Object.fromEntries(
        FIXED_STEPS.map((s) => [s, { step: s, status: "waiting" as const, message: "" }]),
      ) as CopilotTurn["steps"];
      setTurns((prev) => [
        ...prev,
        { id, question: text, status: "running", stages: [], steps: initialSteps, streamedText: "", startedAt: performance.now(), metrics: { tokens: 0 } },
      ]);

      try {
        const api = await getApi();
        const t0 = performance.now();
        let firstTokenAt: number | undefined;
        for await (const ev of api.streamCopilot({ message: text }, controller.signal)) {
          const elapsed = performance.now() - t0;
          update(id, (t) => (t.metrics.ttfeMs === undefined ? { ...t, metrics: { ...t.metrics, ttfeMs: Math.round(elapsed) } } : t));
          switch (ev.type) {
            case "plan":
              update(id, (t) => ({
                ...t,
                intent: ev.intent,
                stages: ev.stages,
                steps: {
                  ...t.steps,
                  ...Object.fromEntries(ev.agents.map((a) => [a, { step: a, status: "waiting", message: "Waiting" }])),
                  synthesizer: { step: "synthesizer", status: "waiting", message: "Waiting" },
                  validator: { step: "validator", status: "waiting", message: "Waiting" },
                },
              }));
              break;
            case "step":
              update(id, (t) => ({ ...t, steps: { ...t.steps, [ev.step]: { step: ev.step, status: ev.status, message: ev.message, durationMs: ev.durationMs } } }));
              break;
            case "token": {
              firstTokenAt ??= elapsed;
              const ttft = Math.round(firstTokenAt);
              const words = ev.text.trim() ? ev.text.trim().split(/\s+/).length : 0;
              update(id, (t) => ({
                ...t,
                streamedText: t.streamedText + ev.text,
                metrics: { ...t.metrics, ttftMs: ttft, tokens: t.metrics.tokens + words },
              }));
              break;
            }
            case "approval_required":
              update(id, (t) => ({ ...t, approval: ev.approval }));
              break;
            case "report": {
              const total = Math.round(elapsed);
              const streamSecs = firstTokenAt !== undefined ? Math.max((elapsed - firstTokenAt) / 1000, 0.001) : undefined;
              update(id, (t) => ({
                ...t,
                status: "done",
                report: ev.report,
                approval: ev.report.approval ?? t.approval,
                metrics: {
                  ...t.metrics,
                  totalMs: total,
                  tokensPerSec: streamSecs ? Math.round(t.metrics.tokens / streamSecs) : undefined,
                },
              }));
              break;
            }
            case "error":
              update(id, (t) => ({ ...t, status: "error", error: { message: ev.message, requestId: ev.requestId, retryable: true } }));
              break;
          }
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          update(id, (t) => ({ ...t, status: "cancelled" }));
          return;
        }
        const apiErr = err instanceof ApiError ? err : null;
        update(id, (t) => ({
          ...t,
          status: "error",
          error: {
            message: apiErr?.message ?? "The copilot couldn't complete this request.",
            requestId: apiErr?.requestId,
            retryable: apiErr?.retryable ?? true,
          },
        }));
      }
    },
    [update],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);
  const reset = useCallback(() => {
    abortRef.current?.abort();
    setTurns([]);
  }, []);
  const setApprovalStatus = useCallback(
    (turnId: string, status: ApprovalRequest["status"]) =>
      update(turnId, (t) => (t.approval ? { ...t, approval: { ...t.approval, status } } : t)),
    [update],
  );

  const running = turns.some((t) => t.status === "running");
  return { turns, ask, stop, reset, running, setApprovalStatus };
}
