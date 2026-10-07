"use client";

import { useState } from "react";
import { Pause, Play } from "lucide-react";
import type { ActivityEvent } from "@/types";
import { useActivity } from "@/hooks/use-api";
import { PageHeader } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Segmented } from "@/components/ui/data";
import { ActivityFeed } from "@/components/activity/activity-feed";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/shared/states";
import { StatusDot } from "@/components/shared/status";

type Filter = "all" | ActivityEvent["kind"];

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "detection", label: "Detections" },
  { value: "analysis", label: "Analyses" },
  { value: "workflow", label: "Workflows" },
  { value: "approval", label: "Approvals" },
  { value: "document", label: "Documents" },
];

export default function ActivityPage() {
  const { data, error, isLoading, refetch } = useActivity();
  const [filter, setFilter] = useState<Filter>("all");
  const [paused, setPaused] = useState(false);
  const [frozen, setFrozen] = useState<ActivityEvent[] | null>(null);

  const source = paused ? frozen : data;
  const events = (source ?? []).filter((e) => filter === "all" || e.kind === filter);

  return (
    <>
      <PageHeader
        title="Activity"
        description="Real-time feed of agent detections, analyses, workflows and approvals."
        actions={
          <>
            <span className="mr-1 inline-flex items-center text-xs text-muted-foreground">
              <StatusDot tone={paused ? "muted" : "success"} pulse={!paused} label={paused ? "Paused" : "Live"} />
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setFrozen(data ?? null);
                setPaused((p) => !p);
              }}
            >
              {paused ? <Play /> : <Pause />} {paused ? "Resume" : "Pause"}
            </Button>
          </>
        }
      />
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-3">
          <Segmented label="Filter activity" value={filter} onChange={setFilter} options={FILTERS} />
          <p className="text-xs text-muted-foreground">{events.length} events · newest first</p>
        </div>
        <CardContent>
          {isLoading ? (
            <ListSkeleton rows={8} />
          ) : error ? (
            <ErrorState error={error} what="activity" onRetry={() => refetch()} />
          ) : !events.length ? (
            <EmptyState title="No activity of this type yet" description="Agent events will appear here in real time as workflows run." action={{ label: "Show all activity", onClick: () => setFilter("all") }} />
          ) : (
            <div className="max-w-3xl">
              <ActivityFeed events={events} />
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}
