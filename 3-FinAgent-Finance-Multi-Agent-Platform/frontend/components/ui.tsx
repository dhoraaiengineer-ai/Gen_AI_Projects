// Views: small presentational building blocks shared by every page (no data fetching here).
import type { ReactNode } from "react";

export type Tone = "good" | "warn" | "bad" | "accent" | "muted";

const TONE_TEXT: Record<Tone, string> = {
  good: "text-good",
  warn: "text-warn",
  bad: "text-bad",
  accent: "text-accent",
  muted: "text-muted",
};

const TONE_BADGE: Record<Tone, string> = {
  good: "bg-good/15 text-good",
  warn: "bg-warn/15 text-warn",
  bad: "bg-bad/15 text-bad",
  accent: "bg-accent/15 text-accent",
  muted: "bg-white/5 text-muted",
};

export const riskTone = (level: string | null | undefined): Tone =>
  level === "LOW" ? "good" : level === "MEDIUM" ? "warn" : level ? "bad" : "muted";

export const statusTone = (status: string | null | undefined): Tone =>
  ({ ok: "good", approved: "good", ready: "good", allow: "good", pending: "warn", partial: "warn", flag: "warn",
     warning: "warn", failed: "bad", rejected: "bad", deny: "bad", block: "bad", hard: "bad", expired: "muted",
     error: "bad", denied: "bad", timeout: "bad" } as Record<string, Tone>)[status ?? ""] ?? "muted";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions}
    </header>
  );
}

export function Card({ title, children, className = "", actions }: { title?: string; children: ReactNode; className?: string; actions?: ReactNode }) {
  return (
    <section className={`rounded-2xl border border-white/10 bg-panel p-4 ${className}`}>
      {(title || actions) && (
        <div className="mb-3 flex items-center justify-between gap-2">
          {title && <h2 className="font-medium">{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, tone, hint }: { label: string; value: string; tone?: Tone; hint?: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-panel p-4">
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className={`mt-1 text-2xl font-semibold tabular-nums ${tone ? TONE_TEXT[tone] : ""}`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}

export function Badge({ children, tone = "muted" }: { children: ReactNode; tone?: Tone }) {
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${TONE_BADGE[tone]}`}>{children}</span>;
}

export function ErrorBox({ message, onRetry }: { message: string | null; onRetry?: () => void }) {
  if (!message) return null;
  return (
    <div role="alert" className="flex items-center justify-between gap-3 rounded-xl border border-bad/30 bg-bad/10 px-4 py-3 text-sm text-bad">
      <span>{message}</span>
      {onRetry && <button onClick={onRetry} className="rounded-lg border border-bad/40 px-2 py-1 text-xs hover:bg-bad/20">Retry</button>}
    </div>
  );
}

export function Loading({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-2" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => <div key={i} className="h-6 animate-pulse rounded bg-white/5" />)}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-center text-sm text-muted">{children}</p>;
}

/** Horizontal bars for shares (0..1); the value label is supplied by the caller. */
export function Bars({ items, max }: { items: { label: string; value: number; text: string; tone?: Tone }[]; max?: number }) {
  const top = max ?? Math.max(...items.map((i) => Math.abs(i.value)), 1e-9);
  return (
    <ul className="space-y-1.5 text-sm">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-2">
          <span className="w-40 shrink-0 truncate" title={item.label}>{item.label}</span>
          <span className="h-2 flex-1 overflow-hidden rounded bg-white/5">
            <span
              className={`block h-full ${item.tone === "bad" ? "bg-bad" : item.tone === "warn" ? "bg-warn" : item.tone === "good" ? "bg-good" : "bg-accent"}`}
              style={{ width: `${Math.min((Math.abs(item.value) / top) * 100, 100)}%` }}
            />
          </span>
          <span className="w-16 shrink-0 text-right tabular-nums">{item.text}</span>
        </li>
      ))}
    </ul>
  );
}

export function Table({ head, children, empty }: { head: string[]; children: ReactNode; empty?: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase tracking-wide text-muted">
          <tr>{head.map((h) => <th key={h} className="whitespace-nowrap px-2 py-2 font-medium">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-white/5">{children}</tbody>
      </table>
      {empty && <Empty>Nothing to show yet.</Empty>}
    </div>
  );
}

export function Button({
  children,
  onClick,
  disabled,
  kind = "primary",
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  kind?: "primary" | "ghost" | "danger";
  type?: "button" | "submit";
}) {
  const style =
    kind === "primary"
      ? "bg-accent text-ink hover:opacity-90"
      : kind === "danger"
        ? "border border-bad/40 text-bad hover:bg-bad/10"
        : "border border-white/10 hover:border-accent";
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`rounded-lg px-3 py-1.5 text-sm font-medium disabled:opacity-50 ${style}`}>
      {children}
    </button>
  );
}
