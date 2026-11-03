import { AppShell } from "@/components/layout/AppShell";
import { AdvancedFeaturePlaceholder } from "@/components/ui/advanced-feature-placeholder";

// EmbeddingExplorerPageClient (components/embeddings/) preserved untouched for
// future real wiring — see verification/releases/v4.0/audit/DEFERRED_BACKEND_WIRING.md.
export default function EmbeddingsPage() {
  return (
    <AppShell title="Embedding Explorer">
      <AdvancedFeaturePlaceholder
        feature="Embedding Explorer"
        relatedScreens={[
          { label: "Retrieval", href: "/retrieve" },
          { label: "Pipeline Progress", href: "/dashboard" },
        ]}
      />
    </AppShell>
  );
}
