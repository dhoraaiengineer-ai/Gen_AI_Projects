"use client";
// Portfolios: holdings, sector weights, risk metrics and limit checks for one portfolio, plus
// one-click agent runs (risk review, rebalance proposal) through the structured endpoints.
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Badge, Bars, Button, Card, ErrorBox, Loading, PageHeader, Stat, Table, riskTone, statusTone } from "@/components/ui";
import { api } from "@/lib/api";
import { label, money, num, pct } from "@/lib/format";
import { useSession } from "@/presenters/session";
import { describe, useResource } from "@/presenters/useResource";
import type { ChatResponse } from "@/types";

export default function PortfoliosPage() {
  return (
    <Suspense fallback={<Loading />}>
      <Portfolios />
    </Suspense>
  );
}

function Portfolios() {
  const params = useSearchParams();
  const { token, can } = useSession();
  const list = useResource("portfolios", api.portfolios);
  const [chosen, setChosen] = useState<string | null>(null);
  const selected = chosen ?? params.get("id") ?? list.data?.[0]?.portfolioId ?? null;
  const detail = useResource(selected ? `portfolio:${selected}` : null, (t) => api.portfolio(t, selected!));
  const risk = useResource(selected ? `risk:${selected}` : null, (t) => api.risk(t, selected!));
  const [run, setRun] = useState<{ kind: string; result?: ChatResponse; error?: string } | null>(null);

  const analyze = async (kind: "risk" | "rebalance") => {
    if (!token || !selected) return;
    setRun({ kind });
    try {
      setRun({ kind, result: await api.analyze(token, kind, { portfolioId: selected }) });
    } catch (e) {
      setRun({ kind, error: describe(e) });
    }
  };

  const d = detail.data;
  const r = risk.data;
  return (
    <>
      <PageHeader
        title="Portfolios"
        actions={
          <select aria-label="Portfolio" value={selected ?? ""} onChange={(e) => setChosen(e.target.value)}
            className="rounded-lg border border-white/10 bg-panel px-3 py-2 text-sm">
            {(list.data ?? []).map((p) => <option key={p.portfolioId} value={p.portfolioId}>{p.portfolioId} — {p.name}</option>)}
          </select>
        }
      />
      <ErrorBox message={list.error ?? detail.error ?? risk.error} onRetry={() => { list.reload(); detail.reload(); risk.reload(); }} />
      {(!d || !r) && !detail.error && !risk.error && <Loading rows={5} />}
      {d && r && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="NAV" value={money(d.nav)} hint={`as of ${d.priceDate} · cash ${money(d.cash)}`} />
            <Stat label="Daily P&L" value={money(d.dailyPnl)} tone={d.dailyPnl >= 0 ? "good" : "bad"} hint={`${pct(d.dailyReturn, 2)} · 1y ${pct(d.return1y)}`} />
            <Stat label="Risk level" value={r.riskLevel ?? "–"} tone={riskTone(r.riskLevel)} hint={`volatility ${pct(r.volatilityPriorQuarter)} → ${pct(r.volatilityRecentQuarter)}`} />
            <Stat label="1-day VaR 95%" value={pct(r.var95, 2)} hint={`${money(r.var95Amount)} · CVaR ${pct(r.cvar95, 2)}`} />
          </div>
          {(can("risk:analyze") || can("portfolio:propose")) && (
            <Card title="Ask the agents">
              <div className="flex flex-wrap gap-2">
                {can("risk:analyze") && <Button onClick={() => analyze("risk")} disabled={run !== null && !run.result && !run.error}>Complete risk review</Button>}
                {can("portfolio:propose") && <Button kind="ghost" onClick={() => analyze("rebalance")} disabled={run !== null && !run.result && !run.error}>Propose a rebalance</Button>}
              </div>
              {run && !run.result && !run.error && <p className="mt-3 text-sm text-muted">Agents are working on the {run.kind === "risk" ? "risk review" : "rebalance proposal"}…</p>}
              <ErrorBox message={run?.error ?? null} />
              {run?.result && (
                <div className="mt-3 space-y-2 text-sm">
                  <p className="font-medium">{run.result.report.headline}</p>
                  {run.result.report.sections.interpretation && <p className="whitespace-pre-wrap text-muted">{run.result.report.sections.interpretation}</p>}
                  {run.result.report.approval.approvalId && (
                    <p>
                      <Badge tone="warn">approval {run.result.report.approval.status}</Badge>{" "}
                      {run.result.report.approval.draftOrders?.length ?? 0} draft orders —{" "}
                      <Link href="/approvals" className="text-accent hover:underline">review</Link>
                    </p>
                  )}
                  <p className="text-xs text-muted">{run.result.report.disclaimer} · request {run.result.requestId}</p>
                </div>
              )}
            </Card>
          )}
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Sector weights">
              <Bars items={Object.entries(d.sectorWeights).sort((a, b) => b[1] - a[1]).map(([sector, w]) => ({
                label: sector, value: w, text: pct(w), tone: w > 0.4 ? "bad" : w > 0.35 ? "warn" : undefined,
              }))} />
            </Card>
            <Card title="Risk metrics">
              <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                {[
                  ["Volatility (1y)", pct(r.volatility)], ["VaR 99% 1d", pct(r.var99, 2)], ["Max drawdown", pct(r.maxDrawdown)],
                  ["Beta", num(r.beta)], ["Sharpe", num(r.sharpe)], ["Sortino", num(r.sortino)], ["Effective holdings", num(r.effectiveHoldings, 1)],
                ].map(([k, v]) => (
                  <div key={k}><dt className="text-xs text-muted">{k}</dt><dd className="font-semibold tabular-nums">{v}</dd></div>
                ))}
              </dl>
            </Card>
          </div>
          <Card title="Limit checks">
            <Table head={["Limit", "Subject", "Actual", "Threshold", "Headroom", "Status", "Policy"]} empty={!r.limitChecks.length}>
              {r.limitChecks.map((c) => {
                const digits = c.limitType.startsWith("var") ? 2 : 1;
                return (
                  <tr key={`${c.limitType}-${c.subject}`}>
                    <td className="px-2 py-2">{label(c.limitType)}</td>
                    <td className="px-2 py-2">{c.subject}</td>
                    <td className="px-2 py-2 tabular-nums">{pct(c.actual, digits)}</td>
                    <td className="px-2 py-2 tabular-nums">{pct(c.threshold, digits)}</td>
                    <td className={`px-2 py-2 tabular-nums ${c.headroom < 0 ? "text-bad" : ""}`}>{pct(c.headroom, digits)}</td>
                    <td className="px-2 py-2">{c.breached ? <Badge tone={statusTone(c.severity)}>{c.severity}</Badge> : <Badge tone="good">ok</Badge>}</td>
                    <td className="px-2 py-2 text-xs text-muted">{c.policyReference ?? "–"}</td>
                  </tr>
                );
              })}
            </Table>
          </Card>
          <Card title={`Holdings (${d.holdings.length})`}>
            <Table head={["Ticker", "Name", "Sector", "Weight", "Value", "Unrealised P&L", "Risk contribution"]} empty={!d.holdings.length}>
              {d.holdings.map((h) => (
                <tr key={h.ticker}>
                  <td className="px-2 py-2 font-mono text-xs">{h.ticker}</td>
                  <td className="px-2 py-2">{h.name}</td>
                  <td className="px-2 py-2 text-muted">{h.sector}</td>
                  <td className="px-2 py-2 tabular-nums">{pct(h.weight)}</td>
                  <td className="px-2 py-2 tabular-nums">{money(h.value)}</td>
                  <td className={`px-2 py-2 tabular-nums ${h.unrealisedPnl >= 0 ? "text-good" : "text-bad"}`}>{money(h.unrealisedPnl)}</td>
                  <td className="px-2 py-2 tabular-nums">{pct(h.riskContribution)}</td>
                </tr>
              ))}
            </Table>
          </Card>
        </>
      )}
    </>
  );
}
