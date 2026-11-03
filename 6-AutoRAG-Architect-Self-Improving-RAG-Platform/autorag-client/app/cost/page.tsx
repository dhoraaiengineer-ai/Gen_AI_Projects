import { AppShell } from "@/components/layout/AppShell";
import { AdvancedFeaturePlaceholder } from "@/components/ui/advanced-feature-placeholder";

// CostAnalyticsPageClient (components/cost/) preserved untouched for future
// real wiring — see verification/releases/v4.0/audit/DEFERRED_BACKEND_WIRING.md. Real
// per-run cost/token/provider data already lives in Pipeline Progress.
export default function CostPage() {
  return (
    <AppShell title="Cost Analytics">
      <AdvancedFeaturePlaceholder
        feature="Cost Analytics"
        relatedScreens={[{ label: "Pipeline Progress", href: "/dashboard" }]}
      />
    </AppShell>
  );
}
