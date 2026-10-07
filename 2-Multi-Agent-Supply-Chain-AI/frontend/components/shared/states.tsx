"use client";

import type { LucideIcon } from "lucide-react";
import { AlertTriangle, CircleCheck, RefreshCw } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/primitives";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Professional error state: a clear message, the request ID for support, and a retry action. Never a stack trace. */
export function ErrorState({
  error,
  title = "Something went wrong",
  what = "this data",
  onRetry,
  className,
}: {
  error: unknown;
  title?: string;
  what?: string;
  onRetry?: () => void;
  className?: string;
}) {
  const apiErr = error instanceof ApiError ? error : null;
  const message =
    apiErr?.status === 404
      ? apiErr.message
      : apiErr?.status === 403
        ? "You don't have permission to view this. Ask an administrator for access."
        : apiErr?.status === 429
          ? "Too many requests. Please wait a moment and try again."
          : `We couldn't retrieve ${what}.`;
  return (
    <div role="alert" className={cn("flex flex-col items-center justify-center gap-3 px-6 py-10 text-center", className)}>
      <div className="flex size-10 items-center justify-center rounded-full bg-critical/10 text-critical">
        <AlertTriangle className="size-5" aria-hidden />
      </div>
      <div>
        <p className="text-sm font-semibold">{title}</p>
        <p className="mt-1 text-[13px] text-muted-foreground">{message}</p>
        {apiErr?.requestId && (
          <p className="mt-2 font-mono text-[11px] text-muted-foreground">
            Request ID: <span className="select-all">{apiErr.requestId}</span>
          </p>
        )}
      </div>
      {onRetry && (apiErr?.retryable ?? true) && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw /> Retry
        </Button>
      )}
    </div>
  );
}

/** Useful empty state: explains why it is empty and what to do next. */
export function EmptyState({
  icon: Icon = CircleCheck,
  title,
  description,
  action,
  tone = "neutral",
  className,
}: {
  icon?: LucideIcon;
  title: string;
  description: string;
  action?: { label: string; href?: string; onClick?: () => void };
  tone?: "neutral" | "positive";
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-3 px-6 py-10 text-center", className)}>
      <div
        className={cn(
          "flex size-10 items-center justify-center rounded-full",
          tone === "positive" ? "bg-success/10 text-success" : "bg-muted text-muted-foreground",
        )}
      >
        <Icon className="size-5" aria-hidden />
      </div>
      <div>
        <p className="text-sm font-semibold">{title}</p>
        <p className="mt-1 max-w-sm text-[13px] text-muted-foreground">{description}</p>
      </div>
      {action &&
        (action.href ? (
          <Button asChild variant="outline" size="sm">
            <Link href={action.href}>{action.label}</Link>
          </Button>
        ) : (
          <Button variant="outline" size="sm" onClick={action.onClick}>
            {action.label}
          </Button>
        ))}
    </div>
  );
}

export function KpiSkeleton() {
  return (
    <div className="rounded-lg border bg-card p-5 shadow-card">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="mt-4 h-8 w-20" />
      <Skeleton className="mt-3 h-3 w-36" />
    </div>
  );
}

export function ChartSkeleton({ className, label = "Loading chart" }: { className?: string; label?: string }) {
  return (
    <div className={cn("flex h-64 flex-col justify-end gap-2 p-1", className)} role="status" aria-label={label}>
      <div className="flex h-full items-end gap-2">
        {[38, 52, 46, 61, 57, 70, 66, 74, 69, 81, 77, 86].map((h, i) => (
          <Skeleton key={i} className="flex-1 rounded-sm" style={{ height: `${h}%` }} />
        ))}
      </div>
      <Skeleton className="h-3 w-full" />
    </div>
  );
}

export function TableSkeleton({ rows = 8, cols = 6 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-0 px-5 py-2" role="status" aria-label="Loading table">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex items-center gap-4 border-b py-3 last:border-0">
          {Array.from({ length: cols }).map((__, c) => (
            <Skeleton key={c} className={cn("h-3.5", c === 1 ? "w-48" : "w-20")} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function ListSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-4 p-5" role="status" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-start gap-3">
          <Skeleton className="size-8 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3.5 w-3/4" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        </div>
      ))}
    </div>
  );
}
