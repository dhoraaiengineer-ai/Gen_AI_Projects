import { AppShell } from "@/components/layout/AppShell";
import { BackButton } from "@/components/ui/back-button";
import { AgentDetailPageClient } from "@/components/agents/AgentDetailPageClient";

interface Props {
  params: Promise<{ agent: string }>;
}

export default async function AgentDetailPage({ params }: Props) {
  const { agent } = await params;
  return (
    <AppShell title={`Agent: ${agent.replace(/-/g, " ")}`}>
      <BackButton href="/agents" label="Back to Agents" className="mb-1" />
      <AgentDetailPageClient agentId={agent} />
    </AppShell>
  );
}
