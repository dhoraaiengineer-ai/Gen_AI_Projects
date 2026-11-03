import { AppShell } from "@/components/layout/AppShell";
import { ExperimentsPageClient } from "@/components/experiments/ExperimentsPageClient";

/**
 * /experiments -- Experiments module (F-16).
 * Server component: wraps AppShell + defers the experiment UI to the client.
 * Experiments comparison (F-16).
 */
export default function ExperimentsPage() {
  return (
    <AppShell
      title="Experiments"
      description="Compare pipeline versions, analyze evaluation metrics, benchmark retrieval quality, and promote the best-performing experiment to production."
    >
      <ExperimentsPageClient />
    </AppShell>
  );
}
