import { AppShell } from "@/components/layout/AppShell";
import { BackButton } from "@/components/ui/back-button";
import { PipelineRunView } from "@/components/dashboard/PipelineRunView";

/**
 * /dashboard/[id] — Pipeline Progress (Part D, 12-Jul-2026).
 * Previously did not exist despite being marked done elsewhere in the project
 * docs (corrected 12-Jul-2026 audit — see project_docs/PROJECT_TREE.md).
 * Server component: wraps AppShell + defers all interactivity to PipelineRunView.
 */
export default async function PipelineRunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <AppShell title="Pipeline Progress">
      <BackButton href="/dashboard" label="Back to Dashboard" className="mb-1" />
      <PipelineRunView pipelineId={id} />
    </AppShell>
  );
}
