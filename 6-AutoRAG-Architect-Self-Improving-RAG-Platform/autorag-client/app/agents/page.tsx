import { AppShell } from "@/components/layout/AppShell";
import { AdvancedFeaturePlaceholder } from "@/components/ui/advanced-feature-placeholder";

// AgentsHubPageClient (components/agents/) preserved untouched for future
// real wiring — see verification/releases/v4.0/audit/DEFERRED_BACKEND_WIRING.md. Real
// per-agent status/latency/cost/tokens already lives in Pipeline Progress.
export default function AgentsPage() {
  return (
    <AppShell title="Agent Control Center">
      <AdvancedFeaturePlaceholder
        feature="Agent Control Center"
        relatedScreens={[{ label: "Pipeline Progress", href: "/dashboard" }]}
      />
    </AppShell>
  );
}
