import { AppShell } from "@/components/layout/AppShell";
import { AdvancedFeaturePlaceholder } from "@/components/ui/advanced-feature-placeholder";

// ChunkExplorerPageClient (components/chunks/) preserved untouched for future
// real wiring — see verification/releases/v4.0/audit/DEFERRED_BACKEND_WIRING.md.
export default function ChunksPage() {
  return (
    <AppShell title="Chunk Explorer">
      <AdvancedFeaturePlaceholder
        feature="Chunk Explorer"
        relatedScreens={[
          { label: "Documents", href: "/documents" },
          { label: "Retrieval", href: "/retrieve" },
        ]}
      />
    </AppShell>
  );
}
