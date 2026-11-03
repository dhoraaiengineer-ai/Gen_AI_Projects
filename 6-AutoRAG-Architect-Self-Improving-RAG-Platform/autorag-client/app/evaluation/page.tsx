import { Suspense } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { EvaluationCenterClient } from "@/components/evaluation/EvaluationCenterClient";

/**
 * /evaluation — Evaluation Center (Phase 2d, 24-Jul-2026).
 * Server component: wraps AppShell + defers all interactivity to
 * EvaluationCenterClient, which tabs between the original single-question
 * Evaluation Dashboard ("Run Evaluation") and the new golden-dataset batch
 * evaluation surfaces (Overview/Batch Runs/Live Monitor/Results/Failed
 * Questions/Compare Runs/Settings). No new top-level route.
 */
export default function EvaluationPage() {
  return (
    // 26-Jul-2026: EvaluationCenterClient no longer renders its own PageHeader
    // (moved to the shared AppShell/PageHero) -- hideHeaderBar removed.
    // Suspense: EvaluationCenterClient reads `?tab=` via useSearchParams
    // (25-Jul-2026, /evaluate deep-link fix) -- same requirement as
    // app/improve/page.tsx's ImproverWorkspace.
    <AppShell
      title="Evaluation Center"
      description="Evaluate retrieval and generation quality using golden datasets, benchmark runs, and RAG metrics before promoting a pipeline to production."
    >
      <Suspense
        fallback={<div className="h-40 animate-pulse rounded-xl border border-border bg-[rgba(15,23,42,0.06)]" />}
      >
        <EvaluationCenterClient />
      </Suspense>
    </AppShell>
  );
}
