import { AppShell } from "@/components/layout/AppShell";
import { PipelineEvolutionWorkspace } from "@/components/optimizer/PipelineEvolutionWorkspace";

export default function EvolutionPage() {
  return (
    <AppShell
      title="Evolution History"
      description="Real version history for every applied Improver recommendation — score, recall, latency, and cost per version, with a one-click rollback to any earlier version."
    >
      <PipelineEvolutionWorkspace />
    </AppShell>
  );
}
