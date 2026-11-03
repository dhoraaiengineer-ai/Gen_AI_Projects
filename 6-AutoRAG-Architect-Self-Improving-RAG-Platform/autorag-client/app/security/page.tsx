import { AppShell } from "@/components/layout/AppShell";
import { AdvancedFeaturePlaceholder } from "@/components/ui/advanced-feature-placeholder";

// SecurityPageClient (components/security/) preserved untouched for future
// real wiring — see verification/releases/v4.0/audit/DEFERRED_BACKEND_WIRING.md. Real
// guardrail-block events already live in the Audit Log.
export default function SecurityPage() {
  return (
    <AppShell title="Security Dashboard">
      <AdvancedFeaturePlaceholder
        feature="Security Dashboard"
        relatedScreens={[{ label: "Audit Log", href: "/audit" }]}
      />
    </AppShell>
  );
}
