"use client";
// Overview: firm-wide KPIs, portfolios with risk and breaches, pending approvals, recent activity.
import Link from "next/link";

import { Badge, Card, ErrorBox, Loading, PageHeader, Stat, Table, statusTone } from "@/components/ui";
import { api } from "@/lib/api";
import { label, money, pct, when } from "@/lib/format";
import { useResource } from "@/presenters/useResource";

export default function OverviewPage() {
  const overview = useResource("overview", api.overview);
  const o = overview.data;
  return (
    <>
      <PageHeader title="Overview" subtitle={o ? `Prices as of ${o.portfolios[0]?.priceDate ?? "–"}` : undefined} />
      <ErrorBox message={overview.error} onRetry={overview.reload} />
      {!o && !overview.error && <Loading rows={4} />}
      {o && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Assets under management" value={money(o.totals.nav)} hint={`${o.portfolios.length} portfolios`} />
            <Stat label="Limit breaches" value={String(o.totals.breaches)} tone={o.totals.breaches ? "bad" : "good"} hint="hard + warning" />
            <Stat label="Pending approvals" value={String(o.totals.pendingApprovals)} tone={o.totals.pendingApprovals ? "warn" : "good"} hint="draft orders awaiting a decision" />
            <Stat label="Largest 1-day VaR 95%" value={pct(Math.max(...o.portfolios.map((p) => p.var95)), 2)} hint="share of NAV" />
          </div>
          <Card title="Portfolios">
            <Table head={["Portfolio", "NAV", "1d", "1y", "Volatility", "VaR 95% 1d", "Breaches", ""]} empty={!o.portfolios.length}>
              {o.portfolios.map((p) => (
                <tr key={p.portfolioId}>
                  <td className="px-2 py-2"><span className="font-mono text-xs text-muted">{p.portfolioId}</span> {p.name}</td>
                  <td className="px-2 py-2 tabular-nums">{money(p.nav)}</td>
                  <td className={`px-2 py-2 tabular-nums ${p.dailyReturn >= 0 ? "text-good" : "text-bad"}`}>{pct(p.dailyReturn, 2)}</td>
                  <td className="px-2 py-2 tabular-nums">{pct(p.return1y)}</td>
                  <td className="px-2 py-2 tabular-nums">{pct(p.volatility)}</td>
                  <td className="px-2 py-2 tabular-nums">{pct(p.var95, 2)}</td>
                  <td className="px-2 py-2">{p.breaches ? <Badge tone="bad">{p.breaches}</Badge> : <Badge tone="good">0</Badge>}</td>
                  <td className="px-2 py-2 text-right"><Link className="text-accent hover:underline" href={`/portfolios?id=${p.portfolioId}`}>Open</Link></td>
                </tr>
              ))}
            </Table>
          </Card>
          <Card title="Recent activity" actions={<Link href="/assistant" className="text-sm text-accent hover:underline">Ask the assistant →</Link>}>
            <Table head={["When", "Action", "Decision", "Reason", "Role"]} empty={!o.recentActivity.length}>
              {o.recentActivity.map((a, i) => (
                <tr key={i}>
                  <td className="whitespace-nowrap px-2 py-2 text-muted">{when(a.at)}</td>
                  <td className="px-2 py-2 font-mono text-xs">{a.action}</td>
                  <td className="px-2 py-2"><Badge tone={statusTone(a.decision)}>{a.decision}</Badge></td>
                  <td className="px-2 py-2">{a.reason ?? "–"}</td>
                  <td className="px-2 py-2 text-muted">{label(a.userRole)}</td>
                </tr>
              ))}
            </Table>
          </Card>
        </>
      )}
    </>
  );
}
