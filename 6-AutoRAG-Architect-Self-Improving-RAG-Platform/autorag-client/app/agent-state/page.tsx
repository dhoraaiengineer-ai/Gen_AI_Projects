import { AppShell } from "@/components/layout/AppShell";
import { AdvancedFeaturePlaceholder } from "@/components/ui/advanced-feature-placeholder";

// AgentStatePageClient (components/agent-state/) preserved untouched for
// future real wiring — see verification/releases/v4.0/audit/DEFERRED_BACKEND_WIRING.md. Real
// per-agent execution state already lives in Pipeline Progress's node_trace.
export default function AgentStatePage() {
  return (
    <AppShell title="Agent State Viewer">
      <AdvancedFeaturePlaceholder
        feature="Agent State Viewer"
        relatedScreens={[{ label: "Pipeline Progress", href: "/dashboard" }]}
      />
    </AppShell>
  );
}
