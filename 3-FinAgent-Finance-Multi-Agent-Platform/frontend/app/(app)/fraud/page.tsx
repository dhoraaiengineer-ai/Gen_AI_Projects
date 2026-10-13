"use client";
// Fraud: latest fraud-model scores (with reason codes) and an on-demand fraud review by the agent.
import { useState } from "react";

import { Badge, Button, Card, Empty, ErrorBox, Loading, PageHeader, Table, riskTone } from "@/components/ui";
import { api } from "@/lib/api";
import { money, when } from "@/lib/format";
import { useSession } from "@/presenters/session";
import { describe, useResource } from "@/presenters/useResource";
import type { ChatResponse } from "@/types";

export default function FraudPage() {
  const { token } = useSession();
  const fraud = useResource("fraud", api.fraud);
  const [subject, setSubject] = useState("TX-004512");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ChatResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const review = async () => {
    if (!token || !subject.trim()) return;
    setBusy(true);
    setError(null);
    const s = subject.trim().toUpperCase();
    try {
      setResult(await api.analyze(token, "fraud", s.startsWith("TX") ? { transactionId: s } : { customerId: s }));
      fraud.reload();
    } catch (e) {
      setError(describe(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader title="Fraud" subtitle="LightGBM + Isolation Forest scores with reason codes. Predictions, not verdicts — an analyst reviews every alert." />
      <Card title="Review a transaction or customer">
        <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); void review(); }}>
          <input value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={40} aria-label="Transaction or customer id"
            placeholder="TX-004512 or CUST-00042" className="rounded-lg border border-white/10 bg-ink px-3 py-2 text-sm" />
          <Button type="submit" disabled={busy}>{busy ? "Fraud agent working…" : "Run fraud review"}</Button>
        </form>
        <ErrorBox message={error} />
        {result && (
          <div className="mt-3 space-y-1 text-sm">
            <p className="font-medium">{result.report.headline}</p>
            <ul className="list-disc pl-5 text-muted">
              {[...result.report.sections.mlPredictions, ...result.report.sections.facts].slice(0, 6).map((f, i) => <li key={i}>{f.text}</li>)}
            </ul>
          </div>
        )}
      </Card>
      <Card title="Latest scored transactions">
        <ErrorBox message={fraud.error} onRetry={fraud.reload} />
        {!fraud.data && !fraud.error && <Loading />}
        {fraud.data && !fraud.data.alerts.length && <Empty>No transactions scored yet — run a fraud review above.</Empty>}
        {fraud.data && fraud.data.alerts.length > 0 && (
          <>
            <Table head={["Transaction", "When", "Amount", "Category / channel", "Country", "Probability", "Level", "Reasons", "Model"]}>
              {fraud.data.alerts.map((a) => (
                <tr key={a.transactionId}>
                  <td className="px-2 py-2 font-mono text-xs">{a.transactionId}</td>
                  <td className="whitespace-nowrap px-2 py-2 text-muted">{when(a.at)}</td>
                  <td className="px-2 py-2 tabular-nums">{money(a.amount)}</td>
                  <td className="px-2 py-2 text-muted">{a.category} · {a.channel}</td>
                  <td className="px-2 py-2">{a.country}</td>
                  <td className="px-2 py-2 tabular-nums">{a.probability.toFixed(2)}</td>
                  <td className="px-2 py-2"><Badge tone={riskTone(a.riskLevel === "CRITICAL" ? "HIGH" : a.riskLevel)}>{a.riskLevel}</Badge></td>
                  <td className="px-2 py-2 text-xs">{a.reasons.join("; ")}</td>
                  <td className="px-2 py-2 text-xs text-muted">{a.modelVersion}</td>
                </tr>
              ))}
            </Table>
            <p className="mt-3 text-xs text-muted">{fraud.data.note}</p>
          </>
        )}
      </Card>
    </>
  );
}
