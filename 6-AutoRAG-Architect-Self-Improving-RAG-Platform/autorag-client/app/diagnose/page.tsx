import { AppShell } from "@/components/layout/AppShell";
import { DiagnoserWorkspace } from "@/components/diagnoser/DiagnoserWorkspace";

/**
 * /diagnose — Diagnoser Workspace (F-14).
 * Server component: wraps AppShell + defers all interactivity to DiagnoserWorkspace.
 * Diagnoser Workspace (F-14).
 */
export default function DiagnosePage() {
  return (
    <AppShell
      title="Diagnoser Workspace"
      description="Failure classification, root cause, and recommended fixes for the selected pipeline's latest evaluation run."
    >
      <DiagnoserWorkspace />
    </AppShell>
  );
}
