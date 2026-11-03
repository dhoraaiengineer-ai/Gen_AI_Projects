import { AppShell } from "@/components/layout/AppShell";
import { PlaygroundPageClient } from "@/components/playground/PlaygroundPageClient";

export default function PlaygroundPage() {
  return (
    <AppShell
      title="Query Playground"
      description="Safely test end-to-end RAG responses before deploying your pipeline. Run queries, inspect retrieved context, and review answer quality without affecting production or the Unified Score gate."
    >
      <PlaygroundPageClient />
    </AppShell>
  );
}
