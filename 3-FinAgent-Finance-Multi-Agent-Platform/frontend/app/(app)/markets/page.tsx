"use client";
// Markets: benchmark, one-month sector performance and recent news (each item links to its source).
import { Bars, Card, ErrorBox, Loading, PageHeader, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { pct, when } from "@/lib/format";
import { useResource } from "@/presenters/useResource";

export default function MarketsPage() {
  const markets = useResource("markets", api.markets);
  const news = useResource("news", api.news);
  const m = markets.data;
  return (
    <>
      <PageHeader title="Markets" subtitle={m ? `Market data as of ${m.date}` : undefined} />
      <ErrorBox message={markets.error} onRetry={markets.reload} />
      {!m && !markets.error && <Loading rows={4} />}
      {m && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label={`${m.benchmark.ticker} level`} value={m.benchmark.level.toFixed(2)} />
            <Stat label="1 day" value={pct(m.benchmark.return1d, 2)} tone={m.benchmark.return1d >= 0 ? "good" : "bad"} />
            <Stat label="1 month" value={pct(m.benchmark.return1m)} tone={m.benchmark.return1m >= 0 ? "good" : "bad"} />
            <Stat label="3-month volatility" value={pct(m.benchmark.volatility3m)} hint="annualised" />
          </div>
          <Card title="Sector performance (1 month)">
            <Bars items={m.sectors.map((s) => ({ label: `${s.sector} (${s.names})`, value: s.return1m, text: pct(s.return1m), tone: s.return1m >= 0 ? "good" : "bad" }))} />
          </Card>
        </>
      )}
      <Card title="News">
        <ErrorBox message={news.error} onRetry={news.reload} />
        {!news.data && !news.error && <Loading />}
        <ul className="space-y-3 text-sm">
          {news.data?.items.map((n) => (
            <li key={n.url}>
              <a href={n.url} target="_blank" rel="noreferrer" className="font-medium text-accent hover:underline">{n.title}</a>
              <p className="text-muted">{n.summary}</p>
              <p className="text-xs text-muted">{n.source} · {when(n.published)}{n.tickers.length ? ` · ${n.tickers.join(", ")}` : ""}</p>
            </li>
          ))}
        </ul>
        {news.data && <p className="mt-3 text-xs text-muted">Provider: {news.data.provider}</p>}
      </Card>
    </>
  );
}
