"use client";
// Presenter: runs a question through the streaming API and derives view state for the chat.
import { useCallback, useRef, useState } from "react";

import { ApiError, api } from "@/lib/api";
import type { Report, StreamEvent } from "@/types";

export interface TimelineItem {
  id: string;
  at: number; // seconds since the question was sent
  label: string;
  detail?: string;
  status: "running" | "ok" | "partial" | "failed" | "info";
}

export interface ChatTurn {
  question: string;
  timeline: TimelineItem[];
  narrative: string;
  report: Report | null;
  error: string | null;
  running: boolean;
  ttfeMs: number | null;
  ttftMs: number | null;
}

const AGENT_LABEL: Record<string, string> = {
  portfolio: "Portfolio agent",
  market: "Market agent",
  risk: "Risk agent",
  compliance: "Compliance agent",
  fraud: "Fraud agent",
  research: "Research agent (knowledge base)",
  prediction: "Prediction agent (ML)",
};

export function useChat(token: string | null) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  const update = (fn: (turn: ChatTurn) => ChatTurn) =>
    setTurns((all) => [...all.slice(0, -1), fn(all[all.length - 1])]);

  const ask = useCallback(
    async (question: string) => {
      if (!token || !question.trim()) return;
      abort.current?.abort();
      abort.current = new AbortController();
      const started = performance.now();
      const at = () => (performance.now() - started) / 1000;
      setTurns((all) => [
        ...all,
        { question, timeline: [], narrative: "", report: null, error: null, running: true, ttfeMs: null, ttftMs: null },
      ]);
      const onEvent = (event: StreamEvent) => {
        update((turn) => {
          const next = { ...turn, timeline: [...turn.timeline] };
          if (next.ttfeMs === null && event.event !== "start") next.ttfeMs = Math.round(at() * 1000);
          switch (event.event) {
            case "guard":
              next.timeline.push({ id: "guard", at: at(), status: "failed", label: "Guardrail",
                detail: `${event.decision}${event.reason ? ` · ${event.reason.replaceAll("_", " ")}` : ""}` });
              break;
            case "approval":
              next.timeline.push({ id: "approval", at: at(), status: "partial", label: "Paused for human approval",
                detail: `${event.approval.draftOrders?.length ?? 0} draft orders · approval ${event.approval.approvalId?.slice(0, 8) ?? ""}` });
              break;
            case "classification":
              next.timeline.push({ id: "route", at: at(), status: "info", label: "Supervisor routed the question",
                detail: `${event.intent.replaceAll("_", " ")} · via ${event.method}${event.portfolio ? ` · ${event.portfolio}` : ""}` });
              break;
            case "plan":
              next.timeline.push({ id: "plan", at: at(), status: "info", label: "Plan",
                detail: event.stages.map((s) => s.join(" + ")).join("  →  ") || "no agents needed" });
              break;
            case "agent_start":
              next.timeline.push({ id: event.agent, at: at(), status: "running", label: AGENT_LABEL[event.agent] ?? event.agent });
              break;
            case "agent_end":
              next.timeline = next.timeline.map((item) =>
                item.id === event.agent
                  ? { ...item, status: (event.status as TimelineItem["status"]) ?? "ok",
                      detail: `${event.tools.join(", ")} · ${(event.durationMs / 1000).toFixed(1)}s · confidence ${Math.round(event.confidence * 100)}%` }
                  : item,
              );
              break;
            case "token":
              if (next.ttftMs === null) next.ttftMs = Math.round(at() * 1000);
              next.narrative += event.text;
              break;
            case "report":
              next.report = event.report;
              break;
            case "error":
              next.error = `${event.message} (request ${event.requestId ?? "n/a"})`;
              break;
            case "done":
              next.running = false;
              break;
          }
          return next;
        });
      };
      try {
        await api.streamChat(token, question, conversationId, (event) => {
          if (event.event === "conversation") setConversationId(event.conversationId);
          onEvent(event);
        }, abort.current.signal);
      } catch (e) {
        const message = e instanceof ApiError ? `${e.message}${e.requestId ? ` (request ${e.requestId})` : ""}` : String(e);
        update((turn) => ({ ...turn, error: message, running: false }));
      }
    },
    [token, conversationId],
  );

  const reset = useCallback(() => {
    abort.current?.abort();
    setTurns([]);
    setConversationId(null);
  }, []);

  return { turns, ask, reset, conversationId, running: turns.at(-1)?.running ?? false };
}
