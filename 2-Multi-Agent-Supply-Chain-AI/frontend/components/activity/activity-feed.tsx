"use client";

import { AnimatePresence, motion } from "framer-motion";
import type { ActivityEvent } from "@/types";
import { STEP_META } from "@/components/agents/agent-meta";
import { SeverityIcon } from "@/components/shared/status";
import { SEVERITY_STYLES } from "@/lib/constants";
import { cn, fmt, formatTime, timeAgo } from "@/lib/utils";

function AgentBadge({ agent }: { agent: ActivityEvent["agent"] }) {
  if (agent === "system" || agent === "user") {
    return <span className="rounded bg-muted px-1.5 py-0.5 text-[10.5px] font-medium text-muted-foreground capitalize">{agent}</span>;
  }
  const meta = STEP_META[agent];
  return (
    <span className="inline-flex items-center gap-1 rounded bg-primary/[0.06] px-1.5 py-0.5 text-[10.5px] font-medium text-primary dark:bg-primary/10 dark:text-foreground">
      <meta.icon className="size-3" aria-hidden />
      {meta.short}
    </span>
  );
}

/** Timeline of agent activity. New events slide in at the top. */
export function ActivityFeed({ events, compact = false }: { events: ActivityEvent[]; compact?: boolean }) {
  return (
    <ol className="relative" aria-live="polite" aria-label="Agent activity">
      <AnimatePresence initial={false}>
        {events.map((e, i) => (
          <motion.li
            key={e.id}
            layout="position"
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className={cn("relative flex gap-3", compact ? "pb-4" : "pb-5")}
          >
            {i < events.length - 1 && <span className="absolute top-8 bottom-0 left-[13.5px] w-px bg-border" aria-hidden />}
            <SeverityIcon severity={e.severity} />
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <time dateTime={e.timestamp} className="font-mono text-[11px] text-muted-foreground tabular">
                  {formatTime(e.timestamp)}
                </time>
                <AgentBadge agent={e.agent} />
                {!compact && e.sku && <span className="font-mono text-[11px] text-muted-foreground">{e.sku}</span>}
                <span className="sr-only">{SEVERITY_STYLES[e.severity].label}</span>
              </div>
              <p className={cn("mt-1 leading-snug", compact ? "text-[13px]" : "text-[13.5px]")}>{e.message}</p>
              {!compact && (
                <p className="mt-0.5 text-[11.5px] text-muted-foreground">
                  {timeAgo(e.timestamp)}
                  {e.durationMs ? ` · ${fmt.ms(e.durationMs)}` : ""}
                  {e.runId ? ` · ${e.runId}` : ""}
                </p>
              )}
            </div>
          </motion.li>
        ))}
      </AnimatePresence>
    </ol>
  );
}
