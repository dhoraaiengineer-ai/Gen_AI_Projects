import { AppShell } from "@/components/layout/AppShell";
import { ObserverDashboardClient } from "@/components/observer/ObserverDashboardClient";

/**
 * /observe — Observer Dashboard (F-21).
 * Server component: wraps AppShell + defers the monitoring UI to the client.
 * Observer Dashboard (F-21).
 */
export default function ObservePage() {
  return (
    <AppShell
      title="Observer Dashboard"
      description="Production quality, latency, and cost across monitored pipelines — the first stage of the autonomous improvement loop. Observe only; never modifies pipelines."
    >
      <ObserverDashboardClient />
    </AppShell>
  );
}
