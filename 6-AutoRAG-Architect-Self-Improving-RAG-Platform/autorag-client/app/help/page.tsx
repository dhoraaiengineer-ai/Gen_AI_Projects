import { AppShell } from "@/components/layout/AppShell";
import { HelpPageClient } from "@/components/help/HelpPageClient";

export default function HelpPage() {
  return (
    <AppShell
      title="Help & Documentation"
      description="AutoRAG Architect v3.0 — Enterprise Autonomous RAG Platform. Learn how to build, evaluate, improve, and deploy RAG pipelines."
    >
      <HelpPageClient />
    </AppShell>
  );
}
