"use client";

import { useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { Bell, CheckCheck } from "lucide-react";
import type { Severity } from "@/types";
import { useMarkNotificationsRead, useNotifications } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/overlays";
import { SeverityIcon } from "@/components/shared/status";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/shared/states";
import { SEVERITY_STYLES } from "@/lib/constants";
import { cn, timeAgo } from "@/lib/utils";

const FILTERS: { value: Severity | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "critical", label: "Critical" },
  { value: "warning", label: "Warnings" },
  { value: "insight", label: "AI Insights" },
];

export function NotificationsMenu() {
  const { data, isLoading, error, refetch } = useNotifications();
  const markRead = useMarkNotificationsRead();
  const [filter, setFilter] = useState<Severity | "all">("all");
  const unread = data?.filter((n) => !n.read).length ?? 0;
  const items = (data ?? []).filter((n) => filter === "all" || n.severity === filter);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon-sm" className="relative" aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}>
          <Bell />
          {unread > 0 && (
            <span className="absolute top-1 right-1 flex min-w-4 items-center justify-center rounded-full bg-critical px-1 text-[10px] leading-4 font-semibold text-white tabular">
              {unread}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[min(400px,calc(100vw-2rem))] p-0">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div>
            <p className="text-sm font-semibold">Notifications</p>
            <p className="text-xs text-muted-foreground">{unread ? `${unread} unread` : "You're all caught up"}</p>
          </div>
          <Button variant="ghost" size="xs" disabled={!unread || markRead.isPending} onClick={() => markRead.mutate("all")}>
            <CheckCheck /> Mark all read
          </Button>
        </div>
        <div className="flex gap-1 border-b px-3 py-2" role="tablist" aria-label="Filter notifications">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              role="tab"
              aria-selected={filter === f.value}
              onClick={() => setFilter(f.value)}
              className={cn(
                "cursor-pointer rounded-md px-2 py-1 text-xs font-medium transition-colors",
                filter === f.value ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="max-h-[420px] overflow-y-auto">
          {isLoading ? (
            <ListSkeleton rows={4} />
          ) : error ? (
            <ErrorState error={error} what="notifications" onRetry={() => refetch()} />
          ) : !items.length ? (
            <EmptyState title="No notifications here" description="New alerts from your agents will appear in this panel." tone="positive" />
          ) : (
            <ul>
              <AnimatePresence initial={false}>
                {items.map((n) => (
                  <motion.li key={n.id} layout initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                    <div className={cn("flex gap-3 border-b px-4 py-3 last:border-0", !n.read && "bg-ai-soft/40")}>
                      <SeverityIcon severity={n.severity} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-[13px] font-semibold">
                            <span className="sr-only">{SEVERITY_STYLES[n.severity].label}: </span>
                            {n.title}
                          </p>
                          <span className="shrink-0 text-[11px] text-muted-foreground">{timeAgo(n.createdAt)}</span>
                        </div>
                        <p className="mt-0.5 text-[13px] leading-snug text-muted-foreground">{n.message}</p>
                        <div className="mt-1.5 flex items-center gap-3">
                          {n.href && (
                            <Link href={n.href} className="text-xs font-medium text-ai hover:underline" onClick={() => !n.read && markRead.mutate([n.id])}>
                              View details
                            </Link>
                          )}
                          {!n.read && (
                            <button className="cursor-pointer text-xs text-muted-foreground hover:text-foreground" onClick={() => markRead.mutate([n.id])}>
                              Mark as read
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
