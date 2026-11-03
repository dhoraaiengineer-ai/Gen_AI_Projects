import { AppShell } from "@/components/layout/AppShell";
import { SystemHealthPageClient } from "@/components/health/SystemHealthPageClient";

/**
 * /health — System Health Dashboard (F-19).
 * Server component: wraps AppShell + defers the live polling UI to the client.
 * System Health Dashboard (F-19).
 */
export default function HealthPage() {
  return (
    <AppShell
      title="System Health"
      description="Live platform health from the FastAPI /health probe. Auto-refreshes every 15s."
    >
      <SystemHealthPageClient />
    </AppShell>
  );
}
