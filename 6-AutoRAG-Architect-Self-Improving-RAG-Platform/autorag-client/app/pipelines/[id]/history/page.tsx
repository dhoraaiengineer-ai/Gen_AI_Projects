import { AppShell } from "@/components/layout/AppShell";
import { BackButton } from "@/components/ui/back-button";
import { PipelineHistoryPageClient } from "@/components/pipeline-history/PipelineHistoryPageClient";

interface Props {
  params: Promise<{ id: string }>;
}

/**
 * /pipelines/[id]/history — Pipeline Version History (F-20).
 * Server component: awaits the route param and hands the pipeline id to the
 * client container.
 */
export default async function PipelineHistoryPage({ params }: Props) {
  const { id } = await params;
  return (
    <AppShell title="Pipeline Version History" description="This pipeline's configuration and deployment history.">
      <BackButton href="/pipelines" label="Back to Pipelines" className="mb-1" />
      <PipelineHistoryPageClient pipelineId={id} />
    </AppShell>
  );
}
