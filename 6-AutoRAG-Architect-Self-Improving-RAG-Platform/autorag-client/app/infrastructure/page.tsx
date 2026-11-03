import { AppShell } from "@/components/layout/AppShell";
import { AdvancedFeaturePlaceholder } from "@/components/ui/advanced-feature-placeholder";

// InfrastructurePageClient (components/infrastructure/) preserved untouched
// for future real wiring — see verification/releases/v4.0/audit/DEFERRED_BACKEND_WIRING.md.
export default function InfrastructurePage() {
  return (
    <AppShell title="Infrastructure Dashboard">
      <AdvancedFeaturePlaceholder
        feature="Infrastructure Dashboard"
        relatedScreens={[{ label: "System Health", href: "/health" }]}
      />
    </AppShell>
  );
}
