import { Suspense } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { ImproverWorkspace } from "@/components/improver/ImproverWorkspace";

/**
 * /improve — Improver Workspace (F-15).
 * Server component: wraps AppShell + defers all interactivity to ImproverWorkspace.
 * Suspense boundary is required because ImproverWorkspace reads `?pipeline_id=`
 * via useSearchParams (Diagnoser deep-link).
 */
export default function ImprovePage() {
  return (
    <AppShell
      title="Improver Workspace"
      description="Turns the selected pipeline's latest failures into an optimized configuration variant, ready to route through Evaluation."
    >
      <Suspense
        fallback={<div className="h-40 animate-pulse rounded-xl border border-border bg-[rgba(15,23,42,0.06)]" />}
      >
        <ImproverWorkspace />
      </Suspense>
    </AppShell>
  );
}
