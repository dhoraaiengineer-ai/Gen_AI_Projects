"use client";
// View: portfolio selector, headline metrics, top holdings and limit breaches.
import { money, pct } from "@/presenters/usePortfolios";
import type { PortfolioListItem, PortfolioView, RiskView } from "@/types";

interface Props {
  list: PortfolioListItem[];
  selected: string | null;
  onSelect: (id: string) => void;
  detail: PortfolioView | null;
  risk: RiskView | null;
  error: string | null;
}

export function PortfolioPanel({ list, selected, onSelect, detail, risk, error }: Props) {
  return (
    <aside className="w-full shrink-0 space-y-4 lg:w-80">
      <div className="rounded-2xl border border-white/10 bg-panel p-4">
        <label className="text-xs uppercase tracking-wide text-muted" htmlFor="portfolio">Portfolio</label>
        <select id="portfolio" value={selected ?? ""} onChange={(e) => onSelect(e.target.value)}
          className="mt-1 w-full rounded-lg border border-white/10 bg-ink px-2 py-2 text-sm">
          {list.map((p) => <option key={p.portfolioId} value={p.portfolioId}>{p.portfolioId} — {p.name}</option>)}
        </select>
        {error && <p className="mt-2 text-xs text-bad">{error}</p>}
        {!detail && !error && <div className="mt-4 h-24 animate-pulse rounded-lg bg-white/5" />}
        {detail && risk && (
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <Metric label="NAV" value={money(detail.nav)} />
            <Metric label="Daily P&L" value={money(detail.dailyPnl)} tone={detail.dailyPnl >= 0 ? "good" : "bad"} />
            <Metric label="VaR 95% 1d" value={pct(risk.var95, 2)} />
            <Metric label="Risk" value={risk.riskLevel ?? "–"} tone={risk.riskLevel === "LOW" ? "good" : risk.riskLevel === "MEDIUM" ? "warn" : "bad"} />
            <Metric label="Volatility" value={`${pct(risk.volatilityPriorQuarter)} → ${pct(risk.volatilityRecentQuarter)}`} />
            <Metric label="Breaches" value={String(detail.breaches)} tone={detail.breaches ? "bad" : "good"} />
          </dl>
        )}
      </div>
      {detail && (
        <div className="rounded-2xl border border-white/10 bg-panel p-4 text-sm">
          <h3 className="mb-2 font-medium">Top holdings</h3>
          <ul className="space-y-1.5">
            {detail.holdings.slice(0, 6).map((h) => (
              <li key={h.ticker} className="flex items-center gap-2">
                <span className="w-12 font-mono text-xs">{h.ticker}</span>
                <span className="h-1.5 flex-1 overflow-hidden rounded bg-white/5">
                  <span className="block h-full bg-accent" style={{ width: `${Math.min(h.weight * 300, 100)}%` }} />
                </span>
                <span className="w-12 text-right tabular-nums">{pct(h.weight)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {risk && risk.limitChecks.some((c) => c.breached) && (
        <div className="rounded-2xl border border-bad/30 bg-panel p-4 text-sm">
          <h3 className="mb-2 font-medium text-bad">Limit breaches</h3>
          <ul className="space-y-1">
            {risk.limitChecks.filter((c) => c.breached).map((c) => (
              <li key={`${c.limitType}-${c.subject}`}>
                <span className={c.severity === "hard" ? "text-bad" : "text-warn"}>{c.severity}</span>{" "}
                {c.subject} {pct(c.actual, c.limitType === "var_95_1d" ? 2 : 1)} vs {pct(c.threshold, c.limitType === "var_95_1d" ? 1 : 0)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "good" | "warn" | "bad" }) {
  const color = tone === "good" ? "text-good" : tone === "warn" ? "text-warn" : tone === "bad" ? "text-bad" : "";
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className={`font-semibold tabular-nums ${color}`}>{value}</dd>
    </div>
  );
}
