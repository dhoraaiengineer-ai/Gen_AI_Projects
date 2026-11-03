import { AppShell } from "@/components/layout/AppShell";
import { AdvancedFeaturePlaceholder } from "@/components/ui/advanced-feature-placeholder";

// WorkflowView (components/workflow/) preserved untouched for future real
// wiring — see verification/releases/v4.0/audit/DEFERRED_BACKEND_WIRING.md. Real graph
// execution state already lives in Pipeline Progress.
export default function WorkflowPage() {
  return (
    <AppShell title="Workflow">
      <AdvancedFeaturePlaceholder
        feature="Workflow"
        relatedScreens={[{ label: "Pipeline Progress", href: "/dashboard" }]}
      />
    </AppShell>
  );
}
