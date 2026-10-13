"use client";
// Approvals: draft-order proposals awaiting a human decision. Approvers (portfolio manager,
// compliance) can approve or reject; the requester cannot approve their own proposal (API-enforced).
import { useState } from "react";

import { Badge, Button, Card, Empty, ErrorBox, Loading, PageHeader, Table, statusTone } from "@/components/ui";
import { api } from "@/lib/api";
import { money, num, when } from "@/lib/format";
import { useSession } from "@/presenters/session";
import { describe, useResource } from "@/presenters/useResource";
import type { Approval } from "@/types";

const FILTERS = ["pending", "approved", "rejected", "expired", ""] as const;

export default function ApprovalsPage() {
  const { token, can } = useSession();
  const [status, setStatus] = useState<(typeof FILTERS)[number]>("pending");
  const approvals = useResource(`approvals:${status}`, (t) => api.approvals(t, status || undefined));
  return (
    <>
      <PageHeader
        title="Approvals"
        subtitle="High-impact actions stop here: agent → risk validation → compliance validation → human approval → draft orders. Nothing is executed."
        actions={
          <div className="flex gap-1 rounded-lg border border-white/10 p-1 text-sm" role="tablist">
            {FILTERS.map((f) => (
              <button key={f || "all"} role="tab" aria-selected={status === f} onClick={() => setStatus(f)}
                className={`rounded-md px-3 py-1 ${status === f ? "bg-accent/15 text-accent" : "text-muted hover:text-white"}`}>
                {f || "all"}
              </button>
            ))}
          </div>
        }
      />
      <ErrorBox message={approvals.error} onRetry={approvals.reload} />
      {approvals.loading && !approvals.data && <Loading />}
      {approvals.data && !approvals.data.length && <Card><Empty>No {status || ""} approvals.</Empty></Card>}
      {approvals.data?.map((a) => (
        <ApprovalCard key={a.approvalId} approval={a} token={token} canDecide={can("approvals:decide")} onDecided={approvals.reload} />
      ))}
    </>
  );
}

function ApprovalCard({ approval: a, token, canDecide, onDecided }: { approval: Approval; token: string | null; canDecide: boolean; onDecided: () => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Approval | null>(null);

  const decide = async (approve: boolean) => {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await api.decide(token, a.approvalId, approve, note));
      onDecided();
    } catch (e) {
      setError(describe(e));
    } finally {
      setBusy(false);
    }
  };

  const orders = a.proposal.orders ?? [];
  return (
    <Card
      title={`${a.portfolio ?? "–"} · ${orders.length} draft orders · ${money(a.totalValue)}`}
      actions={<Badge tone={statusTone(a.status)}>{a.status}</Badge>}
    >
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-2 text-sm lg:col-span-1">
          <p className="text-muted">{a.proposal.question}</p>
          <ul className="list-disc space-y-1 pl-5">{a.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
          <p className="text-xs text-muted">
            Requested {when(a.createdAt)} · expires {when(a.expiresAt)} · request <span className="font-mono">{a.requestId}</span>
          </p>
          {a.decidedAt && (
            <p className="text-xs text-muted">Decided {when(a.decidedAt)}{a.decisionNote ? ` — “${a.decisionNote}”` : ""}</p>
          )}
        </div>
        <div className="lg:col-span-2">
          <Table head={["Ticker", "Side", "Quantity", "Est. price", "Est. value"]} empty={!orders.length}>
            {orders.map((o) => (
              <tr key={`${o.ticker}-${o.side}`}>
                <td className="px-2 py-1.5 font-mono text-xs">{o.ticker}</td>
                <td className={`px-2 py-1.5 ${o.side === "SELL" ? "text-bad" : "text-good"}`}>{o.side}</td>
                <td className="px-2 py-1.5 tabular-nums">{o.quantity.toLocaleString()}</td>
                <td className="px-2 py-1.5 tabular-nums">{num(o.price)}</td>
                <td className="px-2 py-1.5 tabular-nums">{money(o.value)}</td>
              </tr>
            ))}
          </Table>
        </div>
      </div>
      {a.status === "pending" && canDecide && !result && (
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-white/10 pt-4">
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} placeholder="Decision note (recorded in the audit trail)"
            aria-label="Decision note" className="min-w-0 flex-1 rounded-lg border border-white/10 bg-ink px-3 py-1.5 text-sm" />
          <Button onClick={() => decide(true)} disabled={busy}>Approve → create drafts</Button>
          <Button kind="danger" onClick={() => decide(false)} disabled={busy}>Reject</Button>
        </div>
      )}
      <ErrorBox message={error} />
      {result && (
        <p role="status" className="mt-3 text-sm">
          <Badge tone={statusTone(result.status)}>{result.status}</Badge>{" "}
          {result.createdDraftOrders?.length ?? 0} draft orders created (not executed).
        </p>
      )}
    </Card>
  );
}
