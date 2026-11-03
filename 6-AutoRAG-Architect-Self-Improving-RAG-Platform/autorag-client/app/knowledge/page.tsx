import { AppShell } from "@/components/layout/AppShell";
import { KnowledgeBasePageClient } from "@/components/knowledge/KnowledgeBasePageClient";

/**
 * /knowledge — Knowledge Base (F-18).
 * Server component: wraps AppShell + defers all interactivity to the client
 * container.
 */
export default function KnowledgePage() {
  return (
    <AppShell
      title="Knowledge Base"
      description="Central hub for managing, organizing, and exploring enterprise knowledge. Documents are indexed here after ingestion and become available for semantic retrieval and AI-powered search."
      mode="builder"
    >
      <KnowledgeBasePageClient />
    </AppShell>
  );
}
